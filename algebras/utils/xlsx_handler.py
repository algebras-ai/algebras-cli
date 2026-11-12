"""
XLSX translation file handler for multi-language translations.

A translation workbook holds one or more translation sheets: row 1 has the key header and one
header per language, column A holds the keys. Every sheet with that layout is translated (see
_data_sheets); other sheets (notes, lookups) are left alone. A workbook with one translation sheet
uses the bare keys; with several, each key is "<sheet title>!<key>".

Reading uses openpyxl. Writing avoids an openpyxl load/save: the cells are written into the
package directly (algebras.utils.xlsx_package), so images, charts, shapes and every other part
stay as they are. Legacy .xls workbooks are read with xlrd when it is installed, and written to
the .xlsx next to them.
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from openpyxl import load_workbook, Workbook

import click


def read_xlsx_file(file_path: str, config=None) -> Dict[str, Any]:
    """
    Read an XLSX translation file and return its content as a dictionary.

    Args:
        file_path: Path to the XLSX (or .xls) file
        config: Optional Config; its languages tell which sheets are translation sheets

    Returns:
        {"key_column", "languages", "translations": {key: {language: text}}, "rich_text":
        {key: {language: text with <runN> tags}}}. "rich_text" holds the formatted cells only
        (see runs_to_tagged); "translations" always has the plain text.

    Raises:
        FileNotFoundError: If the file doesn't exist
        XlsNotSupportedError: For an .xls file when xlrd is not installed
        ValueError: If the file is not valid XLSX format
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"XLSX file not found: {file_path}")

    try:
        book = read_xlsx_book(file_path, config)
    except XlsNotSupportedError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to parse XLSX file {file_path}: {str(e)}")

    translations: Dict[str, Dict[str, str]] = {}
    rich: Dict[str, Dict[str, str]] = {}
    for key, cells in book.rows.items():
        lang_translations = {}
        for lang, cell in cells.items():
            value = cell.value.strip()
            if value:
                lang_translations[lang] = value
            if cell.tagged != cell.value:
                rich.setdefault(key, {})[lang] = cell.tagged.strip()
        if lang_translations:  # Only include keys with at least one translation
            translations[key] = lang_translations

    return {
        "key_column": book.key_column,
        "languages": list(book.languages),
        "translations": translations,
        "rich_text": rich,
    }


def write_xlsx_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write content to an XLSX translation file.
    
    Args:
        file_path: Path where to write the XLSX file
        content: Dictionary containing the XLSX content
        
    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("XLSX content must be a dictionary")
    
    if 'translations' not in content or 'languages' not in content:
        raise ValueError("XLSX content must contain 'translations' and 'languages' keys")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    key_column = content.get('key_column', 'key')
    languages = content['languages']
    translations = content['translations']
    
    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Translations"
    
    # Write header
    header_row = [key_column] + languages
    ws.append(header_row)
    
    # Write data rows
    for key, lang_translations in translations.items():
        if isinstance(lang_translations, dict):
            row = [key]
            for lang in languages:
                row.append(lang_translations.get(lang, ""))
            ws.append(row)

    # Translations are text: a value starting with "=" must never become a formula.
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    
    # Save the workbook
    wb.save(file_path)


def extract_translatable_strings(xlsx_content: Dict[str, Any], 
                               target_language: str) -> Dict[str, str]:
    """
    Extract translatable strings from XLSX content for a specific language.
    
    Args:
        xlsx_content: XLSX file content as dictionary
        target_language: Target language code
        
    Returns:
        Dictionary of key-value pairs for translatable strings
    """
    if 'translations' not in xlsx_content:
        return {}
    
    translatable = {}
    translations = xlsx_content['translations']
    
    for key, lang_translations in translations.items():
        if isinstance(lang_translations, dict) and target_language in lang_translations:
            translatable[key] = lang_translations[target_language]
    
    return translatable


def create_xlsx_from_translations(translations: Dict[str, str], 
                                languages: List[str],
                                key_column: str = "key") -> Dict[str, Any]:
    """
    Create XLSX content from translations.
    
    Args:
        translations: Dictionary of key-value translation pairs
        languages: List of language codes
        key_column: Name of the key column
        
    Returns:
        XLSX content dictionary
    """
    # For single language translations, we need to create a structure
    # that can be extended with more languages
    xlsx_translations = {}
    
    for key, value in translations.items():
        # Create a single-language translation structure
        lang_translations = {languages[0]: value} if languages else {}
        xlsx_translations[key] = lang_translations
    
    return {
        'key_column': key_column,
        'languages': languages,
        'translations': xlsx_translations
    }


