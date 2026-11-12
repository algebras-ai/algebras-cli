"""
Write cell values straight into an .xlsx package, without an openpyxl load/save round-trip.

openpyxl rebuilds the whole workbook when it saves, and drops what it does not model: images
(without Pillow), shapes, SmartArt, form controls, slicers, custom XML, and charts it cannot fully
read. A translation only changes text cells, so this module edits the package directly:

- the zip is read and written back entry by entry; every part other than the edited worksheets is
  copied unchanged (same bytes, same order, same zip metadata);
- in a worksheet part only <sheetData> (the written cells, and new <row> elements when needed),
  <dimension> and, for a new language column, <cols> change. The rest of the XML is kept as text;
- a written cell becomes an inline string (t="inlineStr"), so sharedStrings.xml, the content types
  and the relationships never change. Its other attributes stay, in particular its style (s=);
- a cell that does not exist yet is inserted in its row in column order, and a row that does not
  exist yet is inserted in row order.

Anything outside that (no workbook part, a strict-OOXML package, rows or cells without an r=
reference, a non-UTF-8 part, a target cell holding a formula) raises PackageEditError; the caller
then decides whether an openpyxl save is acceptable (see openpyxl_losses).
"""

import os
import posixpath
import re
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from openpyxl.utils import column_index_from_string, get_column_letter

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOCUMENT = REL_NS + "/officeDocument"


class PackageEditError(Exception):
    """The workbook cannot be edited at the package level (see the module docstring)."""


class SheetEdit:
    """
    Edits for one worksheet.

    cells: {coordinate: value}; value is a str (plain text, "" empties the cell) or a CellRichText.
    style_from: {coordinate: coordinate}; a new cell takes the s= of another cell of the sheet
        (a new language header takes the style of the header before it).
    copy_columns: [(from_index, to_index)]; a new column gets the <col> (width, style) of another.
    """

    def __init__(self):
        self.cells: Dict[str, object] = {}
        self.style_from: Dict[str, str] = {}
        self.copy_columns: List[Tuple[int, int]] = []


# ---------------------------------------------------------------------------
# What an openpyxl save would lose
# ---------------------------------------------------------------------------

_LOSSY_PARTS = (
    ("xl/media/", "images"),
    ("xl/charts/", "charts"),
    ("xl/chartsheets/", "chart sheets"),
    ("xl/drawings/drawing", "drawings and shapes"),
    ("xl/diagrams/", "SmartArt"),
    ("xl/embeddings/", "embedded objects"),
    ("xl/activeX/", "ActiveX controls"),
    ("xl/ctrlProps/", "form controls"),
    ("xl/slicers/", "slicers"),
    ("xl/slicerCaches/", "slicers"),
    ("xl/timelines/", "timelines"),
    ("customXml/", "custom XML"),
)


def openpyxl_losses(path: str) -> List[str]:
    """Kinds of content in the package that an openpyxl load/save would drop (or may drop)."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    except (OSError, zipfile.BadZipFile):
        return []
    found: List[str] = []
    for prefix, label in _LOSSY_PARTS:
        if label not in found and any(n.startswith(prefix) for n in names):
            found.append(label)
    return found


# ---------------------------------------------------------------------------
# Package structure
# ---------------------------------------------------------------------------


def _resolve(base_dir: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(base_dir, target))


def _rels_name(part: str) -> str:
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def sheet_parts(zf: zipfile.ZipFile) -> Dict[str, str]:
    """{sheet title: worksheet part name} of the workbook."""
    names = set(zf.namelist())
    try:
        root_rels = ET.fromstring(zf.read("_rels/.rels"))
    except (KeyError, ET.ParseError) as e:
        raise PackageEditError(f"no package relationships ({e})")
    workbook_part = None
    for rel in root_rels.iter(f"{{{PKG_REL_NS}}}Relationship"):
        if rel.get("Type") == OFFICE_DOCUMENT:
            workbook_part = _resolve("", rel.get("Target", ""))
    if not workbook_part or workbook_part not in names:
        raise PackageEditError("no workbook part (strict OOXML or not a workbook)")
    workbook = ET.fromstring(zf.read(workbook_part))
    if workbook.tag != f"{{{MAIN_NS}}}workbook":
        raise PackageEditError(f"unsupported workbook namespace {workbook.tag}")
    rels = ET.fromstring(zf.read(_rels_name(workbook_part)))
    targets = {
        rel.get("Id"): _resolve(posixpath.dirname(workbook_part), rel.get("Target", ""))
        for rel in rels.iter(f"{{{PKG_REL_NS}}}Relationship")
    }
    parts: Dict[str, str] = {}
    for sheet in workbook.iter(f"{{{MAIN_NS}}}sheet"):
        part = targets.get(sheet.get(f"{{{REL_NS}}}id"))
        if part in names:
            parts[sheet.get("name")] = part
    return parts


# ---------------------------------------------------------------------------
# Cell XML
# ---------------------------------------------------------------------------

_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _text(value: str) -> str:
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")
    return _ILLEGAL.sub(lambda m: "_x%04X_" % ord(m.group()), value)


def _attr(value: str) -> str:
    return _text(value).replace('"', "&quot;")


def _prefixed(xml: str, prefix: str) -> str:
    """Put the sheet's namespace prefix on every element of a generated fragment."""
    if not prefix:
        return xml
    return re.sub(r"<(/?)([A-Za-z])", lambda m: f"<{m.group(1)}{prefix}:{m.group(2)}", xml)


