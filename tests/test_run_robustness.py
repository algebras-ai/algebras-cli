"""
Robustness of 'translate' / 'update': exit codes and the summary line, one bad file not stopping
the run, --force keys with commas, Android pairing in 'update', leaf-only outdated keys,
non-string values, one API language code on every path, and "Invalid language" answers.
"""

import json
import re
from unittest.mock import MagicMock

import pytest
import yaml
from click.testing import CliRunner

from algebras.cli import cli
from algebras.commands import placeholders_command, translate_command, update_command
from algebras.utils.lang_validator import find_outdated_keys, read_language_file

_TOKEN = re.compile(r"⟦\d+⟧")


def _ok_batch(self, texts, *args, **kwargs):
    return ["UZ " + t for t in texts]


@pytest.fixture
def api(monkeypatch):
    """Fake Algebras AI client: records what is sent; translates by prefixing 'UZ '."""
    calls = {"batch": [], "single": []}

    def translate_batch(self, texts, source_lang, target_lang, *args, **kwargs):
        calls["batch"].append({"texts": list(texts), "source": source_lang, "target": target_lang})
        return ["UZ " + t for t in texts]

    def translate(self, text, source_lang, target_lang, *args, **kwargs):
        calls["single"].append({"text": text, "source": source_lang, "target": target_lang})
        return "UZ " + text

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate", translate)
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return calls


def _project(tmp_path, monkeypatch, files, source_files, languages=("en", "uz")):
    for path, content in files.items():
        p = tmp_path / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": list(languages),
                "source_files": {src: {"destination_path": dst} for src, dst in source_files.items()},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


JSON_SOURCE = {"locales/en/common.json": "locales/%algebras_locale_code%/common.json"}


def _json_project(tmp_path, monkeypatch, data, target=None):
    files = {"locales/en/common.json": json.dumps(data)}
    if target is not None:
        files["locales/uz/common.json"] = json.dumps(target)
    return _project(tmp_path, monkeypatch, files, JSON_SOURCE)


def _run(*args):
    return CliRunner().invoke(cli, list(args), catch_exceptions=False)


# 1. Exit codes ---------------------------------------------------------------------------------


def test_exit_code_0_when_everything_is_translated(tmp_path, monkeypatch, api):
    _json_project(tmp_path, monkeypatch, {"a": "Hello", "b": "Hi {{name}}"})
    result = _run("translate", "-l", "uz", "--force")
    assert result.exit_code == 0, result.output
    assert "1 files OK, 0 files failed, 0 keys left out" in result.output


def test_exit_code_2_when_some_keys_are_left_out(tmp_path, monkeypatch, api):
    _json_project(tmp_path, monkeypatch, {"a": "Hello", "b": "Hi {{name}}"})
    # The model drops placeholder tokens: 'b' is rejected, 'a' is fine.
    monkeypatch.setattr(
        "algebras.services.api_client.AlgebrasAIClient.translate_batch",
        lambda self, texts, *a, **k: ["UZ " + _TOKEN.sub("", t) for t in texts],
    )
    result = _run("translate", "-l", "uz", "--force")
    assert result.exit_code == 2, result.output
    assert "1 files OK, 0 files failed, 1 keys left out" in result.output


def test_exit_code_1_when_a_file_fails(tmp_path, monkeypatch, api):
    _json_project(tmp_path, monkeypatch, {"a": "Hello", "b": "Bye"})

    def failing(self, texts, *a, **k):
        raise Exception("Error from Algebras AI API: 500 - server error")

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", failing)
    result = _run("translate", "-l", "uz", "--force")
    assert result.exit_code == 1, result.output
    assert "0 files OK, 1 files failed, 2 keys left out" in result.output


def test_exit_code_1_when_the_run_cannot_proceed(tmp_path, monkeypatch, api):
    monkeypatch.chdir(tmp_path)  # no config
    assert _run("translate").exit_code == 1
    assert _run("update").exit_code == 1


def test_exit_codes_are_in_help():
    for command in ("translate", "update"):
        output = _run(command, "--help").output
        assert "Exit codes:" in output and "left out" in output


# 2. One bad file does not stop the run ---------------------------------------------------------