def add_language_to_xlsx(xlsx_content: Dict[str, Any], 
                        language: str, 
                        translations: Dict[str, str]) -> Dict[str, Any]:
    """
    Add a new language to existing XLSX content.
    
    Args:
        xlsx_content: Existing XLSX content
        language: New language code to add
        translations: Translations for the new language
        
    Returns:
        Updated XLSX content dictionary
    """
    if 'translations' not in xlsx_content:
        xlsx_content['translations'] = {}
    
    if language not in xlsx_content['languages']:
        xlsx_content['languages'].append(language)
    
    for key, value in translations.items():
        if key not in xlsx_content['translations']:
            xlsx_content['translations'][key] = {}
        xlsx_content['translations'][key][language] = value
    
    return xlsx_content


def get_xlsx_language_codes(xlsx_content: Dict[str, Any]) -> List[str]:
    """
    Get all language codes from XLSX content.
    
    Args:
        xlsx_content: XLSX file content as dictionary
        
    Returns:
        List of language codes
    """
    return xlsx_content.get('languages', [])


def is_valid_xlsx_file(file_path: str) -> bool:
    """
    Check if a file is a valid XLSX translation file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file is a valid XLSX file, False otherwise
    """
    try:
        content = read_xlsx_file(file_path)
        return 'translations' in content and 'languages' in content
    except (FileNotFoundError, ValueError):
        return False


