"""
Android resource folders need Android qualifiers, not raw BCP-47 codes: Android ignores
values-uz-Cyrl and values-pt-BR, but reads values-b+uz+Cyrl and values-pt-rBR.
"""

import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, status_command, translate_command
from algebras.commands.healthcheck_command import find_source_file, iter_file_pairs
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils import path_utils
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.path_utils import (
    android_qualifier,
    determine_target_path,
    locale_from_android_qualifier,
    match_android_qualifier,
    resolve_destination_path,
)

ANDROID = "res/values-%algebras_locale_code%/strings.xml"


@pytest.fixture(autouse=True)
def fresh_warnings():
    path_utils._warned_legacy_folders.clear()
    yield
    path_utils._warned_legacy_folders.clear()


@pytest.mark.parametrize(
    "code,qualifier",
    [
        ("ru", "ru"),
        ("RU", "ru"),
        ("pt-BR", "pt-rBR"),
        ("pt_BR", "pt-rBR"),
        ("pt-br", "pt-rBR"),
        ("zh-CN", "zh-rCN"),
        ("zh-Hans", "b+zh+Hans"),
        ("zh_hans", "b+zh+Hans"),
        ("zh-Hans-CN", "b+zh+Hans+CN"),
        ("sr-Latn", "b+sr+Latn"),
        ("uz-Cyrl", "b+uz+Cyrl"),
        ("uz_Cyrl", "b+uz+Cyrl"),
        # The legacy "-rYY" form only takes two letters; a numeric region needs "b+".
        ("es-419", "b+es+419"),
        ("ca-ES-valencia", "b+ca+ES+valencia"),
        # Already qualifiers
        ("b+uz+Cyrl", "b+uz+Cyrl"),
        ("pt-rBR", "pt-rBR"),
    ],
)
def test_android_qualifier(code, qualifier):
    assert android_qualifier(code) == qualifier
    assert resolve_destination_path(ANDROID, code) == f"res/values-{qualifier}/strings.xml"


@pytest.mark.parametrize(
    "qualifier,languages,expected",
    [
        ("b+uz+Cyrl", ["en", "uz-Cyrl"], "uz-Cyrl"),
        ("b+uz+Cyrl", ["en", "uz_Cyrl"], "uz_Cyrl"),
        ("pt-rBR", ["en", "pt-BR"], "pt-BR"),
        ("b+pt+BR", ["en", "pt_BR"], "pt_BR"),
        ("zh-rCN", ["en", "zh-CN"], "zh-CN"),
        ("b+zh+Hans+CN", ["en", "zh-Hans-CN"], "zh-Hans-CN"),
        ("b+es+419", ["en", "es-419"], "es-419"),
        ("ru", ["en", "ru"], "ru"),
        ("b+uz+Cyrl", ["en", "uz-Latn"], None),
    ],
)
def test_reverse_lookup(qualifier, languages, expected):
    assert match_android_qualifier(qualifier, languages) == expected


def test_locale_from_android_qualifier():
    assert locale_from_android_qualifier("b+sr+Latn") == "sr-Latn"
    assert locale_from_android_qualifier("pt-rBR") == "pt-BR"
    assert locale_from_android_qualifier("de") == "de"


@pytest.mark.parametrize(
    "pattern",
    [
        "locales/%algebras_locale_code%/common.json",
        "locales/%algebras_locale_code%.json",
        "res/%algebras_locale_code%/strings.xml",  # .xml but not a values- folder
        "locale/%algebras_locale_code%/LC_MESSAGES/django.po",
    ],
)
def test_non_android_paths_use_the_code_unchanged(pattern):
    for code in ("pt-BR", "uz-Cyrl", "zh_Hans"):
        assert resolve_destination_path(pattern, code) == pattern.replace("%algebras_locale_code%", code)


def _config(tmp_path, languages, source_files=None):
    path = tmp_path / ".algebras.config"
    path.write_text(
        json.dumps({"languages": languages, "source_files": source_files or {}, "api": {"provider": "algebras-ai"}}),
        encoding="utf-8",
    )
    config = Config(str(path))
    config.load()
    return config


def test_config_mapping_takes_precedence(tmp_path):
    config = _config(tmp_path, ["en", {"uz-Cyrl": "b+uz+Cyrl"}, {"pt-BR": "pt-BR"}, {"sr-Latn": "sr"}, "zh-Hans"])
    assert resolve_destination_path(ANDROID, "uz-Cyrl", config) == "res/values-b+uz+Cyrl/strings.xml"
    assert resolve_destination_path(ANDROID, "sr-Latn", config) == "res/values-sr/strings.xml"
    # Unmapped languages still get a qualifier
    assert resolve_destination_path(ANDROID, "zh-Hans", config) == "res/values-b+zh+Hans/strings.xml"
    # A mapping applies to non-Android paths too, unchanged
    assert resolve_destination_path("locales/%algebras_locale_code%.json", "sr-Latn", config) == "locales/sr.json"


def test_determine_target_path_uses_android_qualifier():
    # determine_target_path builds an OS path (backslashes on Windows)
    norm = os.path.normpath
    assert norm(determine_target_path("res/values/strings.xml", "en", "pt-BR")) == norm("res/values-pt-rBR/strings.xml")
    assert norm(determine_target_path("res/values-en/strings.xml", "en", "uz-Cyrl")) == norm("res/values-b+uz+Cyrl/strings.xml")
    assert norm(determine_target_path("res/values/strings.xml", "en", "ru")) == norm("res/values-ru/strings.xml")


SOURCE = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="hello">Hello %1$s!</string>
    <string name="bye">Goodbye</string>
