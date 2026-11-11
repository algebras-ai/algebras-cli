"""
Legacy mode (no `source_files`): a multi-language CSV / TSV is its own source and target, so
'algebras placeholders', healthcheck and status pair it with itself for every language column.
"""

import json

import pytest

from algebras.commands import healthcheck_command, placeholders_command, status_command
from algebras.config import Config
from algebras.services.file_scanner import FileScanner


@pytest.fixture
def legacy_project(tmp_path, monkeypatch):
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales" / "translations.csv").write_text(
        "key,en,ru\ngreet,Hello %s,Привет %д\nbye,Bye,\n", encoding="utf-8"
    )
    (tmp_path / "locales" / "glossary.csv").write_text("Record ID,en,ru\n1,cart,корзина\n", encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps({"languages": ["en", "ru", "de"], "api": {"provider": "algebras-ai"}}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ALGEBRAS_API_KEY", raising=False)
    config = Config()
    config.load()
    return config


def test_csv_is_paired_with_itself(legacy_project):
    files = FileScanner(config=legacy_project).group_files_by_language()
    csv = "locales/translations.csv"
    assert list(healthcheck_command.iter_file_pairs(legacy_project, "en", "ru", files)) == [(csv, csv)]
    assert list(healthcheck_command.iter_file_pairs(legacy_project, "en", "de", files)) == []  # no column


def test_placeholders_and_healthcheck_check_the_csv(legacy_project, capsys):
    capsys.readouterr()
    assert placeholders_command.execute(output_format="json") == 1
    report = json.loads(capsys.readouterr().out)
    assert report["files_checked"] == 1
    assert [p["code"] for p in report["issues"][0]["problems"]] == ["missing", "corrupted"]

    assert healthcheck_command.execute(language="ru", output_format="json") == 1
    out = capsys.readouterr().out
    health = json.loads(out[out.index("{"):])
    assert health["summary"]["files_checked"] == 1
    assert {i["key"] for f in health["files"] for i in f["issues"]} == {"greet"}


def test_status_counts_the_csv_columns(legacy_project, capsys):
    capsys.readouterr()
    status_command.execute(language="ru")
    out = capsys.readouterr().out
    assert "Source language: en (1 files)" in out
    assert "ru: 1/2 keys (50.0%) in 1/1 files (100.0%)" in out