def get_xlsx_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from XLSX file path.
    
    Args:
        file_path: Path to the XLSX file
        
    Returns:
        Language code if found, None otherwise
    """
    # For XLSX files, we typically don't extract language from filename
    # since they contain multiple languages. Return None to indicate
    # this is a multi-language file.
    return None


def is_glossary_xlsx(file_path: str) -> bool:
    """
    Check if an XLSX file is a glossary file (vs translation file).
    
    Args:
        file_path: Path to the XLSX file
        
    Returns:
        True if the file appears to be a glossary file, False otherwise
    """
    try:
        if is_xls(file_path):
            wb = _load_xls(file_path)
        else:
            wb = load_workbook(filename=file_path, read_only=True, data_only=True)
        ws = wb.active
        
        if ws is None:
            wb.close()
            return False
        
        # Get first row
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        
        if not rows:
            return False
        
        headers = [_safe_cell_value(cell) for cell in rows[0]]
        
        # Glossary files typically have "Record ID" as first column
        # Translation files typically have "key" as first column
        if headers and len(headers) > 0:
            first_header = str(headers[0]).lower().strip()
            return first_header in ['record id', 'record_id', 'id']
    except Exception:
        pass
    
    return False


def _safe_cell_value(cell_value) -> str:
    """
    Convert a cell value to a safe string representation.
    
    Args:
        cell_value: The cell value to convert
        
    Returns:
        String representation of the cell value
    """
    if cell_value is None:
        return ""
    
    if isinstance(cell_value, bool):
        return "TRUE" if cell_value else "FALSE"
    
    if isinstance(cell_value, (int, float)):
        if isinstance(cell_value, float):
            if cell_value != cell_value:  # NaN check
                return ""
            if cell_value.is_integer():
                return str(int(cell_value))
        return str(cell_value)
    
    if isinstance(cell_value, str):
        return cell_value.strip()

    return str(cell_value)


# ---------------------------------------------------------------------------
# Legacy .xls workbooks
# ---------------------------------------------------------------------------
#
# openpyxl cannot read .xls (Excel 97-2003). With xlrd installed the workbook is read through it
# (values only), and since nothing here can write .xls, the translations go to the .xlsx next to
# it (strings.xls -> strings.xlsx). Without xlrd every read fails early with XlsNotSupportedError,
# which says what to do.


class XlsNotSupportedError(ValueError):
    """An .xls workbook was given and xlrd is not installed."""

    def __init__(self, file_path: str):
        super().__init__(
            f"{file_path} is an Excel 97-2003 workbook (.xls), which openpyxl cannot read. "
            "Either install xlrd (pip install xlrd) so the CLI can read it and write the "
            "translations to an .xlsx next to it, or open it in Excel/LibreOffice, save it as "
            ".xlsx and point the config at the .xlsx file."
        )


def is_xls(file_path: Optional[str]) -> bool:
    return bool(file_path) and str(file_path).lower().endswith(".xls")


def xlsx_output_path(file_path: str) -> str:
    """Where a workbook is written: the path itself, or the .xlsx next to an .xls."""
    if is_xls(file_path):
        return file_path[:-4] + ".xlsx"
    return file_path


def _import_xlrd():
    try:
        import xlrd  # optional dependency
    except ImportError:
        return None
    return xlrd


def require_xls_support(file_path: str) -> None:
    """Raise XlsNotSupportedError for an .xls path when xlrd is missing; no-op otherwise."""
    if is_xls(file_path) and _import_xlrd() is None:
        raise XlsNotSupportedError(file_path)


def _load_xls(file_path: str) -> Workbook:
    """An .xls workbook as an in-memory openpyxl Workbook (values only)."""
    xlrd = _import_xlrd()
    if xlrd is None:
        raise XlsNotSupportedError(file_path)
    book = xlrd.open_workbook(file_path)
    wb = Workbook()
    wb.remove(wb.active)
    for sheet in book.sheets():
        ws = wb.create_sheet(str(sheet.name))
        for r in range(sheet.nrows):
            for c, value in enumerate(sheet.row_values(r)):
                if value is None or value == "":
                    continue
                cell = ws.cell(row=r + 1, column=c + 1, value=value)
                if isinstance(value, str):
                    cell.data_type = "s"
    if not wb.worksheets:
        wb.create_sheet("Sheet1")
    wb.active = 0
    return wb


def convert_xls_to_xlsx(xls_path: str, xlsx_path: str) -> None:
    """Save an .xls workbook as .xlsx (values only)."""
    wb = _load_xls(xls_path)
    os.makedirs(os.path.dirname(os.path.abspath(xlsx_path)), exist_ok=True)
    wb.save(xlsx_path)


def _open_workbook(file_path: str):
    """The workbook for reading: values (not formulas), with rich-text runs."""
    if is_xls(file_path):
        return _load_xls(file_path)
    try:
        return load_workbook(filename=file_path, data_only=True, rich_text=True)
    except TypeError:  # openpyxl < 3.1 has no rich text support
        return load_workbook(filename=file_path, data_only=True)


# ---------------------------------------------------------------------------
# Rich text: formatting runs as paired tags
# ---------------------------------------------------------------------------
#
# A rich-text cell is a list of runs, each with its own font. A translation cannot keep run
# boundaries by position (words move), so a formatted source cell is sent to the model with each
# formatted run wrapped in a paired tag, <run1>…</run1>, numbered by its run index. The tags are
# markup placeholders (xml_tag syntax, detected from the tagged source column by resolve_profile):
# the placeholder engine masks them, the model keeps them paired around the translated span, and
# the write gate checks them. When the translation is written, each tagged span gets the font of
# its source run (tagged_to_rich). If the tags cannot be mapped back (unbalanced, an unknown run,
# or no tags at all), the whole cell takes the formatting of the source cell's first run.

RUN_TAG_RE = re.compile(r"<(/?)run(\d+)>")


def _runs(rich) -> List[Tuple[str, object]]:
    """[(text, font or None)] of a CellRichText."""
    out = []
    for run in rich:
        if isinstance(run, str):
            out.append((run, None))
        else:
            out.append((run.text or "", run.font))
    return out


def runs_to_tagged(rich) -> Optional[str]:
    """
    The text of a rich-text cell with each formatted run in <runN>…</runN> (N = run index, from
    1), or None when tags are not needed (fewer than two runs) or would be ambiguous (the text
    already contains such a tag).
    """
    if rich is None:
        return None
    runs = _runs(rich)
    if len(runs) < 2 or any(RUN_TAG_RE.search(text) for text, _ in runs):
        return None
    parts = []
    tagged = False
    for index, (text, font) in enumerate(runs, start=1):
        if font is not None and text.strip():
            parts.append(f"<run{index}>{text}</run{index}>")
            tagged = True
        else:
            parts.append(text)
    return "".join(parts) if tagged else None


def has_run_tags(text: str) -> bool:
    return isinstance(text, str) and RUN_TAG_RE.search(text) is not None


def strip_run_tags(text: str) -> str:
    return RUN_TAG_RE.sub("", text)


def tagged_to_rich(text: str, source_rich):
    """
    A CellRichText from a translation with <runN> tags, each tagged span taking the font of run N
    of `source_rich`; None when the text has no tags or they cannot be mapped (unbalanced or an
    unknown run).
    """
    from openpyxl.cell.rich_text import CellRichText, TextBlock

    if not has_run_tags(text) or source_rich is None:
        return None
    runs = _runs(source_rich)
    stack: List[int] = []
    segments: List[Tuple[str, Optional[int]]] = []
    pos = 0
    for m in RUN_TAG_RE.finditer(text):
        if m.start() > pos:
            segments.append((text[pos:m.start()], stack[-1] if stack else None))
        pos = m.end()
        index = int(m.group(2))
        if not 1 <= index <= len(runs) or runs[index - 1][1] is None:
            return None
        if m.group(1):  # closing tag
            if not stack or stack[-1] != index:
                return None
            stack.pop()
        else:
            stack.append(index)
    if stack:
        return None
    if pos < len(text):
        segments.append((text[pos:], None))

    out: List[Tuple[str, Optional[int]]] = []
    for segment, index in segments:
        if not segment:
            continue
        if out and out[-1][1] == index:
            out[-1] = (out[-1][0] + segment, index)
        else:
            out.append((segment, index))
    if not out:
        return None
    return CellRichText([s if i is None else TextBlock(runs[i - 1][1], s) for s, i in out])


def first_run_formatting(text: str, source_rich):
    """`text` with the font of the first run of `source_rich` (plain text when it has none)."""
    from openpyxl.cell.rich_text import CellRichText, TextBlock

    runs = _runs(source_rich) if source_rich is not None else []
    font = runs[0][1] if runs else None
    if font is None or not text:
        return text
    return CellRichText([TextBlock(font, text)])


# ---------------------------------------------------------------------------
# Cell-level access: data sheets, cells with their coordinates
# ---------------------------------------------------------------------------


def _quote_title(title: str) -> str:
    if not title.replace("_", "").isalnum():
        return "'" + title.replace("'", "''") + "'"
    return title


class XlsxCell:
    """
    A translation cell: its coordinate (e.g. "D14"), its text, its sheet and, for a rich-text cell,
    its runs (a CellRichText).
    """

    __slots__ = ("coordinate", "value", "sheet", "rich")

    def __init__(self, coordinate: str, value: str, sheet: str = "", rich=None):
        self.coordinate = coordinate
        self.value = value
        self.sheet = sheet
        self.rich = rich

    @property
    def ref(self) -> str:
        """Excel reference such as Sheet1!D14."""
        return f"{_quote_title(self.sheet)}!{self.coordinate}" if self.sheet else self.coordinate

    @property
    def tagged(self) -> str:
        """The text with <runN> tags around formatted runs (the plain text when there are none)."""
        return runs_to_tagged(self.rich) or self.value

    def __repr__(self) -> str:
        return f"XlsxCell({self.coordinate!r}, {self.value!r})"


class XlsxSheet:
    """A translation sheet of a workbook: rows[key][language column] -> XlsxCell."""

    def __init__(
        self,
        title: str,
        key_column: str,
        languages: List[str],
        rows: Dict[str, Dict[str, XlsxCell]],
        row_of: Optional[Dict[str, int]] = None,
        letters: Optional[Dict[str, str]] = None,
        max_row: int = 0,
        max_column: int = 0,
    ):
        self.title = title
        self.key_column = key_column
        self.languages = languages
        self.rows = rows
        self.row_of = row_of or {}  # key -> row number
        self.letters = letters or {}  # language column -> column letter
        self.max_row = max_row
        self.max_column = max_column

    def ref(self, coordinate: str) -> str:
        """Excel reference such as Sheet1!D14 ('My sheet'!D14 when the title needs quotes)."""
        return f"{_quote_title(self.title)}!{coordinate}"

    def coordinate(self, key: str, language: str) -> Optional[str]:
        """Coordinate of a key's cell in a language column, also when the cell is empty."""
        if key not in self.row_of or language not in self.letters:
            return None
        return f"{self.letters[language]}{self.row_of[key]}"

    def column(self, language: str) -> Dict[str, XlsxCell]:
        """{key: cell} for one language column (empty cells left out)."""
        return {key: cells[language] for key, cells in self.rows.items() if language in cells}


