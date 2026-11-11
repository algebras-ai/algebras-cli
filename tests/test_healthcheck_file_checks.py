"""
healthcheck uses each format's registered file check (the one 'algebras placeholders' runs), so the
per-entry PO syntax and the .properties MessageFormat checks are reported by both commands.
"""

import json

from algebras.commands import healthcheck_command, placeholders_command

SOURCE_PO = r"""msgid ""
msgstr ""
"Language: en\n"

#, python-format
msgid "Hello, %(name)s!"
msgstr "Hello, %(name)s!"

#, no-c-format
msgid "100% sure"
msgstr "100% sure"
"""

TARGET_PO = SOURCE_PO.replace("Language: en", "Language: ru").replace(
    'msgstr "Hello, %(name)s!"', 'msgstr "Привет, %(имя)s!"'
).replace('msgstr "100% sure"', 'msgstr "100% уверен"')

SOURCE_PROPERTIES = "msg=It''s {0} files\nplain=Hello\n"
TARGET_PROPERTIES = "msg={0} fichiers, c'est tout\nplain=Bonjour\n"


def _project(tmp_path, monkeypatch):
    (tmp_path / "locale").mkdir()
    (tmp_path / "locale" / "en.po").write_text(SOURCE_PO, encoding="utf-8")
    (tmp_path / "locale" / "ru.po").write_text(TARGET_PO, encoding="utf-8")
    (tmp_path / "messages.properties").write_text(SOURCE_PROPERTIES, encoding="utf-8")
    (tmp_path / "messages_ru.properties").write_text(TARGET_PROPERTIES, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {
                    "locale/en.po": {"destination_path": "locale/%algebras_locale_code%.po"},
                    "messages.properties": {"destination_path": "messages_%algebras_locale_code%.properties"},
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)


def _healthcheck(capsys):
    capsys.readouterr()
    code = healthcheck_command.execute(output_format="json")
    out = capsys.readouterr().out
    report = json.loads(out[out.index("{"):])
    return code, {
        (f["file"], i["key"]): i["message"]
        for f in report["files"]
        for i in f["issues"]
        if i["category"] == "placeholders"
    }


def test_healthcheck_reports_po_entry_and_properties_messageformat_findings(tmp_path, monkeypatch, capsys):
    _project(tmp_path, monkeypatch)
    code, found = _healthcheck(capsys)
    assert code == 1
    # PO: the entry's own syntax (python-format) -> one renamed-placeholder finding; the
    # no-c-format entry's "100%" is not a placeholder.
    assert "Placeholder name changed" in found[("locale/ru.po", "Hello, %(name)s!")]
    assert ("locale/ru.po", "100% sure") not in found
    # .properties MessageFormat: a single apostrophe Java would drop.
    assert "apostrophe" in found[("messages_ru.properties", "msg")]
    assert set(found) == {("locale/ru.po", "Hello, %(name)s!"), ("messages_ru.properties", "msg")}

    # 'algebras placeholders' reports the same keys.
    capsys.readouterr()
    placeholders_command.execute(output_format="json")
    report = json.loads(capsys.readouterr().out)
    assert {(i["target_file"], i["key"]) for i in report["issues"]} == set(found)
    codes = {i["key"]: [p["code"] for p in i["problems"]] for i in report["issues"]}
    assert codes == {"Hello, %(name)s!": ["python_named_mismatch"], "msg": ["mf_apostrophe"]}
