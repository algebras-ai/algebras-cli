"""
Gettext msgctxt: the same msgid under two contexts is two entries, keyed "<msgctxt>\\x04<msgid>"
through reading, writing, translation (with the context sent as a translator note), 'status',
'algebras placeholders' and --force.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import po as po_format
from algebras.utils.lang_validator import validate_language_files
from algebras.utils.po_handler import entry_key, read_po_file, write_po_file, _parse_po_content

SOURCE_PO = r"""msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Language: en\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#. Button that opens a file
msgctxt "verb"
msgid "Open"
msgstr "Open"

#. Status of a shop
msgctxt "adjective"
msgid "Open"
msgstr "Open"

#, python-format
msgctxt "verb"
msgid "Delete %(name)s"
msgstr "Delete %(name)s"

#, python-format
msgctxt "noun"
msgid "Delete %(name)s"
msgstr "Delete %(name)s"

msgid "Close"
msgstr "Close"
"""

VERB = "verb\x04Open"
ADJ = "adjective\x04Open"
DEL_VERB = "verb\x04Delete %(name)s"
DEL_NOUN = "noun\x04Delete %(name)s"


@pytest.fixture(autouse=True)
def po_fix_writer():
    register_fix_writer([".po"], po_format.write_fixes)
    yield


def _fake_client(sent):
    """Translates "X" to "X-ru", tagged with the msgctxt it got as a note."""
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        contexts = list(kwargs.get("contexts") or [None] * len(texts))
        sent.append((list(texts), contexts))
        out = []
        for text, ctx in zip(texts, contexts):
            tag = ""
            for name in ("verb", "adjective", "noun"):
                if ctx and f"'{name}'" in ctx:
                    tag = f" ({name})"
            out.append(f"{text}-ru{tag}")
        return out

    client.translate_batch.side_effect = translate_batch
    return client


def _project(tmp_path, monkeypatch):
    source = tmp_path / "locale" / "en.po"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE_PO, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {"locale/en.po": {"destination_path": "locale/%algebras_locale_code%.po"}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return source, tmp_path / "locale" / "ru.po"


def _translate(sent, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        translate_command.execute(language="ru", **kwargs)


def test_reading_keys_entries_by_context(tmp_path):
    path = tmp_path / "en.po"
    path.write_text(SOURCE_PO, encoding="utf-8")
    data = read_po_file(str(path))
    assert set(data) == {VERB, ADJ, DEL_VERB, DEL_NOUN, "Close"}
    assert entry_key({"msgid": "Close", "msgctxt": ""}) == "Close"


def test_both_contexts_are_translated_and_written_independently(tmp_path, monkeypatch):
    _source, target = _project(tmp_path, monkeypatch)
    sent = []
    _translate(sent, force="__all__")

    data = read_po_file(str(target))
    assert data[VERB] == "Open-ru (verb)"
    assert data[ADJ] == "Open-ru (adjective)"
    assert data[DEL_VERB].endswith("(verb)") and "%(name)s" in data[DEL_VERB]
    assert data[DEL_NOUN].endswith("(noun)") and "%(name)s" in data[DEL_NOUN]
    assert data["Close"] == "Close-ru"

    entries = [e for e in _parse_po_content(target.read_text(encoding="utf-8")) if e["msgid"] == "Open"]
    assert [(e["msgctxt"], e["msgstr"]) for e in entries] == [
        ("verb", "Open-ru (verb)"),
        ("adjective", "Open-ru (adjective)"),
    ]
    # Every msgctxt went to the translator as a note; the entry without one got none.
    notes = {t: c for texts, contexts in sent for t, c in zip(texts, contexts)}
    assert "msgctxt" not in (notes["Close"] or "")
    assert sum(1 for texts, contexts in sent for c in contexts if c and "msgctxt" in c) == 4

    # Nothing is reported missing ('status' / missing-key detection).
    _valid, missing = validate_language_files(str(_source), str(target), "en", "ru")
    assert not missing


def test_missing_context_entry_is_detected_and_added(tmp_path, monkeypatch):
    source, target = _project(tmp_path, monkeypatch)
    target.write_text(
        SOURCE_PO.replace('Language: en', 'Language: ru')
        .replace('msgctxt "verb"\nmsgid "Open"\nmsgstr "Open"', 'msgctxt "verb"\nmsgid "Open"\nmsgstr "Открыть"')
        .replace('msgctxt "adjective"\nmsgid "Open"\nmsgstr "Open"\n\n', ""),
        encoding="utf-8",
    )
    _valid, missing = validate_language_files(str(source), str(target), "en", "ru")
    assert ADJ in missing and VERB not in missing

    _translate([], only_missing=True)
    data = read_po_file(str(target))
    assert data[VERB] == "Открыть"
    assert data[ADJ] == "Open-ru (adjective)"


def test_placeholders_check_fix_and_force_per_context(tmp_path, monkeypatch, capsys):
    _source, target = _project(tmp_path, monkeypatch)
    _translate([], force="__all__")
    text = target.read_text(encoding="utf-8")
    # Damage only the noun variant's placeholder.
    noun_line = 'msgstr "Delete %(name)s-ru (noun)"'
    assert noun_line in text
    target.write_text(text.replace(noun_line, 'msgstr "Delete %(имя)s-ru (noun)"'), encoding="utf-8")

    capsys.readouterr()
    code = placeholders_command.execute(output_format="json")
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert [i["key"] for i in report["issues"]] == [DEL_NOUN]

    code = placeholders_command.execute(output_format="json", fix=True)
    capsys.readouterr()
    assert code == 0
    data = read_po_file(str(target))
    assert data[DEL_NOUN] == "Delete %(name)s-ru (noun)"
    assert data[DEL_VERB] == "Delete %(name)s-ru (verb)"

    # --force on one context retranslates only that entry.
    target.write_text(
        target.read_text(encoding="utf-8").replace('"Open-ru (adjective)"', '"stale"').replace(
            '"Open-ru (verb)"', '"keep me"'
        ),
        encoding="utf-8",
    )
    _translate([], force=ADJ)
    data = read_po_file(str(target))
    assert data[ADJ] == "Open-ru (adjective)"
    assert data[VERB] == "keep me"


def test_file_without_msgctxt_is_unchanged(tmp_path):
    plain = 'msgid ""\nmsgstr ""\n"Language: ru\\n"\n\nmsgid "Open"\nmsgstr "Открыть"\n\nmsgid "Close"\nmsgstr ""\n'
    path = tmp_path / "ru.po"
    path.write_text(plain, encoding="utf-8")
    data = read_po_file(str(path))
    assert data == {"Open": "Открыть", "Close": ""}
    write_po_file(str(path), data)
    assert path.read_text(encoding="utf-8") == plain
    write_po_file(str(path), {"Close": "Закрыть"})
    assert read_po_file(str(path)) == {"Open": "Открыть", "Close": "Закрыть"}