</resources>
"""


@pytest.fixture
def android_project(tmp_path, monkeypatch):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values" / "strings.xml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "uz-Cyrl", "pt-BR"],
                "source_files": {"res/values/strings.xml": {"destination_path": ANDROID}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return tmp_path


def _fake_client():
    client = MagicMock()
    client.translate_batch.side_effect = lambda texts, *a, **k: [f"[T] {t}" for t in texts]
    return client


def _translate_all(project):
    cache = MagicMock()
    cache.get.return_value = None
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client()), patch(
        "algebras.services.translator.TranslationCache", return_value=cache
    ):
        for language in ("uz-Cyrl", "pt-BR"):
            translate_command.execute(language=language, force="__all__")


def test_translate_writes_android_qualified_folders(android_project):
    _translate_all(android_project)

    res = android_project / "res"
    assert sorted(p.name for p in res.iterdir()) == ["values", "values-b+uz+Cyrl", "values-pt-rBR"]
    for folder in ("values-b+uz+Cyrl", "values-pt-rBR"):
        data = read_android_xml_file(str(res / folder / "strings.xml"))
        assert data["bye"] == "[T] Goodbye"
        assert "%1$s" in data["hello"]


def test_status_and_placeholders_pair_qualified_folders(android_project, capsys):
    _translate_all(android_project)
    capsys.readouterr()

    config = Config()
    config.load()
    files = FileScanner(config=config).group_files_by_language()
    assert [Path(f).as_posix() for f in files["uz-Cyrl"]] == ["res/values-b+uz+Cyrl/strings.xml"]
    assert [Path(f).as_posix() for f in files["pt-BR"]] == ["res/values-pt-rBR/strings.xml"]
    for lang, folder in (("uz-Cyrl", "values-b+uz+Cyrl"), ("pt-BR", "values-pt-rBR")):
        pairs = [(Path(s).as_posix(), Path(t).as_posix()) for s, t in iter_file_pairs(config, "en", lang, files)]
        assert pairs == [("res/values/strings.xml", f"res/{folder}/strings.xml")]

    status_command.execute()
    out = capsys.readouterr().out
    for lang in ("uz-Cyrl", "pt-BR"):
        line = next(l for l in out.splitlines() if l.startswith(f"{lang}:"))
        assert "2/2 keys (100.0%)" in line and "1/1 files (100.0%)" in line, line

    code = placeholders_command.execute(output_format="json")
    report = json.loads(capsys.readouterr().out)
    assert report["files_checked"] == 2
    assert report["issues"] == []
    assert code == 0


@pytest.fixture
def scanner_project(tmp_path, monkeypatch):
    """No source_files: the scanner finds the folders and has to map them back to languages."""
    for folder in ("values", "values-b+uz+Cyrl", "values-pt-rBR", "values-ru"):
        (tmp_path / "res" / folder).mkdir(parents=True)
        (tmp_path / "res" / folder / "strings.xml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps({"languages": ["en", "uz-Cyrl", "pt_BR", "ru"], "api": {"provider": "algebras-ai"}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_scanner_maps_qualified_folders_to_languages(scanner_project):
    config = Config()
    config.load()
    files = FileScanner(config=config).group_files_by_language()
    assert [Path(f).as_posix() for f in files["uz-Cyrl"]] == ["res/values-b+uz+Cyrl/strings.xml"]
    assert [Path(f).as_posix() for f in files["pt_BR"]] == ["res/values-pt-rBR/strings.xml"]
    assert [Path(f).as_posix() for f in files["ru"]] == ["res/values-ru/strings.xml"]

    source = files["en"]
    assert find_source_file(files["uz-Cyrl"][0], source, "en", "uz-Cyrl") == source[0]
    pairs = list(iter_file_pairs(config, "en", "pt_BR", files))
    assert [(Path(s).as_posix(), Path(t).as_posix()) for s, t in pairs] == [
        ("res/values/strings.xml", "res/values-pt-rBR/strings.xml")
    ]


def test_legacy_folder_gets_a_rename_warning(android_project, capsys):
    legacy = android_project / "res" / "values-uz-Cyrl"
    legacy.mkdir()
    (legacy / "strings.xml").write_text(SOURCE, encoding="utf-8")

    config = Config()
    config.load()
    FileScanner(config=config).group_files_by_language()
    FileScanner(config=config).group_files_by_language()
    err = capsys.readouterr().err
    warnings = [line for line in err.splitlines() if "values-uz-Cyrl" in line]
    assert len(warnings) == 1
    assert "values-b+uz+Cyrl" in warnings[0]
    assert legacy.exists() and not (android_project / "res" / "values-b+uz+Cyrl").exists()


def test_legacy_folder_warning_in_scanner_mode(tmp_path, monkeypatch, capsys):
    for folder in ("values", "values-pt-BR"):
        (tmp_path / "res" / folder).mkdir(parents=True)
        (tmp_path / "res" / folder / "strings.xml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(json.dumps({"languages": ["en", "pt-BR"]}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    config = Config()
    config.load()
    files = FileScanner(config=config).group_files_by_language()
    assert [Path(f).as_posix() for f in files["pt-BR"]] == ["res/values-pt-BR/strings.xml"]
    err = capsys.readouterr().err
    assert "values-pt-BR" in err and "values-pt-rBR" in err


def test_no_warning_without_legacy_folder_or_with_mapping(tmp_path, monkeypatch, capsys):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values" / "strings.xml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "res" / "values-uz-Cyrl").mkdir()
    (tmp_path / "res" / "values-uz-Cyrl" / "strings.xml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", {"uz-Cyrl": "uz-Cyrl-custom"}, "ru"],
                "source_files": {"res/values/strings.xml": {"destination_path": ANDROID}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config = Config()
    config.load()
    FileScanner(config=config).group_files_by_language()
    assert "Warning" not in capsys.readouterr().err