def _inline_string(value) -> str:
    if isinstance(value, str):
        return f'<is><t xml:space="preserve">{_text(value)}</t></is>'
    runs = []
    for run in value:  # CellRichText: str or TextBlock items
        if isinstance(run, str):
            text, font = run, None
        else:
            text, font = run.text, run.font
        if not text:
            continue
        rpr = ""
        if font is not None:
            rpr = ET.tostring(font.to_tree(tagname="rPr"), encoding="unicode")
            rpr = rpr.replace(" />", "/>")
            if rpr == "<rPr/>":
                rpr = ""
        runs.append(f'<r>{rpr}<t xml:space="preserve">{_text(text)}</t></r>')
    return "<is>" + "".join(runs) + "</is>"


_ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*("[^"]*"|\'[^\']*\')')


def _attrs(text: str) -> List[Tuple[str, str]]:
    return [(k, v[1:-1]) for k, v in _ATTR_RE.findall(text)]


def _cell_xml(prefix: str, ref: str, attrs: List[Tuple[str, str]], value) -> str:
    # The value type (t), value metadata (cm, vm) and the phonetic flag belong to the old value.
    kept = [(k, v) for k, v in attrs if k not in ("r", "t", "cm", "vm", "ph")]
    is_empty = value is None or (isinstance(value, str) and value == "")
    head = f'r="{ref}"' + "".join(f' {k}="{v}"' for k, v in kept)
    if is_empty:
        return _prefixed(f"<c {head}/>", prefix)
    return _prefixed(f'<c {head} t="inlineStr">{_inline_string(value)}</c>', prefix)


# ---------------------------------------------------------------------------
# Worksheet editing
# ---------------------------------------------------------------------------


def _split_ref(ref: str) -> Tuple[int, int]:
    m = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", ref)
    if not m:
        raise PackageEditError(f"bad cell reference {ref!r}")
    return column_index_from_string(m.group(1)), int(m.group(2))


class _Row:
    def __init__(self, number: int, open_tag: str, cells: List[Tuple[int, str, str]], closed: bool, raw: str = ""):
        self.number = number
        self.raw = raw  # the row as written in the file (kept as is when the row is not edited)
        self.open_tag = open_tag  # "<row ...>" (as written, also for a self-closing row)
        self.cells = cells  # [(column index, coordinate, cell xml)]
        self.closed = closed  # was self-closing


