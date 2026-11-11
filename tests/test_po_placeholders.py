"""
Gettext .po placeholder protection: per-entry syntax from `#,` flags, plural forms, the write gate,
translation end to end with a transliterating model, and 'algebras placeholders' check / --fix.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.placeholders import extract, mask, profile_for_path
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import po as po_format
from algebras.services.placeholders.formats.po import check_value, profile_for_flags
from algebras.utils.po_handler import (
    _parse_po_content,
    _reconstruct_po_content,
    expand_plural_source,
    plural_key,
    read_po_file,
    write_po_file,
)

MSGFMT = shutil.which("msgfmt")
needs_msgfmt = pytest.mark.skipif(MSGFMT is None, reason="msgfmt (gettext) is not installed")


def msgfmt_check(path) -> None:
    result = subprocess.run(
        [MSGFMT, "--check-format", "-o", os.devnull, str(path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture(autouse=True)
def po_fix_writer():
    # Other tests may replace writers with recording ones; use the real one here.
    register_fix_writer([".po"], po_format.write_fixes)
    yield


SOURCE_PO = r"""# Demo shop.
msgid ""
msgstr ""
"Project-Id-Version: shop\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Language: en\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: shop/views.py:12
#, python-format
msgid "Hello, %(name)s!"
msgstr "Hello, %(name)s!"

#: shop/templates/cart.html:5
#, python-format
msgid "%(counter)s item in your cart"
msgid_plural "%(counter)s items in your cart"
msgstr[0] "%(counter)s item in your cart"
msgstr[1] "%(counter)s items in your cart"

#, python-format
msgid "One file"
msgid_plural "%(counter)s files"
msgstr[0] "One file"
msgstr[1] "%(counter)s files"

#: native/report.c:40
#, c-format
msgid "%1$s scored %2$d points"
msgstr "%1$s scored %2$d points"

#, python-brace-format
msgid "Welcome {0}, use {{braces}} literally"
msgstr "Welcome {0}, use {{braces}} literally"