class XlsxBook:
    """
    The translation sheets of a workbook. With one sheet the keys are the sheet's keys (as before
    multi-sheet support); with several, each key is "<sheet title>!<key>", so keys of different
    sheets never collide and every key says where it lives.
    """

    def __init__(self, sheets: List[XlsxSheet], primary: XlsxSheet):
        self.sheets = sheets
        self.primary = primary
        self.multi = len(sheets) > 1
        self.key_column = primary.key_column
        languages: List[str] = []
        for sheet in [primary] + [s for s in sheets if s is not primary]:
            for lang in sheet.languages:
                if lang not in languages:
                    languages.append(lang)
        self.languages = languages
        self._where: Dict[str, Tuple[XlsxSheet, str]] = {}
        self.rows: Dict[str, Dict[str, XlsxCell]] = {}
        for sheet in sheets:
            for key in sheet.row_of:
                full = self.key(sheet, key)
                self._where[full] = (sheet, key)
                self.rows[full] = sheet.rows.get(key, {})

    @property
    def title(self) -> str:
        return self.primary.title

    def key(self, sheet: XlsxSheet, key: str) -> str:
        return f"{sheet.title}!{key}" if self.multi else key

    def locate(self, key: str, create: bool = False) -> Optional[Tuple[XlsxSheet, str]]:
        """(sheet, key in that sheet) of a key; with `create`, also of a key not in the workbook yet."""
        if key in self._where:
            return self._where[key]
        if not create:
            return None
        if not self.multi:
            return self.primary, key
        for sheet in sorted(self.sheets, key=lambda s: -len(s.title)):
            prefix = f"{sheet.title}!"
            if key.startswith(prefix) and len(key) > len(prefix):
                return sheet, key[len(prefix):]
        return None

    def column(self, language: str) -> Dict[str, XlsxCell]:
        """{key: cell} for one language column across the sheets (empty cells left out)."""
        out: Dict[str, XlsxCell] = {}
        for sheet in self.sheets:
            for key, cell in sheet.column(language).items():
                out[self.key(sheet, key)] = cell
        return out

    def coordinate(self, key: str, language: str) -> Optional[str]:
        where = self.locate(key)
        return where[0].coordinate(where[1], language) if where else None

    def ref(self, key: str, language: str) -> Optional[str]:
        """Sheet!Cell of a key's cell in a language column (also when the cell is empty)."""
        where = self.locate(key)
        if not where:
            return None
        coordinate = where[0].coordinate(where[1], language)
        return where[0].ref(coordinate) if coordinate else None