def _edit_sheet_xml(xml: str, edit: SheetEdit) -> str:
    m = re.search(r"<(?:(\w+):)?sheetData\b[^>]*?(/?)>", xml)
    if not m:
        raise PackageEditError("worksheet without <sheetData>")
    prefix = m.group(1) or ""
    p = f"{prefix}:" if prefix else ""
    if m.group(2):  # <sheetData/>
        open_tag = m.group(0)[:-2].rstrip() + ">"
        close_tag = f"</{p}sheetData>"
        head, tail = xml[: m.start()], xml[m.end():]
        body = ""
    else:
        close = xml.find(f"</{p}sheetData>", m.end())
        if close < 0:
            raise PackageEditError("unterminated <sheetData>")
        open_tag = m.group(0)
        close_tag = f"</{p}sheetData>"
        head, body, tail = xml[: m.start()], xml[m.end():close], xml[close + len(close_tag):]

    row_re = re.compile(rf"<{re.escape(p)}row\b([^>]*?)(?:/>|>(.*?)</{re.escape(p)}row>)", re.S)
    cell_re = re.compile(rf"<{re.escape(p)}c\b([^>]*?)(?:/>|>(.*?)</{re.escape(p)}c>)", re.S)

    rows: List[_Row] = []
    pos = 0
    for rm in row_re.finditer(body):
        if body[pos:rm.start()].strip():
            raise PackageEditError("unexpected content in <sheetData>")
        pos = rm.end()
        row_attrs = dict(_attrs(rm.group(1)))
        if "r" not in row_attrs:
            raise PackageEditError("a <row> without an r= attribute")
        cells: List[Tuple[int, str, str]] = []
        inner = rm.group(2) or ""
        cpos = 0
        for cm in cell_re.finditer(inner):
            if inner[cpos:cm.start()].strip():
                raise PackageEditError("unexpected content in <row>")
            cpos = cm.end()
            ref = dict(_attrs(cm.group(1))).get("r")
            if not ref:
                raise PackageEditError("a <c> without an r= attribute")
            cells.append((_split_ref(ref)[0], ref, cm.group(0)))
        if inner[cpos:].strip():
            raise PackageEditError("unexpected content in <row>")
        tag_end = rm.group(0).index(">")
        tag = rm.group(0)[: tag_end + 1]
        closed = tag.endswith("/>")
        if closed:
            tag = tag[:-2].rstrip() + ">"
        rows.append(_Row(int(row_attrs["r"]), tag, cells, closed, rm.group(0)))
    if body[pos:].strip():
        raise PackageEditError("unexpected content in <sheetData>")

    by_number = {row.number: row for row in rows}

    def cell_attrs(ref: str) -> Optional[List[Tuple[str, str]]]:
        col, row_no = _split_ref(ref)
        row = by_number.get(row_no)
        if row is None:
            return None
        for c_col, _, c_xml in row.cells:
            if c_col == col:
                return _attrs(c_xml[: c_xml.index(">")])
        return None

    touched_rows = set()
    max_col = max_row = 0
    for ref, value in edit.cells.items():
        col, row_no = _split_ref(ref)
        max_col, max_row = max(max_col, col), max(max_row, row_no)
        ref = f"{get_column_letter(col)}{row_no}"
        row = by_number.get(row_no)
        if row is None:
            row = _Row(row_no, _prefixed(f'<row r="{row_no}">', prefix), [], False)
            by_number[row_no] = row
            rows.append(row)
        touched_rows.add(row_no)
        existing = None
        for i, (c_col, _, c_xml) in enumerate(row.cells):
            if c_col == col:
                existing = i
                break
        if existing is not None:
            c_xml = row.cells[existing][2]
            if re.search(rf"<{re.escape(p)}f\b", c_xml):
                raise PackageEditError(f"cell {ref} holds a formula")
            attrs = _attrs(c_xml[: c_xml.index(">")].rstrip("/"))
            row.cells[existing] = (col, ref, _cell_xml(prefix, ref, attrs, value))
        else:
            attrs: List[Tuple[str, str]] = []
            source = edit.style_from.get(ref)
            if source:
                style = dict(cell_attrs(source) or []).get("s")
                if style:
                    attrs = [("s", style)]
            row.cells.append((col, ref, _cell_xml(prefix, ref, attrs, value)))
            row.cells.sort(key=lambda c: c[0])

    rows.sort(key=lambda r: r.number)
    out = []
    for row in rows:
        if row.number not in touched_rows and row.raw:
            out.append(row.raw)
            continue
        tag = row.open_tag
        if row.cells:
            spans = re.search(r'\bspans="(\d+):(\d+)"', tag)
            if spans:
                lo = min(int(spans.group(1)), row.cells[0][0])
                hi = max(int(spans.group(2)), row.cells[-1][0])
                tag = tag[: spans.start()] + f'spans="{lo}:{hi}"' + tag[spans.end():]
        if row.closed and not row.cells:
            out.append(tag[:-1].rstrip() + "/>")
        else:
            out.append(tag + "".join(c[2] for c in row.cells) + f"</{p}row>")

    xml = head + open_tag + "".join(out) + close_tag + tail
    xml = _update_dimension(xml, p, max_col, max_row)
    if edit.copy_columns:
        xml = _copy_columns(xml, p, edit.copy_columns)
    return xml