def test_invalid_xml_source_fails_alone(tmp_path, monkeypatch, api):
    _project(
        tmp_path,
        monkeypatch,
        {
            "res/values/strings.xml": "<resources><string name='a'>Hello</string>",  # not closed
            "locales/en/common.json": json.dumps({"greeting": "Hello"}),
        },
        {
            "res/values/strings.xml": "res/values-%algebras_locale_code%/strings.xml",
            **JSON_SOURCE,
        },
    )
    result = _run("translate", "-l", "uz", "--force")
    assert result.exit_code == 1, result.output
    assert json.loads((tmp_path / "locales/uz/common.json").read_text())["greeting"] == "UZ Hello"
    assert "strings.xml" in result.output and "✗" in result.output
    assert "Traceback" not in result.output
    assert "1 files OK, 1 files failed" in result.output


# 3. --force keys with commas -------------------------------------------------------------------


def _force_project(tmp_path, monkeypatch):
    source = {"Hello, world": "Hello, world", "x": "X", "y": "Y"}
    _json_project(tmp_path, monkeypatch, source, target={k: "old" for k in source})
    return tmp_path / "locales/uz/common.json"


def test_force_key_containing_a_comma(tmp_path, monkeypatch, api):
    target = _force_project(tmp_path, monkeypatch)
    assert _run("translate", "-l", "uz", "--force", "Hello, world").exit_code == 0
    assert json.loads(target.read_text()) == {"Hello, world": "UZ Hello, world", "x": "old", "y": "old"}


def test_force_repeated_and_comma_form(tmp_path, monkeypatch, api):
    target = _force_project(tmp_path, monkeypatch)
    assert _run("translate", "-l", "uz", "--force", "x", "--force", "Hello, world").exit_code == 0
    assert json.loads(target.read_text()) == {"Hello, world": "UZ Hello, world", "x": "UZ X", "y": "old"}

    target.write_text(json.dumps({"Hello, world": "old", "x": "old", "y": "old"}))
    assert _run("translate", "-l", "uz", "--force", "x,y").exit_code == 0  # backwards compatible
    assert json.loads(target.read_text()) == {"Hello, world": "old", "x": "UZ X", "y": "UZ Y"}


def test_retranslate_po_msgid_with_commas(tmp_path, monkeypatch, api):
    header = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
    msgid = "Hello, %(name)s, welcome"
    _project(
        tmp_path,
        monkeypatch,
        {
            "locale/en/LC_MESSAGES/django.po": header + f'msgid "{msgid}"\nmsgstr "{msgid}"\n\nmsgid "Bye"\nmsgstr "Bye"\n',
            # The placeholder was lost: not repairable, so it is retranslated.
            "locale/uz/LC_MESSAGES/django.po": header + f'msgid "{msgid}"\nmsgstr "Salom, xush kelibsiz"\n\nmsgid "Bye"\nmsgstr "Xayr"\n',
        },
        {"locale/en/LC_MESSAGES/django.po": "locale/%algebras_locale_code%/LC_MESSAGES/django.po"},
    )
    placeholders_command.execute(languages=["uz"], fix=True, retranslate=True)
    target = read_language_file(str(tmp_path / "locale/uz/LC_MESSAGES/django.po"))
    assert target[msgid] == "UZ " + msgid
    assert target["Bye"] == "Xayr"


# 4. 'update' pairs Android targets -------------------------------------------------------------


ANDROID_SOURCE = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="a">Hello</string>
    <string name="b">Bye</string>
</resources>
"""
ANDROID_TARGET = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="a">Privet</string>
</resources>
"""


def test_find_matching_source_file_android():
    sources = ["res/values/strings.xml"]
    for target, lang in [
        ("res/values-ru/strings.xml", "ru"),
        ("res/values-pt-rBR/strings.xml", "pt-BR"),
        ("res/values-b+uz+Cyrl/strings.xml", "uz-Cyrl"),
    ]:
        assert update_command.find_matching_source_file(target, sources, lang, "en") == sources[0]
    assert update_command.find_matching_source_file("res/values-ru/other.xml", sources, "ru", "en") is None


def test_update_android_project(tmp_path, monkeypatch, api):
    _project(
        tmp_path,
        monkeypatch,
        {
            "res/values/strings.xml": ANDROID_SOURCE,
            "res/values-ru/strings.xml": ANDROID_TARGET,
            "res/values-b+uz+Cyrl/strings.xml": ANDROID_TARGET,
        },
        {"res/values/strings.xml": "res/values-%algebras_locale_code%/strings.xml"},
        languages=("en", "ru", "uz-Cyrl"),
    )
    result = _run("update", "--only-missing")
    assert result.exit_code == 0, result.output
    for folder in ("values-ru", "values-b+uz+Cyrl"):
        data = read_language_file(str(tmp_path / "res" / folder / "strings.xml"))
        assert data["a"] == "Privet"
        assert data["b"] == "UZ Bye", folder