def _is_rich_text(value) -> bool:
    return type(value).__name__ == "CellRichText"


def _cell_text(value) -> str:
    """Cell value as text, without stripping (rich text is joined into one string)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if _is_rich_text(value):
        return str(value)
    return _safe_cell_value(value)


def _header(ws) -> List[str]:
    for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        return [_safe_cell_value(_cell_text(v)) for v in row]
    return []


def _has_layout(headers: List[str]) -> bool:
    return len(headers) >= 2 and bool(headers[0]) and any(headers[1:])


def _configured_columns(config) -> Optional[set]:
    """Language column names the config knows (codes and mapped names), or None without a config."""
    if config is None:
        return None
    try:
        languages = config.get_languages()
    except Exception:
        return None
    if not isinstance(languages, (list, tuple)):
        return None
    names = set()
    for lang in languages:
        if not isinstance(lang, str):
            continue
        names.add(lang)
        try:
            mapped = config.get_destination_locale_code(lang)
        except Exception:
            mapped = None
        if isinstance(mapped, str) and mapped:
            names.add(mapped)
    return names or None


def _data_sheets(wb, config=None):
    """
    (data sheets in workbook order, primary sheet). The primary sheet is the active sheet when it
    has a key + language header row (else the first sheet that has one); it is always a data sheet,
    as before multi-sheet support. Another sheet is a data sheet when its header row has a key and
    at least one language column that the config lists (without a config: one that the primary
    sheet has). A notes sheet, a lookup table or an empty sheet is not.
    """
    sheets = list(wb.worksheets)
    headers = {id(ws): _header(ws) for ws in sheets}
    active = wb.active if wb.active in sheets else None
    primary = active if active is not None and _has_layout(headers[id(active)]) else None
    if primary is None:
        primary = next((ws for ws in sheets if _has_layout(headers[id(ws)])), None)
    if primary is None:
        return [], None
    known = _configured_columns(config) or {h for h in headers[id(primary)][1:] if h}
    data = [
        ws
        for ws in sheets
        if ws is primary
        or (_has_layout(headers[id(ws)]) and any(h in known for h in headers[id(ws)][1:] if h))
    ]
    return data, primary


def _read_sheet(ws, headers: List[str]) -> XlsxSheet:
    from openpyxl.utils import get_column_letter

    title = ws.title
    rows: Dict[str, Dict[str, XlsxCell]] = {}
    row_of: Dict[str, int] = {}
    letters: Dict[str, str] = {}
    for i, h in enumerate(headers, start=1):
        if h and i > 1 and h not in letters:
            letters[h] = get_column_letter(i)
    for row_index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row:
            continue
        key = _safe_cell_value(_cell_text(row[0]))
        if not key:
            continue
        if key in rows:
            continue  # duplicate key: the first row is the one update_xlsx_cells writes
        cells = rows[key] = {}
        row_of[key] = row_index
        for col_index, language in enumerate(headers[1:], start=2):
            if not language or col_index > len(row) or letters.get(language) != get_column_letter(col_index):
                continue
            value = row[col_index - 1]
            text = _cell_text(value)
            if text.strip():
                rich = value if _is_rich_text(value) else None
                cells[language] = XlsxCell(f"{get_column_letter(col_index)}{row_index}", text, title, rich)
    max_column = max((i for i, h in enumerate(headers, start=1) if h), default=1)
    return XlsxSheet(
        title,
        headers[0] if headers else "key",
        list(letters),
        rows,
        row_of,
        letters,
        max_row=max(ws.max_row or 1, 1),
        max_column=max(max_column, ws.max_column or 1),
    )


def read_xlsx_book(file_path: str, config=None) -> XlsxBook:
    """
    The translation sheets of a workbook (see _data_sheets) with each cell's coordinate. Keys and
    headers are stripped as in read_xlsx_file; values are kept exactly as stored (whitespace-only
    values are left out).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"XLSX file not found: {file_path}")
    wb = _open_workbook(file_path)
    try:
        data, primary = _data_sheets(wb, config)
        if primary is None:
            if not any(any(_header(ws)) for ws in wb.worksheets):
                raise ValueError(f"XLSX file {file_path} is empty")
            raise ValueError(
                f"XLSX file {file_path} must have at least 2 columns (key and at least one language)"
            )
        sheets = []
        primary_sheet = None
        for ws in data:
            sheet = _read_sheet(ws, _header(ws))
            sheets.append(sheet)
            if ws is primary:
                primary_sheet = sheet
    finally:
        try:
            wb.close()
        except Exception:
            pass
    return XlsxBook(sheets, primary_sheet)