def _update_dimension(xml: str, p: str, max_col: int, max_row: int) -> str:
    m = re.search(rf'<{re.escape(p)}dimension\b[^>]*?\bref="([^"]*)"', xml)
    if not m or not max_col:
        return xml
    ref = m.group(1)
    try:
        if ":" in ref:
            first, last = ref.split(":", 1)
        else:
            first = last = ref
        c1, r1 = _split_ref(first)
        c2, r2 = _split_ref(last)
    except PackageEditError:
        return xml
    c2, r2 = max(c2, max_col), max(r2, max_row)
    new = f"{get_column_letter(c1)}{r1}:{get_column_letter(c2)}{r2}"
    if new == ref:
        return xml
    return xml[: m.start(1)] + new + xml[m.end(1):]


def _copy_columns(xml: str, p: str, copies: List[Tuple[int, int]]) -> str:
    m = re.search(rf"<{re.escape(p)}cols\b[^>]*>(.*?)</{re.escape(p)}cols>", xml, re.S)
    if not m:
        return xml  # no column definitions: every column has the default width
    col_re = re.compile(rf"<{re.escape(p)}col\b[^>]*?/>|<{re.escape(p)}col\b[^>]*?>.*?</{re.escape(p)}col>", re.S)
    cols = []
    for cm in col_re.finditer(m.group(1)):
        a = dict(_attrs(cm.group(0)[: cm.group(0).index(">")]))
        try:
            cols.append((int(a["min"]), int(a["max"]), cm.group(0)))
        except (KeyError, ValueError):
            return xml
    for src, dst in copies:
        if any(lo <= dst <= hi for lo, hi, _ in cols):
            continue
        template = next((x for lo, hi, x in cols if lo <= src <= hi), None)
        if template is None:
            continue
        new = re.sub(r'\bmin="\d+"', f'min="{dst}"', template, count=1)
        new = re.sub(r'\bmax="\d+"', f'max="{dst}"', new, count=1)
        cols.append((dst, dst, new))
    cols.sort(key=lambda c: c[0])
    inner = "".join(x for _, _, x in cols)
    return xml[: m.start(1)] + inner + xml[m.end(1):]


def _decode(data: bytes) -> str:
    head = data[:100]
    if head.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
        head = data[:100]
    enc = re.search(rb'encoding\s*=\s*["\']([^"\']+)["\']', head.split(b"?>")[0]) if head.startswith(b"<?xml") else None
    if enc and enc.group(1).lower().replace(b"-", b"") not in (b"utf8",):
        raise PackageEditError(f"worksheet encoded as {enc.group(1).decode()}")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise PackageEditError("worksheet is not UTF-8")


def write_cells(path: str, edits: Dict[str, SheetEdit]) -> None:
    """
    Apply `edits` ({sheet title: SheetEdit}) to the workbook at `path` in place. All edits are
    prepared before anything is written: on PackageEditError the file is unchanged.
    """
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise PackageEditError(f"not a zip package ({e})")
    with zf:
        parts = sheet_parts(zf)
        new_parts: Dict[str, bytes] = {}
        for title, edit in edits.items():
            if not edit.cells:
                continue
            part = parts.get(title)
            if part is None:
                raise PackageEditError(f"no worksheet part for sheet {title!r}")
            xml = _decode(zf.read(part))
            new_parts[part] = _edit_sheet_xml(xml, edit).encode("utf-8")
        if not new_parts:
            return
        infos = zf.infolist()
        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp = tempfile.mkstemp(prefix=".algebras-", suffix=".xlsx", dir=directory)
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp, "w") as out:
                for info in infos:
                    data = new_parts.get(info.filename)
                    if data is None:
                        data = zf.read(info)
                    out.writestr(info, data, compress_type=info.compress_type)
        except Exception:
            os.unlink(tmp)
            raise
    try:
        mode = os.stat(path).st_mode & 0o777
        os.chmod(tmp, mode)
    except OSError:
        pass
    os.replace(tmp, path)
