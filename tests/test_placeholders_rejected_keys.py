"""
A value whose placeholders don't survive translation (even after the retry) is left out of the
target file: never written damaged, and never written as the source-language text. 'status' then
reports it as missing and the next run retries it.
"""

import json
import re
from unittest.mock import MagicMock

import pytest

from algebras.commands import translate_command
from algebras.utils.lang_validator import read_language_file

_TOKEN = re.compile(r"⟦\d+⟧")

# format id -> (source path, destination pattern, source content, "ok" key path, "bad" key path)
FORMATS = {
    "strings": (
        "App/en.lproj/Localizable.strings",
        "App/%algebras_locale_code%.lproj/Localizable.strings",
        '"ok" = "Hello";\n"bad" = "Sent to %1$@";\n',
        ("ok",),
        ("bad",),
    ),
    "android": (
        "res/values/strings.xml",
        "res/values-%algebras_locale_code%/strings.xml",
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <string name="ok">Hello</string>\n'
        '    <string name="bad">Sent to %1$s</string>\n</resources>\n',
        ("ok",),
        ("bad",),
    ),
    "json": (
        "locales/en/common.json",
        "locales/%algebras_locale_code%/common.json",
        json.dumps({"ok": "Hello", "nested": {"bad": "Hi {{name}}", "ok2": "Bye"}}),
        ("ok",),
        ("nested", "bad"),
    ),
    "yaml": (
        "config/locales/en.yml",
        "config/locales/%algebras_locale_code%.yml",
        "en:\n  ok: Hello\n  bad: \"Hi %{name}\"\n",
        ("uz", "ok"),  # paths in the target file: Rails roots it at its own locale
        ("uz", "bad"),
    ),
    "ts": (
        "src/i18n/en.ts",
        "src/i18n/%algebras_locale_code%.ts",
        'export default {\n  ok: "Hello",\n  bad: "Hi {{name}}",\n};\n',
        ("ok",),
        ("bad",),
    ),
    "properties": (
        "src/messages_en.properties",
        "src/messages_%algebras_locale_code%.properties",
        "ok=Hello\nbad=Hi {0}\n",
        ("ok",),
        ("bad",),
    ),
    "arb": (
        "lib/l10n/app_en.arb",
        "lib/l10n/app_%algebras_locale_code%.arb",
        json.dumps({"@@locale": "en", "ok": "Hello", "bad": "Hi {name}"}),
        ("ok",),
        ("bad",),
    ),
    "po": (
        "locale/en/LC_MESSAGES/django.po",
        "locale/%algebras_locale_code%/LC_MESSAGES/django.po",
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        'msgid "Hello"\nmsgstr "Hello"\n\n'
        '#, python-format\nmsgid "Hi %(name)s"\nmsgstr "Hi %(name)s"\n',
        ("Hello",),
        ("Hi %(name)s",),
    ),
}


def _get(data, path):
    for part in path:
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


@pytest.fixture
def fake_api(monkeypatch):
    """Translates by prefixing 'UZ ', but always drops placeholder tokens (so they are rejected)."""
    sent = []

    def translate_batch(self, texts, *args, **kwargs):
        sent.append(list(texts))
        return ["UZ " + _TOKEN.sub("", t) for t in texts]

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate", lambda self, text, *a, **k: "UZ " + _TOKEN.sub("", text))
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return sent


def _project(tmp_path, monkeypatch, fmt):
    source, destination, content, _, _ = FORMATS[fmt]
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "uz"],
                "source_files": {source: {"destination_path": destination}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path / destination.replace("%algebras_locale_code%", "uz")


@pytest.mark.parametrize("fmt", sorted(FORMATS))
@pytest.mark.parametrize("mode", ["full", "missing"])
def test_rejected_value_is_left_out(fmt, mode, tmp_path, monkeypatch, fake_api):
    target = _project(tmp_path, monkeypatch, fmt)
    _, _, _, ok_path, bad_path = FORMATS[fmt]

    if mode == "full":
        translate_command.execute(language="uz", force="__all__")
    else:
        translate_command.execute(language="uz", only_missing=True)

    assert target.exists(), f"{fmt}: target not written"
    data = read_language_file(str(target), None, None)
    ok = _get(data, ok_path)
    assert isinstance(ok, str) and ok.startswith("UZ "), f"{fmt}/{mode}: ok key not translated: {ok!r}"
    bad = _get(data, bad_path)
    assert not bad, f"{fmt}/{mode}: rejected key was written as {bad!r}"


@pytest.mark.parametrize("fmt", ["json", "strings", "yaml", "arb"])
def test_left_out_key_is_retried_on_the_next_run(fmt, tmp_path, monkeypatch, fake_api):
    target = _project(tmp_path, monkeypatch, fmt)
    _, _, _, _, bad_path = FORMATS[fmt]
    translate_command.execute(language="uz", force="__all__")
    assert not _get(read_language_file(str(target), None, None), bad_path)

    # The model behaves now: the next normal run fills in only the missing key.
    monkeypatch.setattr(
        "algebras.services.api_client.AlgebrasAIClient.translate_batch",
        lambda self, texts, *a, **k: ["UZ " + t for t in texts],
    )
    translate_command.execute(language="uz", only_missing=True)
    bad = _get(read_language_file(str(target), None, None), bad_path)
    assert isinstance(bad, str) and bad.startswith("UZ "), f"{fmt}: {bad!r}"


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_failed_api_batch_writes_no_source_text(fmt, tmp_path, monkeypatch, fake_api):
    """A batch that fails at the API (e.g. HTTP 500) leaves its keys out instead of writing source text."""
    target = _project(tmp_path, monkeypatch, fmt)
    _, _, _, ok_path, bad_path = FORMATS[fmt]

    def failing_batch(self, texts, *args, **kwargs):
        raise Exception("Error from Algebras AI API: 500 - server error")

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", failing_batch)
    translate_command.execute(language="uz", force="__all__")

    if not target.exists():
        return  # nothing written at all is fine
    data = read_language_file(str(target), None, None)
    for path in (ok_path, bad_path):
        value = _get(data, path)
        assert not value, f"{fmt}: {path} was written as {value!r} although its batch failed"