def read_xlsx_cells(file_path: str, config=None) -> XlsxSheet:
    """The primary translation sheet with each cell's coordinate (read_xlsx_book has them all)."""
    return read_xlsx_book(file_path, config).primary


# ---------------------------------------------------------------------------
# Writing cells
# ---------------------------------------------------------------------------


def _load_for_edit(file_path: str):
    """Workbook opened for editing; rich-text runs are loaded so that saving keeps them."""
    try:
        return load_workbook(filename=file_path, rich_text=True)
    except TypeError:  # openpyxl < 3.1 has no rich text support
        return load_workbook(filename=file_path)


def _runs_with_edit(rich, new_text: str):
    """
    `rich` (a CellRichText) with its text changed to `new_text`, keeping the runs, or None when a
    change crosses a run boundary (then the run structure cannot be kept).
    """
    from difflib import SequenceMatcher

    from openpyxl.cell.rich_text import CellRichText, TextBlock

    runs = list(rich)
    texts = [r if isinstance(r, str) else r.text for r in runs]
    starts = []
    pos = 0
    for t in texts:
        starts.append(pos)
        pos += len(t)
    old_text = "".join(texts)

    def run_of(i1: int, i2: int) -> Optional[int]:
        for idx, (start, t) in enumerate(zip(starts, texts)):
            end = start + len(t)
            if i1 == i2:  # insertion: goes to the run it follows (or the first run)
                if start < i1 <= end or (i1 == 0 and idx == 0):
                    return idx
            elif start <= i1 and i2 <= end:
                return idx
        return None

    new_texts = list(texts)
    opcodes = SequenceMatcher(None, old_text, new_text, autojunk=False).get_opcodes()
    kept = sum(i2 - i1 for tag, i1, i2, _, _ in opcodes if tag == "equal")
    if kept * 2 < len(old_text):
        return None  # mostly new text (a translation, not a repair): the runs no longer apply
    for tag, i1, i2, j1, j2 in reversed(opcodes):
        if tag == "equal":
            continue
        idx = run_of(i1, i2)
        if idx is None:
            return None
        local1, local2 = i1 - starts[idx], i2 - starts[idx]
        new_texts[idx] = new_texts[idx][:local1] + new_text[j1:j2] + new_texts[idx][local2:]
    out = []
    for run, text in zip(runs, new_texts):
        out.append(text if isinstance(run, str) else TextBlock(run.font, text))
    return CellRichText(out)


