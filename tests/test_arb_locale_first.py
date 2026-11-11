"""
ARB: a new target always gets "@@locale" set to the target locale, as its first entry (the Flutter
convention), whether or not the source has one.
"""

import json

from algebras.utils.arb_handler import write_arb_from_template


def _write(tmp_path, source_text, language="de", name="app_de.arb"):
    source = tmp_path / "app_en.arb"
    source.write_text(source_text, encoding="utf-8")
    target = tmp_path / name
    write_arb_from_template(str(target), {"hello": "Hallo", "bye": "Tschüss"}, str(source), language)
    return target.read_text(encoding="utf-8")


def test_locale_added_first_when_source_has_none(tmp_path):
    text = _write(tmp_path, '{\n  "hello": "Hello",\n  "@hello": {"description": "Greeting"},\n  "bye": "Bye"\n}\n')
    assert text == (
        '{\n  "@@locale": "de",\n  "hello": "Hallo",\n  "@hello": {"description": "Greeting"},\n'
        '  "bye": "Tschüss"\n}\n'
    )


def test_locale_moved_first_and_set_to_target(tmp_path):
    text = _write(
        tmp_path,
        '{\n  "hello": "Hello",\n  "@@locale": "en",\n  "bye": "Bye"\n}\n',
        language="pt-BR",
        name="app_pt_BR.arb",
    )
    assert list(json.loads(text)) == ["@@locale", "hello", "bye"]
    assert json.loads(text)["@@locale"] == "pt_BR"
    assert text.startswith('{\n  "@@locale": "pt_BR",\n  "hello": "Hallo",\n')


def test_locale_already_first_keeps_layout(tmp_path):
    text = _write(tmp_path, '{\n  "@@locale": "en",\n  "hello": "Hello",\n  "bye": "Bye"\n}\n')
    assert text == '{\n  "@@locale": "de",\n  "hello": "Hallo",\n  "bye": "Tschüss"\n}\n'
