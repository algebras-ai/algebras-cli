"""
Android tools:locale: a new target gets its own locale (the values-<qualifier> folder's code), not
the source's; an existing target's tools:locale is left as it is.
"""

from algebras.utils.android_xml_handler import target_tools_locale, write_android_xml_preserving_layout
from algebras.utils.file_format_handlers.xml_handler import XMLHandler

SOURCE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<resources xmlns:tools="http://schemas.android.com/tools" tools:locale="en">\n'
    '    <string name="hello">Hello</string>\n'
    "</resources>\n"
)


def _source(tmp_path):
    path = tmp_path / "res" / "values" / "strings.xml"
    path.parent.mkdir(parents=True)
    path.write_text(SOURCE, encoding="utf-8")
    return path


def test_new_target_gets_the_target_locale(tmp_path):
    source = _source(tmp_path)
    target = tmp_path / "res" / "values-pt-rBR" / "strings.xml"
    target.parent.mkdir(parents=True)
    XMLHandler().write_in_place(
        str(target), {"hello": "Olá"}, {"hello"}, source_file=str(source), target_language="pt-BR"
    )
    assert target.read_text(encoding="utf-8") == SOURCE.replace('tools:locale="en"', 'tools:locale="pt-rBR"').replace(
        "Hello", "Olá"
    )


def test_locale_from_language_when_folder_is_not_a_values_folder(tmp_path):
    assert target_tools_locale(str(tmp_path / "out" / "strings_ru.xml"), "zh-Hans") == "b+zh+Hans"
    assert target_tools_locale(str(tmp_path / "values-b+uz+Cyrl" / "strings.xml"), "uz-Cyrl") == "b+uz+Cyrl"
    assert target_tools_locale(str(tmp_path / "out" / "strings.xml"), None) is None


def test_existing_target_keeps_its_tools_locale(tmp_path):
    source = _source(tmp_path)
    target = tmp_path / "res" / "values-ru" / "strings.xml"
    target.parent.mkdir(parents=True)
    existing = SOURCE.replace('tools:locale="en"', 'tools:locale="en"').replace("Hello", "Привет")
    target.write_text(existing, encoding="utf-8")
    write_android_xml_preserving_layout(str(target), {"hello": "Здравствуйте"}, str(source), language="ru")
    assert target.read_text(encoding="utf-8") == existing.replace("Привет", "Здравствуйте")
