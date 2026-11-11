"""
XLSX placeholder safety: mixed placeholder syntaxes survive translation, cells stay strings (never
formulas), styles, other sheets and column widths are kept; damaged cells are reported with their
Excel reference and repaired in place by 'algebras placeholders'.
"""

import json
import os

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Font, PatternFill

from algebras.commands import healthcheck_command, placeholders_command
from algebras.commands.translate_command import (
    _load_file_contents,
    _translate_plural_aware,
    _write_translated_content,
)
from algebras.services.placeholders import profile_for_path, verify
from algebras.services.placeholders.file_checks import get_file_check
from algebras.services.placeholders.fix_writers import get_fix_writer
from algebras.services.translator import Translator
from algebras.utils.file_format_detector import FileFormat, detect_format, is_flat_format
from algebras.utils.file_format_handlers import XLSXHandler, get_handler
from algebras.utils.lang_validator import read_language_file, validate_language_files
from algebras.utils.xlsx_handler import read_xlsx_cells, set_cell_text, update_xlsx_cells

from tests.test_placeholders_translation import transliterate
from tests.test_stringsdict_plurals import _batch_response, _mock_config

SOURCE = {
    "greet": "Hello %1$s, you have %2$d messages",
    "welcome": "Hi {{name}}, {count} new",
    "formula": "=Total: {0} items",
    "price": "Price: ${amount}",
    "plain": "Plain text",
}
RICH_RUNS = [TextBlock(InlineFont(b=True), "Bold "), "sent to %1$s"]