# 5. Outdated detection reports leaf keys only --------------------------------------------------


def test_outdated_keys_are_leaf_keys(tmp_path, monkeypatch):
    source = tmp_path / "en.yml"
    target = tmp_path / "ru.yml"
    source.write_text(yaml.safe_dump({"en": {"nav": {"home": "Home", "about": "About"}, "title": "T"}}))
    target.write_text(yaml.safe_dump({"en": {"nav": {"home": "Old", "about": "About"}, "title": "T"}}))
    monkeypatch.setattr("algebras.utils.lang_validator.is_git_available", lambda: True)
    monkeypatch.setattr("algebras.utils.lang_validator.is_git_repository", lambda path: True)
    dates = {str(source): "2024-02-01T00:00:00", str(target): "2024-01-01T00:00:00"}
    monkeypatch.setattr(
        "algebras.utils.lang_validator.get_keys_last_modifications_batch",
        lambda path, keys: {k: dates[path] for k in keys},
    )
    assert find_outdated_keys(str(source), str(target)) == (True, {"en.nav.home"})


# 6. Non-string values are copied, not blanked --------------------------------------------------


def test_non_string_values_are_copied(tmp_path, monkeypatch, api):
    _project(
        tmp_path,
        monkeypatch,
        {
            "locales/en/common.json": json.dumps({"t": "Hi", "max": 5, "ratio": 1.5, "flag": False, "n": None}),
            "locales/uz/common.json": json.dumps({"t": "Salom"}),
            "config/locales/en.yml": "en:\n  title: Hello\n  limit: 3\n  enabled: true\n",
            "config/locales/uz.yml": "uz:\n  title: Salom\n",
        },
        {**JSON_SOURCE, "config/locales/en.yml": "config/locales/%algebras_locale_code%.yml"},
    )
    result = _run("translate", "-l", "uz", "--only-missing")
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "locales/uz/common.json").read_text()) == {
        "t": "Salom", "max": 5, "ratio": 1.5, "flag": False, "n": None,
    }
    assert yaml.safe_load((tmp_path / "config/locales/uz.yml").read_text()) == {
        "uz": {"title": "Salom", "limit": 3, "enabled": True}
    }
    sent = [t for call in api["batch"] for t in call["texts"]]
    assert not any(t in ("5", "1.5", "False", "None", "3", "True") for t in sent), sent


# 7. Language codes -----------------------------------------------------------------------------


def test_same_language_code_on_both_paths(tmp_path, monkeypatch, api):
    _json_project(tmp_path, monkeypatch, {"a": "Hello"})
    from algebras.config import Config
    from algebras.services.translator import Translator

    for code, expected in [("uz-Cyrl", "uz-Cyrl"), ("pt_BR", "pt-BR")]:
        translator = Translator(Config())
        translator.translate_missing_keys_batch({"a": "Hello"}, {}, ["a"], code)
        translator.translate_text("Hello", "en", code)
        assert api["batch"][-1]["target"] == expected
        assert api["single"][-1]["target"] == expected


def test_invalid_language_is_reported_once_and_keys_left_out(tmp_path, monkeypatch, api):
    _project(
        tmp_path,
        monkeypatch,
        {
            "locales/en/common.json": json.dumps({"a": "Hello", "b": "Bye", "c": "Yes"}),
            "locales/en/other.json": json.dumps({"d": "No"}),
        },
        {
            **JSON_SOURCE,
            "locales/en/other.json": "locales/%algebras_locale_code%/other.json",
        },
        languages=("en", "pt-BR"),
    )

    def invalid(self, texts, source_lang, target_lang, *a, **k):
        raise Exception(
            "Failed to translate batch with Algebras AI: Error from Algebras AI API: "
            f'500 - {{"detail":"Invalid language: {target_lang}"}}'
        )

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", invalid)
    result = _run("translate", "--force", "--batch-size", "1")
    assert result.output.count("does not support the language 'pt-BR'") == 1, result.output
    assert "locale_mapping" in result.output
    assert "4 keys left out" in result.output
    assert result.exit_code == 1  # no key of either file could be translated
