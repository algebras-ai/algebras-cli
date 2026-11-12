"""
XLSX fidelity: writes go into the workbook package directly, so images, charts and every other
part survive translation writes and `algebras placeholders --fix`; rich-text runs are translated as
paired tags; every translation sheet is translated (notes sheets are not); .xls is read through
xlrd or rejected with an actionable error; `status` counts XLSX per language column.

No API calls: the API is patched as in tests/test_xlsx_placeholders.py.
"""

import json
import os
import re
import struct
import sys
import types
import zipfile
import zlib

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.chart import BarChart, Reference
from openpyxl.drawing.image import Image
from openpyxl.styles import Font

from algebras.commands import placeholders_command, status_command
from algebras.commands.translate_command import _write_translated_content
from algebras.services.strategies.strategy_factory import TranslationStrategyFactory
from algebras.utils.file_format_detector import FileFormat, detect_format
from algebras.utils.file_format_handlers import XLSXHandler, get_handler
from algebras.utils.lang_validator import read_language_file
from algebras.utils.xlsx_handler import (
    XlsNotSupportedError,
    read_xlsx_book,
    read_xlsx_file,
    runs_to_tagged,
    tagged_to_rich,
    update_xlsx_cells,
)
from algebras.utils.xlsx_package import openpyxl_losses

from tests.test_placeholders_translation import transliterate
from tests.test_xlsx_placeholders import (
    DAMAGED_RU,
    RICH_RU,
    _assert_cells_kept,
    _translate_missing,
    _translator,
    make_workbook,
    snapshot,
)

MEDIA_PREFIXES = ("xl/media/", "xl/charts/", "xl/drawings/")


# --- workbook helpers -----------------------------------------------------------------------


def tiny_png() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
        + chunk(b"IEND", b"")
    )


class PngImage(Image):
    """openpyxl's Image with its bytes given directly (no Pillow needed in the test environment)."""

    def __init__(self, data: bytes, anchor: str = "F2"):
        self.ref = None
        self._png = data
        self.width = self.height = 1
        self.format = "png"
        self.anchor = anchor

    def _data(self):
        return self._png


def add_media(path):
    """Add a tiny PNG and a bar chart to the first sheet (saved through openpyxl, once)."""
    wb = load_workbook(path, rich_text=True)
    ws = wb.worksheets[0]
    ws.add_image(PngImage(tiny_png()))
    chart = BarChart()
    chart.title = "Lengths"
    chart.add_data(Reference(ws, min_col=1, min_row=1, max_row=4))
    ws.add_chart(chart, "H2")
    wb.save(path)
    return path


def parts(path):
    with zipfile.ZipFile(path) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def media_parts(path):
    return {n: d for n, d in parts(path).items() if n.startswith(MEDIA_PREFIXES)}


def sheet_part(path, title):
    from algebras.utils.xlsx_package import sheet_parts

    with zipfile.ZipFile(path) as zf:
        return sheet_parts(zf)[title]


def assert_only_sheet_changed(before, after, changed_parts):
    assert list(after) == list(before)  # same parts, same order
    for name, data in before.items():
        if name not in changed_parts:
            assert after[name] == data, name


# --- images and charts ------------------------------------------------------------------------


def test_translate_write_keeps_images_and_charts(tmp_path, monkeypatch):
    path = add_media(make_workbook(str(tmp_path / "strings.xlsx")))
    media = media_parts(path)
    assert any(n.startswith("xl/media/") for n in media) and any(n.startswith("xl/charts/") for n in media)
    before_parts, before = parts(path), snapshot(path)

    _translate_missing(path, monkeypatch, transliterate)

    after_parts = parts(path)
    assert media_parts(path) == media  # drawing, chart and image parts are byte-identical
    assert_only_sheet_changed(before_parts, after_parts, {sheet_part(path, "Strings")})
    _assert_cells_kept(before, snapshot(path), {("Strings", f"C{r}") for r in range(2, 8)})
    ws = load_workbook(path).active
    assert ws["C2"].value == "Hелло %1$s, йоу hаве %2$d мессаgес"
    assert "<drawing" in after_parts[sheet_part(path, "Strings")].decode()


