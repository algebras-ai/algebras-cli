"""
TypeScript: a source `…${x}…` template literal written as "…" or '…' in the target shows ${x} as
text. 'algebras placeholders' reports it (ts_template_quote_changed) and --fix re-quotes it with
backticks, keeping the substitutions evaluated.
"""

import json

import pytest

from algebras.commands import placeholders_command
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import typescript
from algebras.utils.ts_handler import read_ts_document

SOURCE = """\
export const en = {
  welcome: `Welcome back, ${user.name}!`,
  plain: `No substitutions`,
  saved: 'Saved',
};
"""

TARGET = """\
export const fr = {
  welcome: "Bon retour, ${user.name} !",
  plain: "Pas de substitution",
  saved: 'Enregistré',
};
"""


@pytest.fixture(autouse=True)
def ts_fix_writer():
    register_fix_writer([".ts"], typescript.write_fixes)
    yield


@pytest.fixture
def project(tmp_path, monkeypatch):
    source = tmp_path / "en.ts"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "fr.ts"
    target.write_text(TARGET, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "fr"],
                "source_files": {"en.ts": {"destination_path": "%algebras_locale_code%.ts"}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return target


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_quote_change_is_reported(project, capsys):
    code, report = _report(capsys)
    assert code == 1
    assert {i["key"]: [p["code"] for p in i["problems"]] for i in report["issues"]} == {
        "welcome": ["ts_template_quote_changed"]
    }
    assert report["issues"][0]["fixed"] == "Bon retour, ${user.name} !"


def test_fix_requotes_with_backticks(project, capsys):
    code, report = _report(capsys, fix=True)
    assert code == 0 and report["issues"][0]["status"] == "fixed"
    assert project.read_text(encoding="utf-8") == TARGET.replace(
        '"Bon retour, ${user.name} !"', "`Bon retour, ${user.name} !`"
    )
    literal = read_ts_document(str(project)).literals[("welcome",)]
    assert literal.quote == "`" and literal.substitutions == ("${user.name}",)

    code, report = _report(capsys)
    assert (code, report["issues"]) == (0, [])
