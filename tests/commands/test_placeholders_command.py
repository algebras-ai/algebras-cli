"""
'algebras placeholders': check, --fix (with a registered writer), --dry-run, --retranslate, exit codes.
"""

import json
import os
from unittest.mock import patch

import pytest

from algebras.commands import placeholders_command
from algebras.services.placeholders.fix_writers import register_fix_writer, unregister_fix_writer

SOURCE_XML = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="PhoneRegistration.code_disclaimer">We sent a code to %1$s. Resend in %2$d s</string>
    <string name="Quiz.remaining_questions_format">%1$d of %2$d questions left</string>
    <string name="ok">OK</string>
    <plurals name="Quiz.points">
        <item quantity="one">%1$d point</item>
        <item quantity="other">%1$d points</item>
    </plurals>
</resources>
"""

TARGET_XML = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="PhoneRegistration.code_disclaimer">Код %1$с рақамига юборилди. %2$д сониядан сўнг</string>
    <string name="Quiz.remaining_questions_format">%2$д тадан %1$д савол қолди</string>
    <string name="ok">ОК</string>
    <plurals name="Quiz.points">
        <item quantity="one">%1$д очко</item>
        <item quantity="other">%1$д очко</item>
    </plurals>
</resources>
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values-uz").mkdir(parents=True)
    (tmp_path / "res" / "values" / "generic_strings.xml").write_text(SOURCE_XML, encoding="utf-8")
    (tmp_path / "res" / "values-uz" / "generic_strings.xml").write_text(TARGET_XML, encoding="utf-8")
    (tmp_path / "loc" / "en").mkdir(parents=True)
    (tmp_path / "loc" / "uz").mkdir(parents=True)
    (tmp_path / "loc" / "en" / "common.json").write_text(
        json.dumps({"hello": "Hi {{name}}", "lost": "%1$s and %2$s", "fine": {"x": "Bye %s"}}), encoding="utf-8"
    )
    (tmp_path / "loc" / "uz" / "common.json").write_text(
        json.dumps({"hello": "Салом {{ исм }}", "lost": "ва", "fine": {"x": "Хайр %s"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "uz"],
                "source_files": {
                    "res/values/generic_strings.xml": {
                        "destination_path": "res/values-%algebras_locale_code%/generic_strings.xml"
                    },
                    "loc/en/common.json": {"destination_path": "loc/%algebras_locale_code%/common.json"},
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def recording_writer():
    written = {}

    def writer(target_file, fixes, language, config):
        written.setdefault(target_file, {}).update(fixes)

    register_fix_writer([".xml", ".json"], writer)
    yield written
    unregister_fix_writer([".xml", ".json"])


def test_check_reports_client_case_and_exits_1(project, capsys):
    assert placeholders_command.execute() == 1
    out = capsys.readouterr().out
    assert "PhoneRegistration.code_disclaimer" in out
    assert "Quiz.points.__plurals__.one" in out
    assert "%1$с" in out
    assert "auto-fix: Код %1$s рақамига юборилди. %2$d сониядан сўнг" in out
    assert "fine.x" not in out and ".ok" not in out


def test_json_output(project, capsys):
    placeholders_command.execute(output_format="json")
    report = json.loads(capsys.readouterr().out)
    keys = {i["key"]: i for i in report["issues"]}
    assert set(keys) == {
        "PhoneRegistration.code_disclaimer",
        "Quiz.remaining_questions_format",
        "Quiz.points.__plurals__.one",
        "Quiz.points.__plurals__.other",
        "hello",
        "lost",
    }
    assert keys["Quiz.remaining_questions_format"]["fixed"] == "%2$d тадан %1$d савол қолди"
    assert keys["lost"]["fixed"] is None
    assert report["files_checked"] == 2


def test_clean_project_exits_0(project, capsys):
    target = project / "res" / "values-uz" / "generic_strings.xml"
    target.write_text(SOURCE_XML, encoding="utf-8")
    (project / "loc" / "uz" / "common.json").write_text(
        json.dumps({"hello": "Hi {{name}}", "lost": "%1$s, %2$s", "fine": {"x": "Bye %s"}}), encoding="utf-8"
    )
    assert placeholders_command.execute() == 0


def test_fix_writes_only_repairable_values(project, recording_writer, capsys):
    code = placeholders_command.execute(fix=True)
    assert code == 2  # "lost" cannot be repaired without retranslation
    xml_fixes = recording_writer[os.path.join("res", "values-uz", "generic_strings.xml")]
    assert xml_fixes[("PhoneRegistration.code_disclaimer",)] == "Код %1$s рақамига юборилди. %2$d сониядан сўнг"
    assert xml_fixes[("Quiz.points.__plurals__", "one")] == "%1$d очко"
    assert len(xml_fixes) == 4
    json_fixes = recording_writer[os.path.join("loc", "uz", "common.json")]
    assert json_fixes == {("hello",): "Салом {{name}}"}
    out = capsys.readouterr().out
    assert "5 fixed" in out and "1 unresolved" in out


def test_fix_without_writer_reports_unsupported(project, capsys):
    assert placeholders_command.execute(fix=True) == 2
    assert "not available for some file formats" in capsys.readouterr().out


def test_dry_run_writes_nothing(project, recording_writer, capsys):
    before = (project / "res" / "values-uz" / "generic_strings.xml").read_text(encoding="utf-8")
    assert placeholders_command.execute(fix=True, dry_run=True) == 1
    assert recording_writer == {}
    assert (project / "res" / "values-uz" / "generic_strings.xml").read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert "Would fix 4 value(s)" in out
    assert "+ %1$d очко" in out


def test_retranslate_forces_unresolved_keys(project, recording_writer):
    with patch("algebras.commands.translate_command.execute") as translate:
        placeholders_command.execute(fix=True, retranslate=True)
    translate.assert_called_once()
    assert translate.call_args.kwargs["language"] == "uz"
    assert translate.call_args.kwargs["force"] == ["lost"]


def test_unknown_language(project, capsys):
    assert placeholders_command.execute(languages=["xx"]) == 1


def test_language_filter(project, capsys):
    assert placeholders_command.execute(languages=["uz"]) == 1


def test_force_key_uses_plural_group():
    assert placeholders_command._force_key(("Quiz.points.__plurals__", "one"), {"Quiz.points.__plurals__": {}}) == (
        "Quiz.points.__plurals__"
    )
    assert placeholders_command._force_key(("a", "b"), {"a": "text"}) == "a.b"


def test_writer_failure_is_not_reported_as_fixed(project, capsys):
    def failing_writer(target_file, fixes, language, config):
        raise RuntimeError("not written, to keep its images/charts")

    register_fix_writer([".xml", ".json"], failing_writer)
    try:
        assert placeholders_command.execute(fix=True) == 2
    finally:
        unregister_fix_writer([".xml", ".json"])
    captured = capsys.readouterr()
    assert "Could not write fixes" in captured.err
    import re

    summary = captured.out.split("Checked")[-1]
    assert not re.search(r"\b\d+ fixed\b", summary)
    assert re.search(r"\b\d+ unresolved\b", summary)