def test_full_file_translation_keeps_images_and_charts(tmp_path, monkeypatch):
    path = add_media(make_workbook(str(tmp_path / "strings.xlsx")))
    target = str(tmp_path / "strings.ru.xlsx")
    media = media_parts(path)
    translator, _ = _translator(monkeypatch, transliterate)
    content = translator.translate_file(path, "ru")
    _write_translated_content(target, content, get_handler(path, translator.config), set(), False,
                              source_file=path, source_language="en", target_language="ru")
    assert media_parts(target) == media
    assert load_workbook(target).active["C6"].value == "Pлаин техт"


@pytest.fixture
def media_project(tmp_path, monkeypatch):
    path = make_workbook(str(tmp_path / "strings.xlsx"), ru=DAMAGED_RU, rich_ru=CellRichText(list(RICH_RU)))
    add_media(path)
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {"strings.xlsx": {"destination_path": "strings.xlsx"}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return path


def test_fix_keeps_images_charts_and_rich_runs(media_project, capsys):
    media = media_parts(media_project)
    before_parts, before = parts(media_project), snapshot(media_project)
    assert placeholders_command.execute(fix=True, output_format="json") == 0

    assert media_parts(media_project) == media
    assert_only_sheet_changed(before_parts, parts(media_project), {sheet_part(media_project, "Strings")})
    _assert_cells_kept(before, snapshot(media_project), {("Strings", "C2"), ("Strings", "C4"), ("Strings", "C7")})
    ws = load_workbook(media_project, rich_text=True).active
    assert ws["C2"].value == "Привет %1$s, у вас %2$d сообщений"
    assert ws["C4"].value == "=Итого: {0} шт." and ws["C4"].data_type == "s"
    assert isinstance(ws["C7"].value, CellRichText) and ws["C7"].value[0].font.b
    assert str(ws["C7"].value) == "Жирный отправлено %1$s"


def test_unsupported_package_with_images_is_not_written_unless_forced(tmp_path, capsys):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    wb = load_workbook(path)
    wb.active["C6"] = "=1+1"  # a formula in a target cell: the package writer refuses it
    wb.save(path)
    add_media(path)
    before = parts(path)
    assert openpyxl_losses(path) == ["images", "charts", "drawings and shapes"]

    report = update_xlsx_cells(path, "ru", {"plain": "Текст"})
    out = capsys.readouterr().out
    assert report["written"] == [] and report["skipped"] == ["Strings!C6"]
    assert "holds a formula" in out and "images, charts" in out and "--regenerate-from-scratch" in out
    assert parts(path) == before

    report = update_xlsx_cells(path, "ru", {"plain": "Текст"}, force=True)
    assert report["written"] == ["Strings!C6"]
    assert "were removed" in capsys.readouterr().out
    assert load_workbook(path).active["C6"].value == "Текст"


def test_unsupported_package_without_images_falls_back_to_openpyxl(tmp_path, capsys):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    wb = load_workbook(path)
    wb.active["C6"] = "=1+1"
    wb.save(path)
    report = update_xlsx_cells(path, "ru", {"plain": "Текст"})
    assert report["written"] == ["Strings!C6"] and capsys.readouterr().out == ""
    assert load_workbook(path).active["C6"].value == "Текст"


# --- the package writer -------------------------------------------------------------------------


def test_new_cells_rows_and_columns_are_inserted_in_order(tmp_path):
    path = str(tmp_path / "strings.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "Strings"
    ws.append(["key", "en", "ru"])
    ws["A1"].font = ws["B1"].font = ws["C1"].font = Font(bold=True)
    ws["A2"], ws["B2"] = "a", "Alpha"
    ws["A3"], ws["B3"] = "b", "Beta"
    ws["C3"] = "Бета"
    ws["C3"].font = Font(italic=True)
    ws["A5"], ws["B5"] = "c", "Gamma"  # row 4 does not exist
    ws.column_dimensions["C"].width = 33
    wb.save(path)
    before = snapshot(path)

    report = update_xlsx_cells(path, "ru", {"a": "Альфа", "b": "Бета!", "new": "Новый"})
    assert report["written"] == ["Strings!C2", "Strings!C3", "Strings!C6"]
    update_xlsx_cells(path, "de", {"c": "Gamma de"})

    ws = load_workbook(path).active
    assert [c.value for c in ws[2]][:3] == ["a", "Alpha", "Альфа"]
    assert ws["C3"].value == "Бета!" and ws["C3"].font.i  # existing cell keeps its style
    assert ws["A6"].value == "new" and ws["C6"].value == "Новый"
    assert ws["D1"].value == "de" and ws["D1"].font.b and ws["D5"].value == "Gamma de"
    assert ws.column_dimensions["D"].width == 33
    cells_before, widths_before = before
    cells_after, widths_after = snapshot(path)
    assert widths_after == {**widths_before, ("Strings", "D"): 33}
    for ref, cell in cells_before.items():
        if ref in {("Strings", "C2"), ("Strings", "C3")}:
            assert cells_after[ref][2] == cell[2]  # written cells keep their style
        else:
            assert cells_after[ref] == cell, ref

    xml =parts(path)[sheet_part(path, "Strings")].decode()
    rows = [int(r) for r in re.findall(r'<row r="(\d+)"', xml)]
    assert rows == sorted(rows) and 4 not in rows
    for row in re.findall(r"<row [^>]*>(.*?)</row>", xml):
        refs = re.findall(r'<c r="([A-Z]+)\d+"', row)
        assert refs == sorted(refs, key=lambda c: (len(c), c))  # column order within each row
    assert re.search(r'<dimension ref="A1:D6"', xml)
    assert read_xlsx_book(path).primary.max_row == 6  # read-back sees every row


# --- rich text ----------------------------------------------------------------------------------

RICH_SOURCE = CellRichText(["Click ", TextBlock(InlineFont(b=True), "Save"), " to keep ", TextBlock(InlineFont(i=True), "%1$s")])


def test_runs_become_paired_tags_and_back():
    tagged = runs_to_tagged(RICH_SOURCE)
    assert tagged == "Click <run2>Save</run2> to keep <run4>%1$s</run4>"
    rich = tagged_to_rich("<run4>%1$s</run4> сохранится, нажмите <run2>Сохранить</run2>", RICH_SOURCE)
    assert [getattr(r, "text", r) for r in rich] == ["%1$s", " сохранится, нажмите ", "Сохранить"]
    assert rich[0].font.i and rich[2].font.b and isinstance(rich[1], str)
    assert tagged_to_rich("<run2>broken", RICH_SOURCE) is None  # unbalanced
    assert tagged_to_rich("<run1>x</run1>", RICH_SOURCE) is None  # run 1 has no formatting
    assert tagged_to_rich("no tags", RICH_SOURCE) is None
    assert runs_to_tagged(CellRichText([TextBlock(InlineFont(b=True), "one run")])) is None


def _rich_workbook(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Strings"
    ws.append(["key", "en", "ru"])
    ws.append(["save", None, None])
    ws["B2"].value = CellRichText(list(RICH_SOURCE))
    ws.append(["plain", "Plain text", None])
    wb.save(path)
    return path


def test_rich_text_strategy_keeps_formatted_spans(tmp_path, monkeypatch):
    path = _rich_workbook(str(tmp_path / "strings.xlsx"))
    content = read_xlsx_file(path)
    assert content["rich_text"] == {"save": {"en": "Click <run2>Save</run2> to keep <run4>%1$s</run4>"}}
    assert content["translations"]["save"]["en"] == "Click Save to keep %1$s"

    translator, sent = _translator(monkeypatch, transliterate)
    translated = translator.translate_file(path, "ru")
    texts = [t for body in sent for t in body["texts"]]
    assert not any("<run" in t or "%1$s" in t for t in texts)  # tags and placeholders were masked
    assert translated["translations"]["save"]["ru"].count("<run2>") == 1

    _write_translated_content(path, translated, get_handler(path, translator.config), set(), False,
                              source_file=path, source_language="en", target_language="ru")
    value = load_workbook(path, rich_text=True).active["C2"].value
    assert isinstance(value, CellRichText)
    runs = [(getattr(r, "text", r), getattr(getattr(r, "font", None), "b", None), getattr(getattr(r, "font", None), "i", None)) for r in value]
    assert ("Саве", True, False) in runs and ("%1$s", False, True) in runs
    assert str(value) == "Cлиск Саве то кееп %1$s"


def test_rich_text_tags_are_gated(tmp_path, capsys):
    path = _rich_workbook(str(tmp_path / "strings.xlsx"))
    XLSXHandler(None).write_in_place(path, {"save": "<run2>Сохранить %1$s"}, {"save"},
                                     target_language="ru", source_file=path)
    assert "Strings!C2" in capsys.readouterr().out
    assert load_workbook(path).active["C2"].value is None


# --- several sheets -----------------------------------------------------------------------------


def _multi_sheet_workbook(path):
    wb = Workbook()
    strings = wb.active
    strings.title = "Strings"
    strings.append(["key", "en", "ru"])
    strings.append(["greet", "Hello %1$s", None])
    strings.append(["plain", "Plain text", None])
    notes = wb.create_sheet("Notes")
    notes.append(["Topic", "Comment"])  # two columns, but no language column
    notes.append(["style", "Do not translate %1$s"])
    menu = wb.create_sheet("Menu Items")
    menu.append(["key", "en", "ru"])
    menu.append(["file", "File", None])
    menu.append(["greet", "Greet %1$s", None])  # same key as on Strings: no collision
    wb.save(path)
    return path


def test_every_translation_sheet_is_translated_and_notes_are_skipped(tmp_path, monkeypatch):
    path = _multi_sheet_workbook(str(tmp_path / "strings.xlsx"))
    content = read_xlsx_file(path)
    assert sorted(content["translations"]) == [
        "Menu Items!file", "Menu Items!greet", "Strings!greet", "Strings!plain",
    ]
    before = snapshot(path)

    translator, _ = _translator(monkeypatch, transliterate)
    translated = translator.translate_file(path, "ru")
    _write_translated_content(path, translated, get_handler(path, translator.config), set(), False,
                              source_file=path, source_language="en", target_language="ru")
    wb = load_workbook(path)
    assert wb["Strings"]["C2"].value == "Hелло %1$s" and wb["Strings"]["C3"].value == "Pлаин техт"
    assert wb["Menu Items"]["C2"].value == "Fиле" and wb["Menu Items"]["C3"].value == "Gреет %1$s"
    changed = {("Strings", "C2"), ("Strings", "C3"), ("Menu Items", "C2"), ("Menu Items", "C3")}
    _assert_cells_kept(before, snapshot(path), changed)  # Notes untouched


def test_multi_sheet_reports_and_keys_name_the_sheet(tmp_path, capsys, monkeypatch):
    path = _multi_sheet_workbook(str(tmp_path / "strings.xlsx"))
    handler = XLSXHandler(None)
    handler.write_in_place(path, {"Menu Items!greet": "Привет %1$с", "Menu Items!file": "Файл"},
                           {"Menu Items!greet", "Menu Items!file"}, target_language="ru", source_file=path)
    assert "'Menu Items'!C3" in capsys.readouterr().out
    assert read_language_file(path, "ru") == {"Menu Items!file": "Файл"}

    wb = load_workbook(path)
    wb["Menu Items"]["C3"] = "Привет %1$с"  # damaged
    wb.save(path)
    (tmp_path / ".algebras.config").write_text(json.dumps({
        "languages": ["en", "ru"],
        "source_files": {"strings.xlsx": {"destination_path": "strings.xlsx"}},
        "api": {"provider": "algebras-ai"},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    placeholders_command.execute(output_format="json")
    report = json.loads(capsys.readouterr().out)
    assert [i["key"] for i in report["issues"]] == ["greet ['Menu Items'!C3]"]
    assert placeholders_command.execute(fix=True, output_format="json") == 0
    assert load_workbook(path)["Menu Items"]["C3"].value == "Привет %1$s"


def test_new_key_of_a_sheet_goes_to_that_sheet(tmp_path):
    path = _multi_sheet_workbook(str(tmp_path / "strings.xlsx"))
    report = update_xlsx_cells(path, "ru", {"Menu Items!edit": "Правка", "Nowhere!x": "?"})
    assert report["written"] == ["'Menu Items'!C4"] and report["missing"] == ["Nowhere!x"]
    assert load_workbook(path)["Menu Items"]["A4"].value == "edit"


def test_single_sheet_keys_are_unchanged(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    assert sorted(read_xlsx_file(path)["translations"]) == ["formula", "greet", "plain", "price", "rich", "welcome"]


# --- .xls ----------------------------------------------------------------------------------------


class _FakeSheet:
    def __init__(self, name, rows):
        self.name = name
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = max(len(r) for r in rows)

    def row_values(self, index):
        return list(self._rows[index])


def _fake_xlrd(sheets):
    module = types.ModuleType("xlrd")
    module.open_workbook = lambda path: types.SimpleNamespace(sheets=lambda: sheets)
    return module


XLS_ROWS = [["key", "en", "ru"], ["greet", "Hello %1$s", ""], ["count", 3.0, ""], ["plain", "Plain text", "Текст"]]


def test_xls_is_detected_as_a_workbook():
    assert detect_format("strings.xls") == FileFormat.XLSX
    assert detect_format("strings.XLS") == FileFormat.XLSX


def test_xls_without_xlrd_fails_early_with_an_actionable_error(tmp_path, monkeypatch):
    path = tmp_path / "strings.xls"
    path.write_bytes(b"\xd0\xcf\x11\xe0 not really an xls")
    monkeypatch.setitem(sys.modules, "xlrd", None)  # import xlrd -> ImportError
    with pytest.raises(XlsNotSupportedError) as error:
        read_xlsx_file(str(path))
    message = str(error.value)
    assert "pip install xlrd" in message and ".xlsx" in message
    with pytest.raises(XlsNotSupportedError):
        TranslationStrategyFactory.get_strategy(str(path), object.__new__(_StubTranslator))


class _StubTranslator:
    config = None
    api_config = {}
    string_normalizer = None
    batch_size = 10

    def _get_batch_processor(self):
        return None


def test_xls_with_xlrd_is_read_and_written_to_xlsx(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "xlrd", _fake_xlrd([_FakeSheet("Strings", XLS_ROWS)]))
    source = str(tmp_path / "strings.xls")
    with open(source, "wb") as f:
        f.write(b"fake")
    assert read_language_file(source, "en") == {"greet": "Hello %1$s", "count": "3", "plain": "Plain text"}

    translator, _ = _translator(monkeypatch, transliterate)
    translated = translator.translate_file(source, "ru")
    _write_translated_content(source, translated, get_handler(source, translator.config), set(), False,
                              source_file=source, source_language="en", target_language="ru")
    out = capsys.readouterr().out
    assert "strings.xls is an Excel 97-2003 workbook" in out and "strings.xlsx" in out
    with open(source, "rb") as f:
        assert f.read() == b"fake"  # the .xls itself is never written
    ws = load_workbook(str(tmp_path / "strings.xlsx")).active
    assert ws["B2"].value == "Hello %1$s" and ws["C2"].value == "Hелло %1$s"
    assert ws["C4"].value == "Pлаин техт"


# --- status ---------------------------------------------------------------------------------------


def _status_workbook(path):
    wb = Workbook()
    ws = wb.active
    ws.append(["key", "en", "ru", "de"])
    ws.append(["a", "A", "А", None])
    ws.append(["b", "B", "Б", None])
    ws.append(["c", "C", None, "C de"])
    ws.append(["d", "D", None, None])
    wb.save(path)
    return path


def test_status_counts_xlsx_per_language_column(tmp_path):
    path = _status_workbook(str(tmp_path / "strings.xlsx"))
    assert status_command.count_translated_keys(path, "en") == (4, 4)
    assert status_command.count_current_and_outdated_keys(path, path, "en", "ru") == (2, 0)
    assert status_command.count_current_and_outdated_keys(path, path, "en", "de") == (1, 0)


def test_status_command_reports_xlsx_languages(tmp_path, monkeypatch, capsys):
    _status_workbook(str(tmp_path / "strings.xlsx"))
    (tmp_path / ".algebras.config").write_text(json.dumps({
        "languages": ["en", "ru", "de"],
        "source_files": {"strings.xlsx": {"destination_path": "strings.xlsx"}},
        "api": {"provider": "algebras-ai"},
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ALGEBRAS_API_KEY", raising=False)
    status_command.execute()
    out = capsys.readouterr().out
    assert re.search(r"ru.*2/4 keys", out) and re.search(r"de.*1/4 keys", out)


EXCEL_SHEET = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac" mc:Ignorable="x14ac">'
    '<dimension ref="A1:C2"/><sheetData>'
    '<row r="1" spans="1:3" x14ac:dyDescent="0.25"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>'
    '<c r="C1" s="2" t="s"><v>2</v></c></row>\n'
    '<row r="2" spans="1:3" x14ac:dyDescent="0.25"><c r="A2" t="s"><v>3</v></c><c r="C2" s="4" t="s"><v>4</v></c></row>'
    '</sheetData><pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/></worksheet>'
)


def test_excel_style_sheet_xml_is_edited_in_place():
    from xml.etree import ElementTree as ET

    from algebras.utils.xlsx_package import SheetEdit, _edit_sheet_xml

    edit = SheetEdit()
    edit.cells["C2"] = "x < y & \"z\""
    edit.cells["B2"] = CellRichText([TextBlock(InlineFont(b=True), "Bold"), " rest"])
    edit.cells["D3"] = "new"
    xml = _edit_sheet_xml(EXCEL_SHEET, edit)
    root = ET.fromstring(xml.encode())  # well-formed
    assert xml.startswith(EXCEL_SHEET[: EXCEL_SHEET.index("<dimension")])  # prolog and namespaces kept
    assert '<row r="1" spans="1:3" x14ac:dyDescent="0.25"><c r="A1" t="s"><v>0</v></c>' in xml  # row 1 verbatim
    assert '<c r="C2" s="4" t="inlineStr"><is><t xml:space="preserve">x &lt; y &amp; "z"</t></is></c>' in xml
    assert '<c r="B2" t="inlineStr"><is><r><rPr><b val="1"/></rPr><t xml:space="preserve">Bold</t></r>' in xml
    assert xml.index('r="A2"') < xml.index('r="B2"') < xml.index('r="C2"')
    assert '<row r="3"><c r="D3" t="inlineStr">' in xml and '<dimension ref="A1:D3"/>' in xml

    prefixed = EXCEL_SHEET.replace("<worksheet xmlns=", "<x:worksheet xmlns:x=").replace("</worksheet>", "</x:worksheet>")
    prefixed = re.sub(r"<(/?)(dimension|sheetData|row|c|v|pageMargins)\b", r"<\1x:\2", prefixed)
    edit = SheetEdit()
    edit.cells["B2"] = "Prefixed"
    xml = _edit_sheet_xml(prefixed, edit)
    ET.fromstring(xml.encode())
    assert '<x:c r="B2" t="inlineStr"><x:is><x:t xml:space="preserve">Prefixed</x:t></x:is></x:c>' in xml