#, no-c-format
msgid "100% satisfaction"
msgstr "100% satisfaction"
"""

RU_PLURAL = "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"
RU_FORMS = (3, RU_PLURAL.split("plural=", 1)[1].rstrip(";"))


def _entry(content: str, msgid: str):
    return next(e for e in _parse_po_content(content) if e["msgid"] == msgid)


# ---------------------------------------------------------------------------
# Flags and per-entry profiles
# ---------------------------------------------------------------------------


def test_flags_are_parsed_per_entry():
    flags = {e["msgid"]: e["flags"] for e in _parse_po_content(SOURCE_PO)}
    assert flags["Hello, %(name)s!"] == ["python-format"]
    assert flags["%1$s scored %2$d points"] == ["c-format"]
    assert flags["Welcome {0}, use {{braces}} literally"] == ["python-brace-format"]
    assert flags["100% satisfaction"] == ["no-c-format"]
    assert flags[""] == []


def test_flags_and_layout_round_trip_unchanged(tmp_path):
    target = tmp_path / "ru.po"
    target.write_text(SOURCE_PO, encoding="utf-8")
    write_po_file(str(target), read_po_file(str(target)))
    assert target.read_text(encoding="utf-8") == SOURCE_PO

    content = read_po_file(str(target))
    content["Hello, %(name)s!"] = "Привет, %(name)s!"
    content[plural_key("One file", 1)] = "%(counter)s файла"
    write_po_file(str(target), content)
    written = target.read_text(encoding="utf-8")
    changed = [
        (a, b) for a, b in zip(SOURCE_PO.split("\n"), written.split("\n")) if a != b
    ]
    assert changed == [
        ('msgstr "Hello, %(name)s!"', 'msgstr "Привет, %(name)s!"'),
        ('msgstr[1] "%(counter)s files"', 'msgstr[1] "%(counter)s файла"'),
    ]
    # Flags are never added to or dropped from entries.
    assert written.count("#, python-format") == 3 and written.count("#, c-format") == 1


def test_fuzzy_mark_joins_the_existing_flags_line(tmp_path):
    target = tmp_path / "de.po"
    target.write_text(SOURCE_PO, encoding="utf-8")
    write_po_file(str(target), {"Hello, %(name)s!": "Hallo, %(name)s!"}, mark_fuzzy=True)
    entry = _entry(target.read_text(encoding="utf-8"), "Hello, %(name)s!")
    assert entry["comments"] == ["#: shop/views.py:12", "#, fuzzy, python-format"]


def test_profile_is_chosen_from_flags():
    assert profile_for_flags(("c-format",)).syntax_names == ("printf",)
    assert profile_for_flags(("python-format",)).syntax_names == ("python_percent", "printf")
    assert profile_for_flags(("python-brace-format",)).syntax_names == ("python_brace",)
    assert profile_for_flags(("qt-format",)).syntax_names == ("qt",)
    assert profile_for_flags(("fuzzy",)).syntax_names == ("python_percent", "printf")  # heuristic
    assert "printf" not in profile_for_flags(("no-c-format",)).syntax_names


def test_python_brace_doubled_braces_are_literal_text():
    profile = profile_for_flags(("python-brace-format",))
    assert [p.raw for p in extract("Use {{braces}} for {0} and {name!r:>10}", profile)] == ["{0}", "{name!r:>10}"]
    # The translation profile masks the field but sends "{{braces}}" as text.
    assert mask("Use {{braces}} for {0}", profile_for_path("locale/en/django.po")).text == "Use {{braces}} for ⟦0⟧"


def test_no_c_format_percent_is_literal():
    entry = _entry(SOURCE_PO, "100% satisfaction")
    assert check_value(entry, None, "100 % удовлетворения")[1] == []
    assert extract("100% satisfaction", profile_for_flags(("no-c-format",))) == []


def test_c_format_and_python_named_damage_is_found():
    entry = _entry(SOURCE_PO, "%1$s scored %2$d points")
    codes = {p.code for p in check_value(entry, None, "%1$с набрал %2$д очков")[1]}
    assert codes == {"missing", "corrupted"}

    entry = _entry(SOURCE_PO, "Hello, %(name)s!")
    problems = check_value(entry, None, "Привет, %(имя)s!")[1]
    assert [p.code for p in problems] == ["python_named_mismatch"]


def test_plural_forms_checked_against_plural_text_with_single_count_exemption():
    entry = _entry(SOURCE_PO, "One file")
    # German msgstr[0] is n = 1 only: the count may be spelled out.
    assert check_value(entry, 0, "Eine Datei", None, (2, "(n != 1)"))[1] == []
    # French msgstr[0] is n = 0 and 1, Russian msgstr[0] is 1, 21, 31 ...: the count must stay.
    assert [p.code for p in check_value(entry, 0, "Un fichier", None, (2, "(n > 1)"))[1]] == ["missing"]
    assert [p.code for p in check_value(entry, 0, "Один файл", None, RU_FORMS)[1]] == ["missing"]
    assert check_value(entry, 0, "%(counter)s файл", None, RU_FORMS)[1] == []


def test_plural_source_follows_target_plural_forms(tmp_path):
    source = tmp_path / "en.po"
    source.write_text(SOURCE_PO, encoding="utf-8")
    data = read_po_file(str(source))

    ru = expand_plural_source(str(source), data, "ru")
    assert [k for k in ru if k.startswith("One file")] == [plural_key("One file", i) for i in range(3)]
    # Every Russian form covers several counts, so all are translated from the plural text.
    assert {ru[plural_key("One file", i)] for i in range(3)} == {"%(counter)s files"}

    de = expand_plural_source(str(source), data, "de")
    assert de[plural_key("One file", 0)] == "One file"
    assert de[plural_key("One file", 1)] == "%(counter)s files"

    fr = expand_plural_source(str(source), data, "fr")  # msgstr[0] = 0 and 1
    assert fr[plural_key("One file", 0)] == "%(counter)s files"


# ---------------------------------------------------------------------------
# Write gate
# ---------------------------------------------------------------------------


def test_gate_writes_empty_msgstr_instead_of_damaged_value(tmp_path, capsys):
    target = tmp_path / "ru.po"
    target.write_text(SOURCE_PO.replace("Language: en", "Language: ru").replace(
        "Plural-Forms: nplurals=2; plural=(n != 1);", "Plural-Forms: " + RU_PLURAL
    ), encoding="utf-8")
    write_po_file(
        str(target),
        {
            "Hello, %(name)s!": "Привет, %(имя)s!",
            "%1$s scored %2$d points": "%1$s набрал %2$d очков",
            "Welcome {0}, use {{braces}} literally": "Добро пожаловать {0}, {скобки}",
            "100% satisfaction": "100% удовлетворения",
            plural_key("One file", 0): "Один файл",
            plural_key("One file", 1): "%(counter)s файла",
        },
    )
    data = read_po_file(str(target))
    assert data["Hello, %(name)s!"] == ""
    assert data["Welcome {0}, use {{braces}} literally"] == ""
    assert data[plural_key("One file", 0)] == ""
    assert data["%1$s scored %2$d points"] == "%1$s набрал %2$d очков"
    assert data["100% satisfaction"] == "100% удовлетворения"
    assert data[plural_key("One file", 1)] == "%(counter)s файла"
    out = capsys.readouterr().out
    assert "not writing 'Hello, %(name)s!'" in out and "One file::msgstr[0]" in out


# ---------------------------------------------------------------------------
# Translation end to end
# ---------------------------------------------------------------------------

_LATIN_TO_CYRILLIC = str.maketrans(dict(zip("sdcSDabeiklmnoprtuvxyz", "сдсСДабеиклмнопртувхйз")))


def transliterate(text: str) -> str:
    """What the model did for uz-Cyrl: every Latin letter becomes Cyrillic (tokens survive)."""
    return text.translate(_LATIN_TO_CYRILLIC)


def _fake_client(sent):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append((list(texts), list(kwargs.get("contexts") or [])))
        return [transliterate(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    return client


LANGUAGES = ["en", "ru", "de", "fr", {"uz-Cyrl": "uz_Cyrl"}]


def _project(tmp_path, monkeypatch, languages=LANGUAGES):
    source = tmp_path / "locale" / "en" / "LC_MESSAGES" / "django.po"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE_PO, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": languages,
                "source_files": {
                    "locale/en/LC_MESSAGES/django.po": {
                        "destination_path": "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
                    }
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return lambda locale: tmp_path / "locale" / locale / "LC_MESSAGES" / "django.po"


def _translate_all(target_path, sent, languages=("ru", "de", "fr", "uz-Cyrl")):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        for language in languages:
            translate_command.execute(language=language, force="__all__")


EXPECTED_FORMS = {"ru": 3, "de": 2, "fr": 2, "uz_Cyrl": 2}


def test_translate_never_writes_a_transliterated_placeholder(tmp_path, monkeypatch):
    target_path = _project(tmp_path, monkeypatch)
    sent = []
    _translate_all(target_path, sent)

    for locale, nplurals in EXPECTED_FORMS.items():
        path = target_path(locale)
        raw = path.read_text(encoding="utf-8")
        data = read_po_file(str(path))
        assert f"nplurals={nplurals};" in raw and f"Language: {locale}" in raw
        assert "%(name)s" in data["Hello, %(name)s!"]
        assert "%1$s" in data["%1$s scored %2$d points"] and "%2$d" in data["%1$s scored %2$d points"]
        assert "{0}" in data["Welcome {0}, use {{braces}} literally"]
        assert "{{" in data["Welcome {0}, use {{braces}} literally"]
        assert data["100% satisfaction"].startswith("100%")
        for msgid in ("%(counter)s item in your cart", "One file"):
            forms = [data[plural_key(msgid, i)] for i in range(nplurals)]
            assert len([k for k in data if k.startswith(msgid + "::")]) == nplurals
            for i, text in enumerate(forms):
                if (msgid, i) == ("One file", 0) and locale in ("de", "uz_Cyrl"):
                    assert "%" not in text  # n = 1 only: "One file"
                else:
                    assert "%(counter)s" in text, (locale, msgid, i, text)
        # Every flag line of the source is in the target, unchanged.
        assert raw.count("#, python-format") == 3
        assert "#, c-format" in raw and "#, python-brace-format" in raw and "#, no-c-format" in raw
        # Every value matches its entry's syntax (the same check 'algebras placeholders' runs).
        assert po_format.check_file(
            str(target_path("en")), str(path), "en", locale.replace("_", "-")
        ) == []

    # The model never saw a raw placeholder, and plural forms had their notes.
    assert not any("%(" in t or "%1$" in t or "{0}" in t for texts, _ in sent for t in texts)
    assert any(c and "gettext plural form msgstr[2]" in c for _, contexts in sent for c in contexts)


@needs_msgfmt
def test_translated_files_pass_msgfmt_check_format(tmp_path, monkeypatch):
    target_path = _project(tmp_path, monkeypatch)
    _translate_all(target_path, [])
    for locale in EXPECTED_FORMS:
        msgfmt_check(target_path(locale))


def test_lost_placeholder_leaves_the_entry_empty(tmp_path, monkeypatch):
    target_path = _project(tmp_path, monkeypatch, ["en", "ru"])
    client = MagicMock()
    # A model that always drops the second token of the c-format string.
    client.translate_batch.side_effect = lambda texts, *a, **k: [
        t.replace(" ⟦1⟧", "") if "scored" in t else transliterate(t) for t in texts
    ]
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=client):
        translate_command.execute(language="ru", force="__all__")

    data = read_po_file(str(target_path("ru")))
    assert data["%1$s scored %2$d points"] == ""  # gettext falls back to the source
    assert "%(name)s" in data["Hello, %(name)s!"]


def test_translate_missing_keys_in_place_keeps_layout(tmp_path, monkeypatch):
    target_path = _project(tmp_path, monkeypatch, ["en", "ru"])
    target = target_path("ru")
    target.parent.mkdir(parents=True)
    existing = (
        SOURCE_PO.replace("Language: en", "Language: ru")
        .replace("Plural-Forms: nplurals=2; plural=(n != 1);", "Plural-Forms: " + RU_PLURAL)
        .replace("#: shop/views.py:12", "#  translator note\n#: shop/views.py:12")
        .replace('msgstr "Hello, %(name)s!"', 'msgstr "Привет, %(name)s!"')
    )
    # Untranslated target: every value empty except the greeting.
    lines = []
    for line in existing.split("\n"):
        if line.startswith("msgstr") and "Привет" not in line and not line.startswith('msgstr ""'):
            line = line.split(" ", 1)[0] + ' ""'
        lines.append(line)
    existing = "\n".join(lines)
    target.write_text(existing, encoding="utf-8")

    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        translate_command.execute(language="ru", only_missing=True)

    data = read_po_file(str(target))
    assert data["Hello, %(name)s!"] == "Привет, %(name)s!"  # untouched
    assert [data[plural_key("One file", i)].startswith("%(counter)s") for i in range(3)] == [True] * 3
    written = target.read_text(encoding="utf-8")
    assert written.split("\n")[:12] == existing.split("\n")[:12]  # header and comments as they were
    assert not any("Hello" in t for texts, _ in sent for t in texts)


# ---------------------------------------------------------------------------
# 'algebras placeholders'
# ---------------------------------------------------------------------------

CORRUPTED_RU = (
    SOURCE_PO.replace("Language: en", "Language: ru")
    .replace("Plural-Forms: nplurals=2; plural=(n != 1);", "Plural-Forms: " + RU_PLURAL)
    .replace('msgstr "Hello, %(name)s!"', 'msgstr "Привет, %(имя)s!"')
    .replace(
        'msgstr[0] "%(counter)s item in your cart"\nmsgstr[1] "%(counter)s items in your cart"',
        'msgstr[0] "%(counter)с товар в корзине"\n'
        'msgstr[1] "%(counter)s товара в корзине"\n'
        'msgstr[2] "%(counter)s товаров в корзине"',
    )
    .replace(
        'msgstr[0] "One file"\nmsgstr[1] "%(counter)s files"',
        'msgstr[0] "%(counter)s файл"\nmsgstr[1] "%(counter)s файла"\nmsgstr[2] "%(counter)s файлов"',
    )
    .replace('msgstr "%1$s scored %2$d points"', 'msgstr "%1$с набрал %2$д очков"')
    .replace(
        'msgstr "Welcome {0}, use {{braces}} literally"',
        'msgstr "Добро пожаловать, {0}, пишите {{braces}} буквально"',
    )
    .replace('msgstr "100% satisfaction"', 'msgstr "100% удовлетворения"')
)

EXPECTED_FIXED = (
    CORRUPTED_RU.replace("%(имя)s", "%(name)s")
    .replace("%(counter)с", "%(counter)s")
    .replace("%1$с", "%1$s")
    .replace("%2$д", "%2$d")
)


@pytest.fixture
def ru_project(tmp_path, monkeypatch):
    target_path = _project(tmp_path, monkeypatch, ["en", "ru"])
    target = target_path("ru")
    target.parent.mkdir(parents=True)
    target.write_text(CORRUPTED_RU, encoding="utf-8")
    return target


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_exact_codes(ru_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    problems = {i["key"]: sorted(p["code"] for p in i["problems"]) for i in report["issues"]}
    assert problems == {
        "Hello, %(name)s!": ["python_named_mismatch"],
        plural_key("%(counter)s item in your cart", 0): ["corrupted", "missing"],
        "%1$s scored %2$d points": ["corrupted", "corrupted", "missing", "missing"],
    }
    assert all(i["fixed"] is not None for i in report["issues"])


def test_fix_repairs_in_place_and_is_idempotent(ru_project, capsys):
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert {i["status"] for i in report["issues"]} == {"fixed"}
    assert ru_project.read_text(encoding="utf-8") == EXPECTED_FIXED

    code, report = _report(capsys)
    assert (code, report["issues"]) == (0, [])

    code, report = _report(capsys, fix=True)
    assert code == 0
    assert ru_project.read_text(encoding="utf-8") == EXPECTED_FIXED


def test_dry_run_writes_nothing(ru_project, capsys):
    _report(capsys, fix=True, dry_run=True)
    assert ru_project.read_text(encoding="utf-8") == CORRUPTED_RU


def test_single_count_form_may_spell_out_the_number(tmp_path):
    source = tmp_path / "en.po"
    source.write_text(SOURCE_PO, encoding="utf-8")
    de = tmp_path / "de.po"
    de.write_text(SOURCE_PO.replace('msgstr[0] "One file"', 'msgstr[0] "Eine Datei"'), encoding="utf-8")
    assert po_format.check_file(str(source), str(de), "en", "de") == []

    ru = tmp_path / "ru.po"
    ru.write_text(EXPECTED_FIXED.replace('msgstr[0] "%(counter)s файл"', 'msgstr[0] "Один файл"'), encoding="utf-8")
    findings = po_format.check_file(str(source), str(ru), "en", "ru")
    assert [(f.key, [p.code for p in f.problems]) for f in findings] == [
        (plural_key("One file", 0), ["missing"])
    ]


@needs_msgfmt
def test_check_agrees_with_msgfmt(ru_project, capsys):
    with pytest.raises(AssertionError):
        msgfmt_check(ru_project)  # msgfmt rejects the corrupted file too
    _report(capsys, fix=True)
    msgfmt_check(ru_project)
