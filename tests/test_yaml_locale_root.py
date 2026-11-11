"""
Rails-style YAML locale files are rooted at their own locale: config/locales/en.yml has `en:`, the
translated ru.yml must have `ru:` (Rails merges files by root key, so `en:` inside ru.yml loads as
English). Translation writes the target's root, comparisons pair the roots (keys in source terms,
`en.greeting`), files written with the source root are migrated, and other YAML is left alone.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from algebras.commands import placeholders_command, translate_command
from algebras.commands.healthcheck_command import validate_file_pair
from algebras.commands.status_command import count_current_and_outdated_keys
from algebras.config import Config
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import yaml_format
from algebras.utils import lang_validator, yaml_locale_root
from algebras.utils.lang_validator import validate_language_files

SOURCE = """\
en:
  greeting: "Hello, %{name}!"
  farewell: Goodbye
  nav:
    home: Home
"""


@pytest.fixture(autouse=True)
def yaml_fix_writer():
    register_fix_writer([".yaml", ".yml"], yaml_format.write_fixes)
    yield


@pytest.fixture
def fake_api(monkeypatch):
    """Translates by prefixing 'RU ' (placeholder tokens kept); no cache, no network."""
    sent = []

    def translate_batch(self, texts, *args, **kwargs):
        sent.append(list(texts))
        return ["RU " + t for t in texts]

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate", lambda self, text, *a, **k: "RU " + text)
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return sent


def _project(tmp_path, monkeypatch, source_text=SOURCE, languages=("en", "ru"), source_rel="config/locales/en.yml",
             destination="config/locales/%algebras_locale_code%.yml"):
    source = tmp_path / source_rel
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_text, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": list(languages),
                "source_files": {source_rel: {"destination_path": destination}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return source


def _target(tmp_path, code="ru"):
    return tmp_path / "config" / "locales" / f"{code}.yml"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Writing the root
# ---------------------------------------------------------------------------


def test_full_translation_writes_the_target_root(tmp_path, monkeypatch, fake_api):
    _project(tmp_path, monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    data = _load(_target(tmp_path))
    assert list(data) == ["ru"]
    assert data["ru"]["greeting"] == "RU Hello, %{name}!"
    assert data["ru"]["nav"]["home"] == "RU Home"


def test_only_missing_adds_keys_under_the_target_root(tmp_path, monkeypatch, fake_api):
    _project(tmp_path, monkeypatch)
    target = _target(tmp_path)
    target.write_text("ru:\n  greeting: 'Привет, %{name}!'\n", encoding="utf-8")

    translate_command.execute(language="ru", only_missing=True)

    data = _load(target)
    assert list(data) == ["ru"]
    assert data["ru"] == {"greeting": "Привет, %{name}!", "farewell": "RU Goodbye", "nav": {"home": "RU Home"}}
    # Only the two missing values went to the API; the existing one was matched under ru:.
    assert sorted(t for batch in fake_api for t in batch) == ["Goodbye", "Home"]


def test_force_keys_are_named_in_source_terms(tmp_path, monkeypatch, fake_api):
    _project(tmp_path, monkeypatch)
    target = _target(tmp_path)
    target.write_text("ru:\n  greeting: old\n  farewell: Пока\n  nav:\n    home: Главная\n", encoding="utf-8")

    translate_command.execute(language="ru", force="en.greeting")

    assert _load(target) == {"ru": {"greeting": "RU Hello, %{name}!", "farewell": "Пока", "nav": {"home": "Главная"}}}


def test_target_rooted_at_the_source_locale_is_migrated(tmp_path, monkeypatch, fake_api, capsys):
    _project(tmp_path, monkeypatch)
    target = _target(tmp_path)
    target.write_text("en:\n  greeting: 'Привет, %{name}!'\n  nav:\n    home: Главная\n", encoding="utf-8")

    capsys.readouterr()
    translate_command.execute(language="ru", only_missing=True)
    out = capsys.readouterr().out

    assert _load(target) == {"ru": {"greeting": "Привет, %{name}!", "farewell": "RU Goodbye", "nav": {"home": "Главная"}}}
    assert fake_api == [["Goodbye"]]  # existing values were read as Russian, not retranslated
    notices = [line for line in out.splitlines() if "root key 'en:'" in line]
    assert len(notices) == 1 and "'ru:'" in notices[0]

    # Written once with the right root, there is nothing more to migrate.
    capsys.readouterr()
    translate_command.execute(language="ru", force="en.farewell")
    assert "root key 'en:'" not in capsys.readouterr().out


def test_locale_mapping_gives_the_root_and_path(tmp_path, monkeypatch, fake_api):
    _project(tmp_path, monkeypatch, languages=["en", {"pt_BR": "pt-BR"}])
    translate_command.execute(language="pt_BR", force="__all__")
    target = _target(tmp_path, "pt-BR")
    data = _load(target)
    assert list(data) == ["pt-BR"]

    # The mapped root is matched on the way back: nothing missing, nothing outdated.
    config = Config()
    config.load()
    source = str(tmp_path / "config" / "locales" / "en.yml")
    assert validate_language_files(source, str(target), "en", "pt_BR", config) == (True, set())
    assert count_current_and_outdated_keys(source, str(target), "en", "pt_BR", config) == (3, 0)


def test_root_code_falls_back_to_the_language_for_non_locale_mappings():
    config = MagicMock()
    config.get_destination_locale_code.side_effect = lambda lang: {"pt_BR": "pt-BR", "uz": "b+uz+Cyrl"}.get(lang, lang)
    assert yaml_locale_root.root_code("pt_BR", config) == "pt-BR"
    assert yaml_locale_root.root_code("uz", config) == "uz"
    assert yaml_locale_root.root_code("ru", None) == "ru"


# ---------------------------------------------------------------------------
# Comparing under the roots
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("root", ["ru", "en"])  # en: a file written by older versions
def test_missing_and_status_counts_pair_the_roots(tmp_path, monkeypatch, root):
    source = _project(tmp_path, monkeypatch)
    target = _target(tmp_path)
    target.write_text(f"{root}:\n  greeting: 'Привет, %{{name}}!'\n  farewell: ''\n  stale: Старое\n", encoding="utf-8")
    config = Config()
    config.load()

    valid, missing = validate_language_files(str(source), str(target), "en", "ru", config)
    assert (valid, missing) == (False, {"en.farewell", "en.nav", "en.nav.home"})
    # 1 translated (greeting); 1 key the source no longer has (stale).
    assert count_current_and_outdated_keys(str(source), str(target), "en", "ru", config) == (1, 1)

    issues, keys_checked, _, _ = validate_file_pair(str(source), str(target), "en", "ru", config, False)
    assert keys_checked == 1


def test_update_detection_pairs_the_roots_without_a_config(tmp_path):
    # update / healthcheck callers that know no languages still pair a Rails root with the target's.
    source = tmp_path / "en.yml"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "ru.yml"
    target.write_text("ru:\n  greeting: Привет\n  farewell: Пока\n", encoding="utf-8")
    assert validate_language_files(str(source), str(target)) == (False, {"en.nav", "en.nav.home"})


def test_outdated_keys_look_up_target_history_under_its_root(tmp_path, monkeypatch):
    source = tmp_path / "en.yml"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "ru.yml"
    target.write_text("ru:\n  greeting: Привет\n  farewell: Пока\n  nav:\n    home: Главная\n", encoding="utf-8")

    looked_up = {}

    def batch(path, keys):
        looked_up[path] = sorted(keys)
        date = "2024-01-02T00:00:00" if path == str(source) else "2024-01-01T00:00:00"
        return {k: date for k in keys}

    monkeypatch.setattr(lang_validator, "is_git_available", lambda: True)
    monkeypatch.setattr(lang_validator, "is_git_repository", lambda p: True)
    monkeypatch.setattr(lang_validator, "get_keys_last_modifications_batch", batch)

    has, keys = lang_validator.find_outdated_keys(str(source), str(target), "en", "ru")
    # (Mappings whose contents differ are compared too, as for any nested file.)
    assert has and keys >= {"en.greeting", "en.farewell", "en.nav.home"}
    assert all(k == "en" or k.startswith("en.") for k in keys)
    assert looked_up[str(target)] == sorted("ru" + k[len("en"):] for k in keys)


# ---------------------------------------------------------------------------
# 'algebras placeholders'
# ---------------------------------------------------------------------------


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def test_placeholders_fix_keeps_the_target_root(tmp_path, monkeypatch, capsys):
    _project(tmp_path, monkeypatch)
    target = _target(tmp_path)
    target.write_text("# ru\nru:\n  greeting: 'Привет, %{имя}!'\n  farewell: Пока\n", encoding="utf-8")

    code, report, _ = _report(capsys)
    assert code == 1
    assert [i["key"] for i in report["issues"]] == ["en.greeting"]

    code, report, _ = _report(capsys, fix=True)
    assert code == 0
    assert target.read_text(encoding="utf-8") == "# ru\nru:\n  greeting: 'Привет, %{name}!'\n  farewell: Пока\n"


def test_placeholders_fix_migrates_a_source_root(tmp_path, monkeypatch, capsys):
    _project(tmp_path, monkeypatch)
    target = _target(tmp_path)
    target.write_text("# ru\nen:\n  greeting: 'Привет, %{имя}!'\n  farewell: Пока\n", encoding="utf-8")

    code, report, err = _report(capsys, fix=True)
    assert code == 0
    assert [i["key"] for i in report["issues"]] == ["en.greeting"]
    assert target.read_text(encoding="utf-8") == "# ru\nru:\n  greeting: 'Привет, %{name}!'\n  farewell: Пока\n"
    assert "root key 'en:'" in err


# ---------------------------------------------------------------------------
# Other YAML is left alone
# ---------------------------------------------------------------------------

SEVERAL_TOP_LEVEL = "greeting: Hello\nnav:\n  home: Home\n"
NON_LOCALE_ROOT = "app:\n  greeting: Hello\n  nav:\n    home: Home\n"
OTHER_LOCALE_ROOT = "de:\n  greeting: Hello\n"  # a single locale key, but not the source's


@pytest.mark.parametrize("text", [SEVERAL_TOP_LEVEL, NON_LOCALE_ROOT, OTHER_LOCALE_ROOT])
def test_non_rails_yaml_keeps_its_structure(tmp_path, monkeypatch, fake_api, text):
    source = _project(tmp_path, monkeypatch, source_text=text, source_rel="locales/en.yml",
                      destination="locales/%algebras_locale_code%.yml")
    translate_command.execute(language="ru", force="__all__")
    target = tmp_path / "locales" / "ru.yml"
    data = _load(target)
    original = yaml.safe_load(text)
    assert list(data) == list(original)

    config = Config()
    config.load()
    assert yaml_locale_root.align_target(original, data, "en", "ru", config) is data
    assert validate_language_files(str(source), str(target), "en", "ru", config) == (True, set())


def test_non_rails_target_with_a_locale_like_key_is_not_renamed():
    source = {"greeting": "Hello", "nav": {"home": "Home"}}
    target = {"ru": {"greeting": "Привет"}}
    assert yaml_locale_root.align_target(source, target, "en", "ru") is target
    assert yaml_locale_root.reroot_for_target(source, source, "en", "ru") is source