def set_cell_text(cell, text: str, keep_runs: bool = False) -> bool:
    """
    Write `text` to an openpyxl `cell` as an explicit string, so that "=…", "+…", "-…" or "@…"
    never turns into a formula. The cell's style stays. With `keep_runs`, a rich-text cell keeps
    its runs when the change fits inside them (e.g. a repaired placeholder). Returns False when a
    rich-text cell was written as plain text (its runs were dropped).
    """
    old = cell.value
    if _is_rich_text(old) and text:
        edited = _runs_with_edit(old, text) if keep_runs else None
        if edited is not None:
            cell.value = edited
            return True
        cell.value = text
        cell.data_type = "s"
        return False
    cell.value = text if text else None
    if text:
        cell.data_type = "s"
    return True


def _cell_value(text: str, current_rich, keep_runs: bool, source_rich) -> Tuple[object, bool]:
    """
    (value to write, rich-text formatting dropped?). A translation of a formatted source cell gets
    the source's runs (tagged_to_rich, else the first run's formatting); a repair of a formatted
    target cell keeps its runs when it fits inside them (keep_runs).
    """
    if not text:
        return "", False
    if source_rich is not None:
        rich = tagged_to_rich(text, source_rich)
        if rich is not None:
            return rich, False
        return first_run_formatting(strip_run_tags(text), source_rich), False
    if current_rich is not None:
        if keep_runs:
            edited = _runs_with_edit(current_rich, text)
            if edited is not None:
                return edited, False
        return text, True
    return text, False


def _writable_path(file_path: str) -> str:
    out = xlsx_output_path(file_path)
    if out != file_path:
        click.echo(
            f"  {click.style('ℹ', fg='blue')} {os.path.basename(file_path)} is an Excel 97-2003 "
            f"workbook (.xls), which cannot be written; the translations are saved to "
            f"{os.path.basename(out)} next to it."
        )
    return out


def _create_target(file_path: str, template_file: Optional[str], language: str) -> None:
    import shutil

    same = template_file and os.path.abspath(template_file) == os.path.abspath(file_path)
    if template_file and os.path.exists(template_file) and not same:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        if is_xls(template_file):
            convert_xls_to_xlsx(template_file, file_path)
            click.echo(
                f"  {click.style('ℹ', fg='blue')} Created {os.path.basename(file_path)} from "
                f"{os.path.basename(template_file)} (converted from .xls)."
            )
        else:
            shutil.copyfile(template_file, file_path)
    else:
        write_xlsx_file(file_path, {"key_column": "key", "languages": [language], "translations": {}})


def _write_with_openpyxl(file_path: str, edits) -> None:
    """The fallback writer: an openpyxl load/save (drops what openpyxl does not model)."""
    from copy import copy

    from openpyxl.utils import get_column_letter

    wb = _load_for_edit(file_path)
    for title, edit in edits.items():
        ws = wb[title]
        for coordinate, value in edit.cells.items():
            cell = ws[coordinate]
            source = edit.style_from.get(coordinate)
            if source and ws[source].has_style and not cell.has_style:
                cell._style = copy(ws[source]._style)
            if isinstance(value, str):
                cell.value = value if value else None
                if value:
                    cell.data_type = "s"
            else:
                cell.value = value
        for src, dst in edit.copy_columns:
            width = ws.column_dimensions[get_column_letter(src)].width
            if width and not ws.column_dimensions[get_column_letter(dst)].width:
                ws.column_dimensions[get_column_letter(dst)].width = width
    wb.save(file_path)


