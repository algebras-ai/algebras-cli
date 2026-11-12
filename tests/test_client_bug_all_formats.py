"""
The client's bug, in every format: translating into Uzbek Cyrillic, the model transliterates Latin
letters, which turned %1$s into %1$с and %1$d into %1$д. A fake model that transliterates every
Latin letter it sees must leave all placeholders byte-for-byte intact in the written files.
"""

import json
from unittest.mock import MagicMock

import pytest

from algebras.commands import translate_command
from algebras.utils.lang_validator import read_language_file

_LATIN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_CYRILLIC = "абсдефгхижклмнопқрстувўхйзАБСДЕФГҲИЖКЛМНОПҚРСТУВЎХЙЗ"
_TRANSLIT = str.maketrans(dict(zip(_LATIN, _CYRILLIC)))


def transliterate(text: str) -> str:
    return text.translate(_TRANSLIT)


# format id -> (source path, destination pattern, source content, key path, placeholders that must survive)
FORMATS = {
    "android": (
        "res/values/strings.xml",
        "res/values-%algebras_locale_code%/strings.xml",
        '<?xml version="1.0" encoding="utf-8"?>\n<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n'
        '    <string name="code">We sent a code to %1$s. Resend in %2$d s</string>\n'
        '    <string name="hello">Hello <xliff:g id="n">%1$s</xliff:g>!</string>\n'
        "    <plurals name=\"points\">\n"
        '        <item quantity="one">%1$d point</item>\n'
        '        <item quantity="other">%1$d points</item>\n'
        "    </plurals>\n</resources>\n",
        ("code",),
        ["%1$s", "%2$d"],
    ),
    "strings": (
        "App/en.lproj/Localizable.strings",
        "App/%algebras_locale_code%.lproj/Localizable.strings",
        '"code" = "%1$@ shared %2$ld files with %3$@";\n',
        ("code",),
        ["%1$@", "%2$ld", "%3$@"],
    ),
    "json": (
        "locales/en/common.json",
        "locales/%algebras_locale_code%/common.json",
        json.dumps({"code": "Hi {{name}}, order {{orderId}} has shipped"}),
        ("code",),
        ["{{name}}", "{{orderId}}"],
    ),
    "yaml": (
        "config/locales/en.yml",
        "config/locales/%algebras_locale_code%.yml",
        'en:\n  code: "Total: %{amount} for %{count} items"\n',
        ("uz", "code"),
        ["%{amount}", "%{count}"],
    ),
    "ts": (
        "src/i18n/en.ts",
        "src/i18n/%algebras_locale_code%.ts",
        "export default {\n  code: `Price: ${price} (was ${oldPrice})`,\n};\n",
        ("code",),
        ["${price}", "${oldPrice}"],
    ),
    "properties": (
        "src/messages_en.properties",
        "src/messages_%algebras_locale_code%.properties",
        "code=Welcome, {0}! You have {1,number} messages\n",
        ("code",),
        ["{0}", "{1,number}"],
    ),
    "arb": (
        "lib/l10n/app_en.arb",
        "lib/l10n/app_%algebras_locale_code%.arb",
        json.dumps({"code": "Hello {userName}, you have {count} messages"}),
        ("code",),
        ["{userName}", "{count}"],
    ),
    "po": (
        "locale/en/LC_MESSAGES/django.po",
        "locale/%algebras_locale_code%/LC_MESSAGES/django.po",
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        '#, python-format\nmsgid "Hi %(name)s, %(days)d days left"\nmsgstr "Hi %(name)s, %(days)d days left"\n',
        ("Hi %(name)s, %(days)d days left",),
        ["%(name)s", "%(days)d"],
    ),
    "xliff": (
        "i18n/messages.en.xlf",
        "i18n/messages.%algebras_locale_code%.xlf",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
        '  <file source-language="en" datatype="plaintext" original="ng2.template">\n    <body>\n'
        '      <trans-unit id="code">\n'
        '        <source>Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>, you have %d messages</source>\n'
        "      </trans-unit>\n    </body>\n  </file>\n</xliff>\n",
        ("code",),
        ['<x id="INTERPOLATION" equiv-text="{{ name }}"/>', "%d"],
    ),
    "csv": (
        "sheet/strings.csv",
        "sheet/strings.csv",
        "key,en,uz\ncode,\"Sent to %1$s, retry in %2$d s\",\n",
        ("code",),
        ["%1$s", "%2$d"],
    ),
}


@pytest.fixture
def transliterating_api(monkeypatch):
    sent = []

    def translate_batch(self, texts, *args, **kwargs):
        sent.extend(texts)
        return [transliterate(t) for t in texts]

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    monkeypatch.setattr(
        "algebras.services.api_client.AlgebrasAIClient.translate", lambda self, text, *a, **k: transliterate(text)
    )
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return sent


def _get(data, path):
    for part in path:
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


@pytest.mark.parametrize("fmt", sorted(FORMATS))
def test_transliterating_model_cannot_damage_placeholders(fmt, tmp_path, monkeypatch, transliterating_api):
    source, destination, content, key_path, placeholders = FORMATS[fmt]
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

    translate_command.execute(language="uz", force="__all__")

    # The model never saw a raw placeholder: nothing it could transliterate.
    sent = "\n".join(transliterating_api)
    for placeholder in placeholders:
        assert placeholder not in sent, f"{fmt}: {placeholder} was sent to the model"

    target = tmp_path / destination.replace("%algebras_locale_code%", "uz")
    data = read_language_file(str(target), "uz" if fmt == "csv" else None, None)
    value = _get(data, key_path)
    if fmt == "xliff":
        # The reader keeps attribute text in an internal encoding; check the written <target>.
        import re

        value = re.search(r"<target[^>]*>(.*?)</target>", target.read_text(encoding="utf-8"), re.S).group(1)
    assert isinstance(value, str) and value, f"{fmt}: nothing written for {key_path}: {data!r}"
    assert value != content, f"{fmt}: not translated"
    for placeholder in placeholders:
        assert placeholder in value, f"{fmt}: {placeholder} damaged in {value!r}"
    # The client's exact symptom: a Cyrillic letter in a conversion position.
    for damaged in ("$с", "$д", "%с", "%д"):
        assert damaged not in value, f"{fmt}: transliterated specifier in {value!r}"
