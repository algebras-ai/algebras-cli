"""
Android XML escaping: every writer escapes values the way aapt2 requires, whatever
api.normalize_strings says, and the reader decodes them back to the plain text.

These tests replace the old ones in this file, which asserted that with normalize_strings on
(the default) an apostrophe was written unescaped ("Ko'proq matn"). aapt2 rejects that file
("Apostrophe not preceded by \\"), so the Android build failed. normalize_strings only cleans
up escapes in the model's output (StringNormalizer); it no longer reaches the writer.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import translate_command
from algebras.utils import android_xml_handler as handler
from algebras.utils.android_xml_handler import (
    read_android_xml_file,
    update_android_xml_values,
    write_android_xml_file,
    write_android_xml_file_in_place,
)
from tests.aapt_string_rules import assert_aapt_valid, file_problems

XLIFF = 'xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"'
NAME = '<xliff:g id="name" example="Bob">%1$s</xliff:g>'

# value -> how its text is written in the file
CASES = {
    "apostrophe": ("It's", r"It\'s"),
    "quote": ('Say "hi"', r"Say \"hi\""),
    "at": ("@home", r"\@home"),
    "question": ("?why", r"\?why"),
    "backslash": ("a\\b", r"a\\b"),
    "newline": ("Line\nTwo", r"Line\nTwo"),
    "tab": ("Col\tB", r"Col\tB"),
    "format": ("It's %1$s's \"best\" %2$d", r"It\'s %1$s\'s \"best\" %2$d"),
    "xliff": (f"Don't tell {NAME} \"now\"", f"Don\\'t tell {NAME} \\\"now\\\""),
    "unicode_escape": ("Wait\\u2026", "Wait\\u2026"),  # kept as written, never \\u2026
}
VALUES = {key: value for key, (value, _raw) in CASES.items()}
PLURAL = {"one": "%d file's", "other": '%d files "here"'}


@pytest.fixture(params=[True, False], ids=["normalize_on", "normalize_off"])
def normalize_project(request, tmp_path, monkeypatch):
    """A project whose config sets api.normalize_strings; the writers must not care."""
    (tmp_path / ".algebras.config").write_text(
        json.dumps({"languages": ["en", "fr"], "api": {"provider": "algebras-ai", "normalize_strings": request.param}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_escape_helper_is_pure():
    assert not hasattr(handler, "Config")
    assert not hasattr(handler, "_normalize_strings_enabled")
    for key in ("apostrophe", "quote", "backslash", "newline", "tab", "unicode_escape"):
        value, raw = CASES[key]
        assert handler._escape_android_text(value) == raw
    assert handler._escape_android_text("It's", quoted=True) == "It's"
    assert handler._escape_xml_text("Ko'proq & co") == r"Ko\'proq &amp; co"


def test_full_write_escapes_and_round_trips(normalize_project):
    path = normalize_project / "strings.xml"
    content = dict(VALUES, **{"count.__plurals__": PLURAL})

    write_android_xml_file(str(path), content)
    raw = path.read_text(encoding="utf-8")

    for key, (_value, escaped) in CASES.items():
        assert f'<string name="{key}">{escaped}</string>' in raw, key
    assert r'<item quantity="one">%d file\'s</item>' in raw
    assert r'<item quantity="other">%d files \"here\"</item>' in raw
    assert_aapt_valid(path)
    assert read_android_xml_file(str(path)) == content


def test_in_place_write_escapes_and_round_trips(normalize_project):
    path = normalize_project / "strings.xml"
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<resources {XLIFF}>\n'
        "    <!-- keep me -->\n"
        + "".join(f'    <string name="{key}">old</string>\n' for key in list(CASES)[:5])
        + '    <plurals name="count">\n        <item quantity="other">old</item>\n    </plurals>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    content = dict(VALUES, **{"count.__plurals__": PLURAL})

    write_android_xml_file_in_place(str(path), content, set(content))
    raw = path.read_text(encoding="utf-8")

    assert "<!-- keep me -->" in raw
    for key, (_value, escaped) in CASES.items():
        assert f'<string name="{key}">{escaped}</string>' in raw, key
    assert_aapt_valid(path)
    assert read_android_xml_file(str(path)) == content


def test_update_values_escapes_and_round_trips(normalize_project):
    """The 'algebras placeholders --fix' writer, from values with and without escapes."""
    path = normalize_project / "strings.xml"
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<resources {XLIFF}>\n'
        + "".join(f'    <string name="{key}">old %1$s</string>\n' for key in CASES)
        + '    <string name="markup">Old <xliff:g id="name" example="Bob">%1$s</xliff:g></string>\n'
        '    <plurals name="count">\n        <item quantity="one">old</item>\n'
        '        <item quantity="other">old</item>\n    </plurals>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    values = {(key,): value for key, value in VALUES.items()}
    values[("markup",)] = f"It's {NAME}"
    values[("count.__plurals__", "one")] = PLURAL["one"]
    values[("count.__plurals__", "other")] = PLURAL["other"]

    assert update_android_xml_values(str(path), values) == []
    raw = path.read_text(encoding="utf-8")

    for key, (_value, escaped) in CASES.items():
        assert f'<string name="{key}">{escaped}</string>' in raw, key
    assert f'<string name="markup">It\\\'s {NAME}</string>' in raw
    assert_aapt_valid(path)
    data = read_android_xml_file(str(path))
    for (key, *quantity), value in values.items():
        assert (data[key][quantity[0]] if quantity else data[key]) == value


def test_update_values_never_leaves_an_unescaped_leading_at(tmp_path):
    # The smallest raw edit ("x" -> "@") would leave "@home", which aapt2 reads as a reference.
    path = tmp_path / "strings.xml"
    path.write_text('<resources><string name="a">xhome</string></resources>', encoding="utf-8")
    update_android_xml_values(str(path), {("a",): "@home"})
    assert r'<string name="a">\@home</string>' in path.read_text(encoding="utf-8")
    assert_aapt_valid(path)
    assert read_android_xml_file(str(path))["a"] == "@home"


def test_wholly_quoted_values_stay_quoted(tmp_path):
    path = tmp_path / "strings.xml"
    path.write_text(
        '<resources>\n'
        '    <string name="q">"It\'s"</string>\n'
        '    <string name="fix">"Don\'t"</string>\n'
        '    <string name="b">"It\'s <b>bold</b>"</string>\n'
        '    <plurals name="p">\n        <item quantity="other">"%d don\'t"</item>\n    </plurals>\n'
        '</resources>\n',
        encoding="utf-8",
    )
    assert_aapt_valid(path)
    data = read_android_xml_file(str(path))
    assert data == {
        "q": "It's",
        "fix": "Don't",
        "b": "It's <b>bold</b>",
        "p.__plurals__": {"other": "%d don't"},
    }

    write_android_xml_file_in_place(
        str(path),
        {"q": "C'est", "b": "C'est <b>gras</b>", "p.__plurals__": {"other": '%d l\'"été"'}},
        {"q", "b", "p.__plurals__"},
    )
    update_android_xml_values(str(path), {("fix",): "N'oubliez pas"})
    raw = path.read_text(encoding="utf-8")

    assert '<string name="q">"C\'est"</string>' in raw
    assert '<string name="b">"C\'est <b>gras</b>"</string>' in raw
    assert '<string name="fix">"N\'oubliez pas"</string>' in raw
    assert '<item quantity="other">"%d l\'\\"été\\""</item>' in raw
    assert_aapt_valid(path)
    assert read_android_xml_file(str(path)) == {
        "q": "C'est",
        "fix": "N'oubliez pas",
        "b": "C'est <b>gras</b>",
        "p.__plurals__": {"other": '%d l\'"été"'},
    }


def test_reader_decodes_android_escapes(tmp_path):
    path = tmp_path / "strings.xml"
    path.write_text(
        '<resources>\n'
        r'    <string name="esc">\@a \?b c\\d \'e\' \"f\" g\nh\ti ' "\\u2026</string>\n"
        r'    <string name="literal_ref">\@string/app_name</string>' "\n"
        '    <string name="ref">@string/app_name</string>\n'
        '    <string name="padded">"  two spaces  "</string>\n'
        '    <string name="mixed">Say "it\'s" here</string>\n'
        r'    <string name="cdata"><![CDATA[<b>Hi</b> %1$s]]></string>' "\n"
        '</resources>\n',
        encoding="utf-8",
    )
    assert_aapt_valid(path)
    data = read_android_xml_file(str(path))
    assert data["esc"] == "@a ?b c\\d 'e' \"f\" g\nh\ti \\u2026"
    assert data["literal_ref"] == "@string/app_name"  # literal text, not a reference
    assert "ref" not in data
    assert data["padded"] == "  two spaces  "
    assert data["mixed"] == "Say it's here"  # aapt2 drops the quotes of a quoted section
    assert data["cdata"] == "<b>Hi</b> %1$s"

    out = tmp_path / "out.xml"
    write_android_xml_file(str(out), {"padded": "  two spaces  ", "esc": data["esc"]})
    raw = out.read_text(encoding="utf-8")
    assert '<string name="padded">"  two spaces  "</string>' in raw  # quoted, or aapt2 trims
    assert_aapt_valid(out)
    assert read_android_xml_file(str(out)) == {"padded": "  two spaces  ", "esc": data["esc"]}


def test_validator_catches_what_aapt2_rejects(tmp_path):
    path = tmp_path / "strings.xml"
    path.write_text(
        "<resources>\n"
        "    <string name=\"apos\">It's</string>\n"
        '    <string name="unbalanced">Say \\"hi" there</string>\n'
        '    <string name="at">@home</string>\n'
        '    <string name="ok1">"It\'s"</string>\n'
        '    <string name="ok2">It\\\'s <b>"x"</b></string>\n'
        '    <string name="ok3">@string/app_name</string>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    problems = file_problems(path)
    assert [p.split(":")[0] for p in problems] == ["string apos", "string unbalanced", "string at"]


# ---------------------------------------------------------------------------
# End to end: 'algebras translate' with a model that answers with apostrophes and quotes
# ---------------------------------------------------------------------------

E2E_SOURCE = f"""<?xml version="1.0" encoding="utf-8"?>
<resources {XLIFF}>
    <string name="welcome">It\\'s %1$s</string>
    <string name="say">Say \\"hi\\"</string>
    <string name="invite">Invite {NAME} now</string>
    <string name="quoted">"Don't stop"</string>
    <plurals name="files">
        <item quantity="one">%d file</item>
        <item quantity="other">%d files</item>
    </plurals>