def make_workbook(path, ru=None, rich_ru=None):
    """Sheet 'Strings' (key, en, ru) with a styled header, plus a second sheet 'Notes'."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Strings"
    ws.append(["key", "en", "ru"])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4472C4")
    ru = ru or {}
    for key, text in SOURCE.items():
        ws.append([key, text, ru.get(key)])
    ws.append(["rich", None, None])
    ws["B7"].value = CellRichText(list(RICH_RUNS))
    if rich_ru is not None:
        ws["C7"].value = rich_ru
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"  # "=Total…" is text, not a formula
    ws["B2"].font = Font(italic=True)
    ws.column_dimensions["B"].width = 42
    ws.column_dimensions["C"].width = 37
    notes = wb.create_sheet("Notes")
    notes["A1"] = "Do not translate this sheet: %1$s"
    notes["A2"] = "=1+1"  # a real formula
    wb.save(path)
    return path


def snapshot(path):
    """{(sheet, coordinate): (value as text, style ids)} of every cell, plus column widths."""
    wb = load_workbook(path, rich_text=True)
    cells = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                cells[(ws.title, c.coordinate)] = (repr(c.value), c.data_type, c.style_id)
    widths = {(ws.title, k): d.width for ws in wb.worksheets for k, d in ws.column_dimensions.items()}
    return cells, widths


# --- registration --------------------------------------------------------------------------


def test_xlsx_is_a_registered_format(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"), ru={"plain": "Обычный текст"})
    assert detect_format(path) == FileFormat.XLSX
    assert is_flat_format(FileFormat.XLSX)
    assert isinstance(get_handler(path, None), XLSXHandler)
    assert read_language_file(path, "en")["greet"] == SOURCE["greet"]
    assert read_language_file(path, "ru") == {"plain": "Обычный текст"}
    assert get_file_check(path) is not None and get_fix_writer(path) is not None
    valid, missing = validate_language_files(path, path, "en", "ru")
    assert missing == set(SOURCE) - {"plain"} | {"rich"}


def test_glossary_workbooks_are_skipped(tmp_path):
    path = str(tmp_path / "glossary.xlsx")
    wb = Workbook()
    wb.active.append(["Record ID", "en", "ru"])
    wb.active.append(["1", "%1$s term", "%1$с термин"])
    wb.save(path)
    with pytest.raises(ValueError, match="glossary"):
        read_language_file(path, "ru")
    assert get_file_check(path)(path, path, "en", "ru", None) == []
    issues, keys, _, _ = healthcheck_command.validate_file_pair(path, path, "en", "ru", None, False)
    assert issues == [] and keys == 0


def test_profile_is_detected_from_the_source_column(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    profile = profile_for_path(path, None)
    assert {"printf", "i18next", "icu_simple", "js_template"} <= set(profile.syntax_names)
    assert "ruby" not in profile.syntax_names
    assert verify("Hello %1$s", "Привет %1$с", profile)


# --- writing ------------------------------------------------------------------------------


def test_values_are_written_as_strings_never_formulas(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    update_xlsx_cells(path, "ru", {"greet": "=SUM(A1)", "plain": "+7 @user -1"})
    ws = load_workbook(path).active
    assert ws["C2"].value == "=SUM(A1)" and ws["C2"].data_type == "s"
    assert ws["C6"].value == "+7 @user -1" and ws["C6"].data_type == "s"
    # data_only reading still gives the text, not a (missing) formula result
    assert load_workbook(path, data_only=True).active["C2"].value == "=SUM(A1)"


def test_rich_text_runs_are_kept_when_the_change_fits_in_a_run(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    wb = load_workbook(path, rich_text=True)
    cell = wb.active["B7"]
    assert set_cell_text(cell, "Bold sent to %1$s!", keep_runs=True) is True
    assert isinstance(cell.value, CellRichText)
    assert [getattr(r, "text", r) for r in cell.value] == ["Bold ", "sent to %1$s!"]
    assert cell.value[0].font.b
    # A whole new sentence crosses the run boundary: written as plain text, reported.
    assert set_cell_text(cell, "Совсем другой текст", keep_runs=True) is False
    assert cell.value == "Совсем другой текст" and cell.data_type == "s"


def test_new_language_column_gets_the_header_style(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    update_xlsx_cells(path, "de", {"plain": "Einfacher Text"})
    ws = load_workbook(path).active
    assert ws["D1"].value == "de" and ws["D1"].font.b and ws["D1"]._style == ws["C1"]._style
    assert ws["D6"].value == "Einfacher Text"
    assert ws.column_dimensions["D"].width == 37


# --- translation end to end ---------------------------------------------------------------


def _fake_api(sent, answer):
    def post(url, headers=None, json=None, **kwargs):
        sent.append(json)
        return _batch_response([answer(t) for t in json["texts"]])

    return post


def _config():
    config = _mock_config()
    config.get_languages.return_value = ["en", "ru"]
    return config


def _translator(monkeypatch, answer):
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    sent = []
    monkeypatch.setattr("algebras.services.api_client.requests.post", _fake_api(sent, answer))
    translator = Translator(config=_config())
    translator.api_client.set_sync_batch(True)
    return translator, sent


def _translate_missing(path, monkeypatch, answer):
    translator, sent = _translator(monkeypatch, answer)
    config = translator.config
    handler = get_handler(path, config)
    source, target, source_raw, target_raw, contexts = _load_file_contents(path, path, handler, "en", "ru", config)
    missing = [k for k in source if k not in target]
    translated = _translate_plural_aware(
        translator.translate_missing_keys_batch, source, target, missing, "ru",
        source_file_path=path, contexts=contexts,
    )
    _write_translated_content(
        path, translated, handler, set(missing), True,
        source_file=path, source_language="en", target_language="ru",
    )
    return [t for body in sent for t in body["texts"]]


def _assert_cells_kept(before, after, changed):
    cells_before, widths_before = before
    cells_after, widths_after = after
    assert widths_after == widths_before
    for ref, (value, data_type, style) in cells_before.items():
        if ref in changed:
            assert cells_after[ref][2] == style  # the written cell keeps its style id
            continue
        assert cells_after[ref] == (value, data_type, style), ref


def test_transliterating_model_keeps_placeholders_and_styles(tmp_path, monkeypatch):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    before = snapshot(path)
    sent = _translate_missing(path, monkeypatch, transliterate)

    assert not any("%1$s" in t or "{{name}}" in t for t in sent)  # the model only saw tokens
    ws = load_workbook(path, rich_text=True).active
    for row in range(2, 8):
        source = str(ws.cell(row=row, column=2).value)
        target = ws.cell(row=row, column=3)
        assert target.data_type == "s"
        assert verify(source, target.value, profile_for_path(path, None)) == []
    assert ws["C2"].value == "Hелло %1$s, йоу hаве %2$d мессаgес"
    assert ws["C4"].value.startswith("=") and ws["C4"].data_type == "s"
    assert "{0}" in ws["C4"].value and "${amount}" in ws["C5"].value
    assert "{{name}}" in ws["C3"].value and "{count}" in ws["C3"].value

    changed = {("Strings", f"C{r}") for r in range(2, 8)}
    _assert_cells_kept(before, snapshot(path), changed)
    notes = load_workbook(path).worksheets[1]
    assert notes["A1"].value == "Do not translate this sheet: %1$s"
    assert notes["A2"].value == "=1+1" and notes["A2"].data_type == "f"


def test_full_file_translation_keeps_the_workbook(tmp_path, monkeypatch):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    target = str(tmp_path / "strings.ru.xlsx")
    translator, _ = _translator(monkeypatch, transliterate)
    content = translator.translate_file(path, "ru")
    _write_translated_content(target, content, get_handler(path, translator.config), set(), False,
                              source_file=path, source_language="en", target_language="ru")
    ws = load_workbook(target).active
    assert ws["C2"].value == "Hелло %1$s, йоу hаве %2$d мессаgес"
    assert ws["C4"].data_type == "s" and ws["C4"].value.startswith("=")
    assert ws["A1"].font.b and ws.column_dimensions["B"].width == 42
    assert load_workbook(target).sheetnames == ["Strings", "Notes"]


def test_damaged_cells_are_not_written(tmp_path, monkeypatch, capsys):
    path = make_workbook(str(tmp_path / "strings.xlsx"), ru={"greet": "Старое значение %1$s %2$d"})

    def drop_tokens(text):  # the model loses every placeholder token, every time
        return "".join(ch for ch in transliterate(text) if ch not in "⟦⟧0123456789")

    translator, _ = _translator(monkeypatch, drop_tokens)
    content = translator.translate_file(path, "ru")
    _write_translated_content(path, content, get_handler(path, translator.config), set(), False,
                              source_file=path, source_language="en", target_language="ru")
    out = capsys.readouterr().out
    ws = load_workbook(path).active
    assert ws["C2"].value == "Старое значение %1$s %2$d"  # keeps its old value
    assert ws["C3"].value is None and ws["C5"].value is None  # stays empty
    assert ws["C6"].value == "Pлаин техт"  # no placeholders: translated
    assert "greet" in out and "welcome" in out


def test_write_gate_reports_the_cell_reference(tmp_path, capsys):
    path = make_workbook(str(tmp_path / "strings.xlsx"))
    handler = XLSXHandler(None)
    handler.write_in_place(path, {"greet": "Хелло %1$с", "plain": "Текст"}, {"greet", "plain"},
                           target_language="ru", source_file=path)
    out = capsys.readouterr().out
    assert "Strings!C2" in out and "greet" in out
    ws = load_workbook(path).active
    assert ws["C2"].value is None and ws["C6"].value == "Текст"


# --- algebras placeholders + healthcheck -------------------------------------------------

DAMAGED_RU = {
    "greet": "Привет %1$с, у вас %2$д сообщений",
    "welcome": "Привет {{name}}, {count} новых",  # clean
    "formula": "=Итого: {٠} шт.",
    "price": "Цена: ${amount}",  # clean
    "plain": "Обычный текст",
}
RICH_RU = CellRichText([TextBlock(InlineFont(b=True), "Жирный "), "отправлено %1$с"])


@pytest.fixture
def check_project(tmp_path, monkeypatch):
    make_workbook(str(tmp_path / "strings.xlsx"), ru=DAMAGED_RU, rich_ru=RICH_RU)
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
    return str(tmp_path / "strings.xlsx")


def _report(capsys):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json")
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_cell_references(check_project, capsys):
    code, report = _report(capsys)
    assert code == 1 and report["files_checked"] == 1
    keys = sorted(i["key"] for i in report["issues"])
    assert keys == ["formula [Strings!C4]", "greet [Strings!C2]", "rich [Strings!C7]"]
    assert all(i["fixed"] is not None for i in report["issues"])
    codes = {c for i in report["issues"] for c in (p["code"] for p in i["problems"])}
    assert "corrupted" in codes


def test_fix_repairs_cells_in_place_and_is_idempotent(check_project, capsys):
    before = snapshot(check_project)
    assert placeholders_command.execute(fix=True, output_format="json") == 0
    after = snapshot(check_project)
    changed = {("Strings", "C2"), ("Strings", "C4"), ("Strings", "C7")}
    _assert_cells_kept(before, after, changed)

    ws = load_workbook(check_project, rich_text=True).active
    assert ws["C2"].value == "Привет %1$s, у вас %2$d сообщений"
    assert ws["C4"].value == "=Итого: {0} шт." and ws["C4"].data_type == "s"
    assert isinstance(ws["C7"].value, CellRichText)  # runs kept
    assert str(ws["C7"].value) == "Жирный отправлено %1$s" and ws["C7"].value[0].font.b

    code, report = _report(capsys)
    assert code == 0 and report["issues"] == []
    placeholders_command.execute(fix=True, output_format="json")
    assert snapshot(check_project) == after


def test_dry_run_writes_nothing(check_project):
    before = snapshot(check_project)
    assert placeholders_command.execute(fix=True, dry_run=True, output_format="json") == 1
    assert snapshot(check_project) == before


def test_healthcheck_covers_xlsx(check_project):
    issues, keys_checked, errors, _ = healthcheck_command.validate_file_pair(
        "strings.xlsx", "strings.xlsx", "en", "ru", None, False
    )
    assert keys_checked == 6
    assert "system" not in {i.category for i in issues}
    assert {"greet", "formula", "rich"} <= {i.key for i in issues if i.category == "placeholders"}


def test_translation_over_a_rich_text_cell_takes_the_source_formatting(tmp_path, capsys):
    path = make_workbook(str(tmp_path / "strings.xlsx"), rich_ru=CellRichText(list(RICH_RU)))
    # No run tags in the translation: the whole cell takes the source's first run (bold).
    XLSXHandler(None).write_in_place(path, {"rich": "Совсем новый перевод %1$s"}, {"rich"},
                                     target_language="ru", source_file=path)
    assert "rich-text formatting was replaced" not in capsys.readouterr().out
    value = load_workbook(path, rich_text=True).active["C7"].value
    assert isinstance(value, CellRichText) and str(value) == "Совсем новый перевод %1$s"
    assert len(value) == 1 and value[0].font.b
    # With run tags, each span takes the font of its source run.
    XLSXHandler(None).write_in_place(path, {"rich": "<run1>Жирно</run1> отправлено %1$s"}, {"rich"},
                                     target_language="ru", source_file=path)
    value = load_workbook(path, rich_text=True).active["C7"].value
    assert [getattr(r, "text", r) for r in value] == ["Жирно", " отправлено %1$s"]
    assert value[0].font.b


def test_read_cells_gives_coordinates(tmp_path):
    path = make_workbook(str(tmp_path / "strings.xlsx"), ru={"plain": "x"})
    sheet = read_xlsx_cells(path)
    assert sheet.title == "Strings" and sheet.languages == ["en", "ru"]
    assert sheet.rows["plain"]["ru"].coordinate == "C6"
    assert sheet.coordinate("greet", "ru") == "C2"
    assert sheet.ref("C2") == "Strings!C2"
    assert os.path.exists(path)
