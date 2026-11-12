"""
CSV / TSV placeholder protection: profile auto-detection over the source column (mixed syntaxes),
translation end to end with a transliterating model into several columns, per-cell rejection,
and 'algebras placeholders' check / --fix / idempotency with only the corrupted cells changed.
"""

import csv
import io
import json
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.placeholders import GENERIC_PROFILE, extract, profile_for_path
from algebras.services.placeholders.engine import TOKEN_OPEN
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import csv_format
from algebras.services.placeholders.formats.csv_format import cell_spans, check_file, write_fixes

# One table exported from Android, a .NET backend, an i18next web app and JS templates.
ROWS = [
    ("app.title", "Welcome, {0}!"),
    ("android.greeting", "Hello %1$s, you have %2$d new messages"),
    ("web.user", "Signed in as {{name}}"),
    ("js.total", "Total: ${0}"),
    ("mixed", 'Say "{0}", then %1$s'),
    ("plain", "No placeholders here"),
]
SOURCE_SYNTAXES = {"icu_simple", "printf", "i18next", "js_template"}


@pytest.fixture(autouse=True)
def csv_fix_writer():
    # Other tests may replace writers with recording ones; use the real one here.
    register_fix_writer([".csv", ".tsv"], csv_format.write_fixes)
    yield


def _table(languages, rows, delimiter=","):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=delimiter, lineterminator="\n")
    writer.writerow(["key"] + list(languages))
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def _project(tmp_path, monkeypatch, languages, text, name="strings.csv"):
    path = tmp_path / "loc" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    rel = f"loc/{name}"
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": list(languages),
                "source_files": {rel: {"destination_path": rel}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return path


def _read(path, delimiter=","):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=delimiter))
    return rows[0], {r[0]: dict(zip(rows[0][1:], r[1:])) for r in rows[1:] if r}


_LATIN_TO_CYRILLIC = str.maketrans(dict(zip("sdcSDabeiklmnoprtuvxyz", "сдсСДабеиклмнопртувхйз")))


def transliterate(text: str) -> str:
    """The uz-Cyrl failure: every Latin letter becomes Cyrillic, and braces get spaces."""
    return text.translate(_LATIN_TO_CYRILLIC).replace("{{", "{{ ").replace("}}", " }}")