def update_xlsx_cells(
    file_path: str,
    language: str,
    values: Dict[str, str],
    template_file: Optional[str] = None,
    add_missing: bool = True,
    keep_runs: bool = False,
    force: bool = False,
    rich_sources: Optional[Dict[str, Any]] = None,
    config=None,
) -> Dict[str, Any]:
    """
    Write `values` ({key: text}) to the `language` column of the workbook. Only those cells change.

    The cells are written into the package directly (xlsx_package.write_cells): every other part
    (images, charts, shapes, styles, other sheets) stays byte-identical, and a written cell keeps
    its style. A missing target file is created as a copy of `template_file` (the source workbook;
    an .xls source is converted) when given. A missing language column is added after the last
    column, with the header style and width of the column before it. Keys of a multi-sheet
    workbook are "<sheet>!<key>" (see XlsxBook). An .xls target is written to the .xlsx next to it.

    Formatting: `rich_sources` ({key: CellRichText of the source cell}) gives a translation the
    source's runs (tags, else the first run's formatting); with `keep_runs`, a rich-text target
    cell keeps its runs where a change fits inside them (repaired placeholders).

    When the package cannot be edited directly (PackageEditError), the workbook is saved through
    openpyxl, unless that would drop images, charts or other parts openpyxl does not keep: then
    nothing is written and a warning names what would be lost, unless `force` is set.

    Returns {"written": [Sheet!Cell], "missing": [keys not found], "runs_dropped": [Sheet!Cell of
    rich-text cells written as plain text], "skipped": [Sheet!Cell not written], "path": file}.
    """
    from openpyxl.utils import get_column_letter

    from algebras.utils.xlsx_package import PackageEditError, SheetEdit, openpyxl_losses, write_cells

    original = file_path
    file_path = _writable_path(file_path)
    report: Dict[str, Any] = {"written": [], "missing": [], "runs_dropped": [], "skipped": [], "path": file_path}
    if not os.path.exists(file_path):
        if template_file is None and original != file_path and os.path.exists(original):
            template_file = original
        _create_target(file_path, template_file, language)
    if not values:
        return report

    book = read_xlsx_book(file_path, config)
    rich_sources = rich_sources or {}
    edits: Dict[str, SheetEdit] = {}
    next_row = {sheet.title: sheet.max_row + 1 for sheet in book.sheets}

    for key, text in values.items():
        where = book.locate(key, create=add_missing)
        if where is None:
            report["missing"].append(key)
            continue
        sheet, raw_key = where
        edit = edits.setdefault(sheet.title, SheetEdit())
        letter = sheet.letters.get(language)
        if letter is None:
            column = sheet.max_column + 1
            letter = get_column_letter(column)
            sheet.letters[language] = letter
            sheet.max_column = column
            edit.cells[f"{letter}1"] = language
            if column > 1:
                edit.style_from[f"{letter}1"] = f"{get_column_letter(column - 1)}1"
                edit.copy_columns.append((column - 1, column))
        row = sheet.row_of.get(raw_key)
        if row is None:
            if not add_missing:
                report["missing"].append(key)
                continue
            row = next_row[sheet.title]
            next_row[sheet.title] += 1
            sheet.row_of[raw_key] = row
            edit.cells[f"A{row}"] = raw_key
        coordinate = f"{letter}{row}"
        current = sheet.rows.get(raw_key, {}).get(language)
        value, dropped = _cell_value(text, current.rich if current else None, keep_runs, rich_sources.get(key))
        edit.cells[coordinate] = value
        report["written"].append(sheet.ref(coordinate))
        if dropped:
            report["runs_dropped"].append(sheet.ref(coordinate))

    if not edits:
        return report
    try:
        write_cells(file_path, edits)
    except PackageEditError as e:
        lost = openpyxl_losses(file_path)
        name = os.path.basename(file_path)
        warn = click.style("⚠", fg="yellow")
        if lost and not force:
            click.echo(
                f"  {warn} {name}: the cells cannot be written directly into the workbook ({e}), and "
                f"saving it through openpyxl would remove its {', '.join(lost)}. Nothing was written. "
                "Run 'algebras translate --regenerate-from-scratch' to write anyway (those parts "
                "will be lost), or remove them from the workbook first."
            )
            report["skipped"] = report["written"]
            report["written"] = []
            report["runs_dropped"] = []
            return report
        if lost:
            click.echo(f"  {warn} {name}: saved through openpyxl ({e}); its {', '.join(lost)} were removed.")
        _write_with_openpyxl(file_path, edits)
    return report