</resources>
"""

PLAIN_SUFFIX = " l'été \"chaud\""
ESCAPED_SUFFIX = " l\\'été \\\"chaud\\\""


@pytest.mark.parametrize(
    "normalize,model_suffix",
    [(True, PLAIN_SUFFIX), (False, PLAIN_SUFFIX), (True, ESCAPED_SUFFIX)],
    ids=["normalize_on", "normalize_off", "normalize_on_escaped_model_output"],
)
def test_translate_writes_a_file_aapt2_accepts(tmp_path, monkeypatch, normalize, model_suffix):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values" / "strings.xml").write_text(E2E_SOURCE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "de"],  # German plurals: one / other
                "source_files": {
                    "res/values/strings.xml": {"destination_path": "res/values-%algebras_locale_code%/strings.xml"}
                },
                "api": {"provider": "algebras-ai", "normalize_strings": normalize},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)

    client = MagicMock()
    client.translate_batch.side_effect = lambda texts, *a, **k: [t + model_suffix for t in texts]
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=client):
        translate_command.execute(language="de", force="__all__")

    target = tmp_path / "res" / "values-de" / "strings.xml"
    assert_aapt_valid(target)
    data = read_android_xml_file(str(target))
    assert data["welcome"] == "It's %1$s" + PLAIN_SUFFIX
    assert data["say"] == 'Say "hi"' + PLAIN_SUFFIX
    assert data["invite"] == f"Invite {NAME} now" + PLAIN_SUFFIX
    assert data["quoted"] == "Don't stop" + PLAIN_SUFFIX
    assert data["files.__plurals__"] == {"one": "%d file" + PLAIN_SUFFIX, "other": "%d files" + PLAIN_SUFFIX}
    raw = target.read_text(encoding="utf-8")
    assert r"It\'s %1$s l\'été \"chaud\"" in raw
    assert f"Invite {NAME} now" in raw  # markup written as elements