def _fake_client(sent, damage=None):
    client = MagicMock()

    def one(text):
        return damage(text) if damage else transliterate(text)

    def translate_batch(texts, *args, **kwargs):
        sent.append(list(texts))
        return [one(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    client.translate.side_effect = lambda text, *a, **k: one(text)
    return client


def _translate(languages, sent, damage=None, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent, damage)):
        for language in languages:
            translate_command.execute(language=language, **kwargs)


def _raws(text, profile):
    return sorted(p.raw for p in extract(text, profile))


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def test_mixed_syntaxes_are_detected_from_the_source_column(tmp_path):
    path = tmp_path / "strings.csv"
    # The source column is not the first one, and a target column uses a syntax the source lacks.
    path.write_text(
        _table(["de", "en"], [("a", "%{x}", "{0} and %1$s"), ("b", "", "Hi {{name}}, ${0}")]),
        encoding="utf-8",
    )
    config = MagicMock()
    config.get_source_files.return_value = {}
    config.get_source_language.return_value = "en"
    config.get_destination_locale_code.side_effect = lambda code: code
    profile = csv_format.resolve_profile(str(path), config)
    assert set(profile.syntax_names) == SOURCE_SYNTAXES
    # Longest match first: no overlap between the syntaxes in one cell.
    assert [(p.raw, p.syntax) for p in extract("%1$s {0} {{name}} ${0}", profile)] == [
        ("%1$s", "printf"),
        ("{0}", "icu_simple"),
        ("{{name}}", "i18next"),
        ("${0}", "js_template"),
    ]


def test_glossary_csv_gets_the_generic_profile(tmp_path):
    path = tmp_path / "glossary.csv"
    path.write_text("Record ID,en,de\n1,%1$s term,%1$s Begriff\n", encoding="utf-8")
    assert profile_for_path(str(path)) == GENERIC_PROFILE


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

TARGETS = ("ru", "uk", "be")


@pytest.mark.parametrize("mode", [{"force": "__all__"}, {"only_missing": True}])
def test_transliterating_model_keeps_every_column_intact(tmp_path, monkeypatch, mode):
    text = _table(("en",) + TARGETS, [(k, v, "", "", "") for k, v in ROWS])
    path = _project(tmp_path, monkeypatch, ("en",) + TARGETS, text)
    sent = []
    _translate(TARGETS, sent, **mode)

    headers, data = _read(path)
    assert headers == ["key", "en", "ru", "uk", "be"]
    profile = profile_for_path(str(path))
    assert set(profile.syntax_names) == SOURCE_SYNTAXES
    for key, source in ROWS:
        assert data[key]["en"] == source
        for language in TARGETS:
            translated = data[key][language]
            assert translated, (key, language)
            assert _raws(translated, profile) == _raws(source, profile), (key, language, translated)
    # The quote next to {0} and the comma survived csv quoting: the cell reads back unchanged.
    assert data["mixed"]["ru"] == transliterate('Say "') + '{0}' + transliterate('", then ') + "%1$s"
    for language in TARGETS:
        assert check_file(str(path), str(path), "en", language) == []
    # The model never saw a raw placeholder.
    texts = [t for batch in sent for t in batch]
    assert any(TOKEN_OPEN in t for t in texts)
    for raw in ("{0}", "%1$s", "%2$d", "{{name}}", "${0}"):
        assert not any(raw in t for t in texts), raw


def test_rejected_cell_keeps_its_previous_value_and_is_reported(tmp_path, monkeypatch, capsys):
    text = _table(
        ("en", "ru", "de"),
        [
            ("android.greeting", "Hello %1$s, you have %2$d new messages", "старое %1$s %2$d", ""),
            ("web.user", "Signed in as {{name}}", "", ""),
            ("plain", "No placeholders here", "", ""),
        ],
    )
    path = _project(tmp_path, monkeypatch, ("en", "ru", "de"), text)

    def drop_second_token(text):
        # Loses ⟦1⟧ every time (also on the retry); other texts translate fine.
        return transliterate(text.replace("⟦1⟧", ""))

    _translate(["ru", "de"], [], damage=drop_second_token, force="__all__")
    _, data = _read(path)
    assert data["android.greeting"]["ru"] == "старое %1$s %2$d"  # previous value kept
    assert data["android.greeting"]["de"] == ""  # stays empty, never written damaged
    assert data["web.user"]["ru"] == transliterate("Signed in as ") + "{{name}}"
    assert data["plain"]["de"] == transliterate("No placeholders here")
    out = capsys.readouterr().out
    assert "Row 'android.greeting', column 'ru'" in out and "Row 'android.greeting', column 'de'" in out


def test_tsv_with_tabs_in_neighbouring_cells(tmp_path, monkeypatch):
    rows = [
        ("app.title", "Welcome, {0}!", "", "Willkommen,\t{0}!"),
        ("web.user", "Signed in\tas {{name}}", "", "Angemeldet als\t{{name}}"),
        ("js.total", "Total: ${0}", "", ""),
    ]
    text = _table(("en", "ru", "de"), rows, delimiter="\t")
    path = _project(tmp_path, monkeypatch, ("en", "ru", "de"), text, name="strings.tsv")
    _translate(["ru"], [], force="__all__")

    headers, data = _read(path, "\t")
    assert headers == ["key", "en", "ru", "de"]
    profile = profile_for_path(str(path))
    for key, source, _, de in rows:
        assert data[key]["en"] == source
        assert data[key]["de"] == de
        assert _raws(data[key]["ru"], profile) == _raws(source, profile)
    assert data["web.user"]["ru"] == transliterate("Signed in\tas ") + "{{name}}"
    assert check_file(str(path), str(path), "en", "ru") == []


# ---------------------------------------------------------------------------
# 'algebras placeholders'
# ---------------------------------------------------------------------------

LANGS = ("en", "ru", "uk", "de", "fr")
GOOD = {
    "ru": ["Добро пожаловать, {0}!", "Привет %1$s, у вас %2$d новых", "Вход: {{name}}", "Итого: ${0}"],
    "uk": ["Ласкаво просимо, {0}!", "Привіт %1$s, у вас %2$d нових", "Вхід: {{name}}", "Разом: ${0}"],
    "de": ["Willkommen, {0}!", "Hallo %1$s, du hast %2$d neue", "Angemeldet: {{name}}", "Summe: ${0}"],
    "fr": ["Bienvenue, {0} !", "Bonjour %1$s, vous avez %2$d", "Connecté : {{name}}", "Total : ${0}"],
}
# Corruptions in 2 of the 4 language columns (de and fr stay intact).
BAD = {
    ("android.greeting", "ru"): "Привет %1$с, у вас %2$д новых",  # transliterated
    ("web.user", "ru"): "Вход: {{ имя }}",  # translated name: the only slot, restored
    ("js.total", "uk"): "Разом: ${0},  ＄{1}",  # an invented placeholder: needs retranslation
    ("mixed", "uk"): 'Скажіть "{0}", потім %1$с',  # quote and delimiter next to placeholders
}


def _check_text(line_ending="\n", delimiter=","):
    keys = ["app.title", "android.greeting", "web.user", "js.total"]
    sources = dict(ROWS)
    rows = []
    for i, key in enumerate(keys):
        cells = [GOOD[l][i] for l in LANGS[1:]]
        rows.append([key, sources[key]] + cells)
    rows.append(["mixed", sources["mixed"], 'Скажите "{0}", затем %1$s', "", 'Sag "{0}", dann %1$s', ""])
    for (key, language), bad in BAD.items():
        row = next(r for r in rows if r[0] == key)
        row[LANGS.index(language) + 1] = bad
    out = io.StringIO()
    writer = csv.writer(out, delimiter=delimiter, lineterminator=line_ending)
    writer.writerow(["key"] + list(LANGS))
    for row in rows:
        writer.writerow(row)
    return out.getvalue()


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("name, delimiter, line_ending", [("strings.csv", ",", "\r\n"), ("strings.tsv", "\t", "\n")])
def test_report_fix_clean_idempotent(tmp_path, monkeypatch, capsys, name, delimiter, line_ending):
    text = _check_text(line_ending, delimiter)
    path = _project(tmp_path, monkeypatch, LANGS, text, name=name)

    code, report = _report(capsys)
    assert code == 1
    problems = {(i["language"], i["key"]): sorted(p["code"] for p in i["problems"]) for i in report["issues"]}
    assert problems == {
        ("ru", "android.greeting [ru]"): ["corrupted", "corrupted", "missing", "missing"],
        ("ru", "web.user [ru]"): ["extra", "missing"],
        ("uk", "js.total [uk]"): ["extra"],  # a placeholder the model invented
        ("uk", "mixed [uk]"): ["corrupted", "missing"],
    }
    fixed = {i["key"]: i["fixed"] for i in report["issues"]}
    assert fixed == {
        "android.greeting [ru]": "Привет %1$s, у вас %2$d новых",
        "web.user [ru]": "Вход: {{name}}",
        "js.total [uk]": None,
        "mixed [uk]": 'Скажіть "{0}", потім %1$s',
    }

    code, report = _report(capsys, fix=True)
    assert code == 2  # one cell needs retranslation
    statuses = {i["key"]: i["status"] for i in report["issues"]}
    assert statuses == {
        "android.greeting [ru]": "fixed",
        "mixed [uk]": "fixed",
        "web.user [ru]": "fixed",
        "js.total [uk]": "unresolved",
    }
    # Only the fixed cells changed: the delimiter, quoting and line endings are kept.
    after = path.read_bytes().decode("utf-8")
    expected = (
        text.replace("Привет %1$с, у вас %2$д новых", "Привет %1$s, у вас %2$d новых")
        .replace('"Скажіть ""{0}"", потім %1$с"', '"Скажіть ""{0}"", потім %1$s"')
        .replace("Вход: {{ имя }}", "Вход: {{name}}")
    )
    assert after == expected
    assert after != text

    # The fixable ones are clean now; fixing again changes nothing.
    code, report = _report(capsys)
    assert {i["key"] for i in report["issues"]} == {"js.total [uk]"}
    _report(capsys, fix=True)
    assert path.read_bytes().decode("utf-8") == expected


def test_clean_after_all_fixable(tmp_path, monkeypatch, capsys):
    text = _check_text().replace("${0},  ＄{1}", "${0}")
    path = _project(tmp_path, monkeypatch, LANGS, text)
    code, _ = _report(capsys, fix=True)
    assert code == 0
    fixed = path.read_text(encoding="utf-8")
    assert _report(capsys) == (0, {"files_checked": 4, "skipped": [], "issues": []})
    code, _ = _report(capsys, fix=True)
    assert code == 0 and path.read_text(encoding="utf-8") == fixed


def test_retranslate_rewrites_only_the_unfixable_cell(tmp_path, monkeypatch, capsys):
    path = _project(tmp_path, monkeypatch, LANGS, _check_text())
    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        code = placeholders_command.execute(fix=True, retranslate=True)
    assert code == 0, capsys.readouterr().out
    assert [t for batch in sent for t in batch] == ["Total: ⟦0⟧"]
    _, data = _read(path)
    assert data["js.total"]["uk"] == transliterate("Total: ") + "${0}"
    assert data["js.total"]["ru"] == GOOD["ru"][3]
    assert _report(capsys)[0] == 0


def test_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    path = _project(tmp_path, monkeypatch, LANGS, _check_text())
    before = path.read_bytes()
    code, _ = _report(capsys, fix=True, dry_run=True)
    assert code == 1
    assert path.read_bytes() == before


# ---------------------------------------------------------------------------
# Writer details
# ---------------------------------------------------------------------------


def test_cell_spans_match_csv_reader():
    text = 'k,a,b\r\nx,"q ""1"", {0}",plain\n\ny,"multi\nline %1$s",\rz,"",tail"x\n'
    spans = cell_spans(text, ",")
    parsed = list(csv.reader(io.StringIO(text, newline="")))
    assert len(spans) == len(parsed)
    for span_row, row in zip(spans, parsed):
        values = [next(csv.reader(io.StringIO(text[c.start : c.end], newline="")), [""]) for c in span_row]
        assert [v[0] if v else "" for v in values] == row


def test_writer_quotes_only_when_needed_and_keeps_quoted_cells_quoted(tmp_path):
    path = tmp_path / "t.csv"
    original = 'key,en,de\r\na,"Hi {0}",Hallo {О}\r\nb,x %1$s,"y %1$с"\r\nc,z,unchanged "q"\r\n'
    path.write_bytes(original.encode("utf-8"))
    write_fixes(str(path), {("a",): 'Hallo, "{0}"', ("b",): "y %1$s"}, "de")
    assert path.read_bytes().decode("utf-8") == (
        'key,en,de\r\na,"Hi {0}","Hallo, ""{0}"""\r\nb,x %1$s,"y %1$s"\r\nc,z,unchanged "q"\r\n'
    )
    with pytest.raises(ValueError):
        write_fixes(str(path), {("missing",): "v"}, "de")
