"""
'algebras translate' / 'update' keep the file layout for CSV/TSV, JSON, Flutter ARB and Java
.properties: an existing target changes only the values that changed (new keys at their source
position), and a new target is built from the source file as a template, leaving out keys that
were not translated. --regenerate-from-scratch still rewrites the file from the content alone.
"""

import difflib
import json
import os
import re
from unittest.mock import MagicMock

import pytest

from algebras.commands import translate_command
from algebras.utils.json_layout import merge_json_text

_TOKEN = re.compile(r"⟦\d+⟧")


def _model(prefix):
    """'<prefix> ' + text; texts with 'Broken' lose their placeholder tokens (so they are rejected)."""

    def one(text):
        return prefix + " " + (_TOKEN.sub("", text) if "Broken" in text else text)

    return one


@pytest.fixture
def fake_api(monkeypatch):
    def use(prefix):
        one = _model(prefix)
        monkeypatch.setattr(
            "algebras.services.api_client.AlgebrasAIClient.translate_batch",
            lambda self, texts, *a, **k: [one(t) for t in texts],
        )
        monkeypatch.setattr(
            "algebras.services.api_client.AlgebrasAIClient.translate", lambda self, text, *a, **k: one(text)
        )

    use("UZ")
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return use


def _project(tmp_path, monkeypatch, source, destination, content: bytes, languages=("en", "uz")):
    path = tmp_path / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": list(languages),
                "source_files": {source: {"destination_path": destination}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return path, tmp_path / destination.replace("%algebras_locale_code%", "uz")


def _edit_source(path, content: bytes):
    """Change the source and make it newer than the target, as an edit after a translate run does."""
    path.write_bytes(content)
    stamp = os.path.getmtime(path) + 10
    os.utime(path, (stamp, stamp))


def _changed_lines(before: bytes, after: bytes):
    """(removed, added) lines between two versions, line endings included."""
    a = before.decode("utf-8").splitlines(keepends=True)
    b = after.decode("utf-8").splitlines(keepends=True)
    removed, added = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            removed += a[i1:i2]
            added += b[j1:j2]
    return removed, added


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

JSON_SOURCE = (
    '{\r\n'
    '\t"zeta": "Last first",\r\n'
    '\t"alpha": "Hello {name}",\r\n'
    '\r\n'
    '\t"menu": {\r\n'
    '\t\t"open": "Open",\r\n'
    '\t\t"broken": "Broken {name}"\r\n'
    '\t},\r\n'
    '\t"bye": "Bye"\r\n'
    '}\r\n'
)

JSON_EXPECTED = (
    '{\r\n'
    '\t"zeta": "UZ Last first",\r\n'
    '\t"alpha": "UZ Hello {name}",\r\n'
    '\r\n'
    '\t"menu": {\r\n'
    '\t\t"open": "UZ Open"\r\n'
    '\t},\r\n'
    '\t"bye": "UZ Bye"\r\n'
    '}\r\n'
)


@pytest.fixture
def json_project(tmp_path, monkeypatch):
    return _project(
        tmp_path, monkeypatch, "locales/en/common.json", "locales/%algebras_locale_code%/common.json",
        JSON_SOURCE.encode(),
    )


def test_json_new_target_is_the_source_with_only_values_changed(json_project, fake_api):
    _, target = json_project
    translate_command.execute(language="uz")
    # Tabs, CRLF, the blank line, key order and the trailing newline come from the source;
    # the rejected "menu.broken" is left out, not written in English.
    assert target.read_bytes() == JSON_EXPECTED.encode()


def test_json_update_touches_only_changed_lines(json_project, fake_api):
    source, target = json_project
    translate_command.execute(language="uz")
    before = target.read_bytes()

    _edit_source(
        source,
        JSON_SOURCE.replace('"Bye"', '"Goodbye"')
        .replace('\t"alpha": "Hello {name}",\r\n', '\t"alpha": "Hello {name}",\r\n\t"beta": "Beta",\r\n')
        .replace('\t\t"open": "Open",\r\n', '\t\t"open": "Open",\r\n\t\t"save": "Save",\r\n')
        .encode(),
    )
    translate_command.execute(language="uz")
    after = target.read_bytes()

    removed, added = _changed_lines(before, after)
    assert removed == ['\t\t"open": "UZ Open"\r\n', '\t"bye": "UZ Bye"\r\n']
    assert added == [
        '\t"beta": "UZ Beta",\r\n',
        '\t\t"open": "UZ Open",\r\n',
        '\t\t"save": "UZ Save"\r\n',
        '\t"bye": "UZ Goodbye"\r\n',
    ]
    assert list(json.loads(after)) == ["zeta", "alpha", "beta", "menu", "bye"]


def test_json_only_missing_inserts_at_source_position_and_keeps_extra_keys(json_project, fake_api):
    source, target = json_project
    translate_command.execute(language="uz")
    # A key only the target has stays where it is.
    target.write_bytes(target.read_bytes().replace(b'\t"bye"', b'\t"legacy": "Old",\r\n\t"bye"'))
    before = target.read_bytes()
    _edit_source(
        source,
        JSON_SOURCE.replace('\t"zeta": "Last first",\r\n', '\t"zeta": "Last first",\r\n\t"new": "New",\r\n').encode(),
    )

    translate_command.execute(language="uz", only_missing=True)
    removed, added = _changed_lines(before, target.read_bytes())
    assert removed == [] and added == ['\t"new": "UZ New",\r\n']
    assert b'\t"legacy": "Old",\r\n' in target.read_bytes()


def test_json_force_keys_rewrites_only_those_values(json_project, fake_api):
    _, target = json_project
    translate_command.execute(language="uz")
    before = target.read_bytes()

    fake_api("XX")
    translate_command.execute(language="uz", force="alpha")
    removed, added = _changed_lines(before, target.read_bytes())
    assert removed == ['\t"alpha": "UZ Hello {name}",\r\n']
    assert added == ['\t"alpha": "XX Hello {name}",\r\n']


def test_json_regenerate_from_scratch_still_rewrites(json_project, fake_api):
    _, target = json_project
    translate_command.execute(language="uz")
    translate_command.execute(language="uz", force="__all__", regenerate_from_scratch=True)
    text = target.read_bytes().decode("utf-8")
    assert "\r\n" not in text and "\t" not in text
    assert text == json.dumps(json.loads(text), ensure_ascii=False, indent=2)


@pytest.mark.parametrize(
    "base, indent",
    [
        ('{\n  "a": "x",\n  "b": {\n    "c": "y"\n  }\n}', "  "),
        ('{\n    "a": "x",\n    "b": {\n        "c": "y"\n    }\n}', "    "),
        ('{\n\t"a": "x",\n\t"b": {\n\t\t"c": "y"\n\t}\n}', "\t"),
    ],
)
def test_json_new_nested_values_follow_the_file_indentation(base, indent):
    out = merge_json_text(base, {"a": "x", "b": {"c": "y"}, "d": {"e": "z"}})
    assert out.startswith(base[:-2])  # everything before the closing brace is unchanged
    assert out.endswith(f',\n{indent}"d": {{\n{indent}{indent}"e": "z"\n{indent}}}\n}}')
    assert json.loads(out)["d"] == {"e": "z"}


def test_json_escaping_style_is_kept():
    escaped = '{"a": "\\u041f", "b": "x"}'
    assert merge_json_text(escaped, {"a": "П", "b": "Б"}) == '{"a": "\\u041f", "b": "\\u0411"}'
    raw = '{"a": "П", "b": "x"}\n'
    assert merge_json_text(raw, {"a": "П", "b": "Б"}) == '{"a": "П", "b": "Б"}\n'


def test_json_unchanged_content_is_byte_identical():
    text = '{\n  "a" : "x",\n\n  "b": ["1", "2"],\n  "n": 1.50\n}'
    assert merge_json_text(text, json.loads(text)) == text


# ---------------------------------------------------------------------------
# Flutter ARB
# ---------------------------------------------------------------------------

ARB_SOURCE = """{
  "@@locale": "en",
  "title": "Shop",
  "@title": {
    "description": "App title"
  },
  "greeting": "Hi {name}",
  "@greeting": {
    "placeholders": {
      "name": {}
    }
  },
  "broken": "Broken {name}",
  "@broken": {
    "placeholders": {
      "name": {}
    }
  },
  "bye": "Bye"
}
"""

ARB_EXPECTED = """{
  "@@locale": "uz",
  "title": "UZ Shop",
  "@title": {
    "description": "App title"
  },
  "greeting": "UZ Hi {name}",
  "@greeting": {
    "placeholders": {
      "name": {}
    }
  },
  "bye": "UZ Bye"
}
"""


@pytest.fixture
def arb_project(tmp_path, monkeypatch):
    return _project(
        tmp_path, monkeypatch, "lib/l10n/app_en.arb", "lib/l10n/app_%algebras_locale_code%.arb",
        ARB_SOURCE.encode(),
    )


def test_arb_new_target_copies_metadata_and_sets_locale(arb_project, fake_api):
    _, target = arb_project
    translate_command.execute(language="uz")
    # Order and metadata come from the source, @@locale is the target's; the rejected message is
    # left out together with its metadata.
    assert target.read_bytes() == ARB_EXPECTED.encode()


def test_arb_update_inserts_new_message_with_metadata_at_source_position(arb_project, fake_api):
    source, target = arb_project
    translate_command.execute(language="uz")
    before = target.read_bytes()

    _edit_source(
        source,
        ARB_SOURCE.replace('"Shop"', '"Store"')
        .replace(
            '    "description": "App title"\n  },\n',
            '    "description": "App title"\n  },\n  "subtitle": "Deals",\n'
            '  "@subtitle": {\n    "description": "Under the title"\n  },\n',
        )
        .encode(),
    )
    translate_command.execute(language="uz")

    # The title value changes; the new message and its metadata sit where the source has them.
    assert target.read_bytes() == before.replace(
        b'  "title": "UZ Shop",\n  "@title": {\n    "description": "App title"\n  },\n',
        b'  "title": "UZ Store",\n  "@title": {\n    "description": "App title"\n  },\n'
        b'  "subtitle": "UZ Deals",\n  "@subtitle": {\n    "description": "Under the title"\n  },\n',
    )
    assert json.loads(target.read_bytes())["@@locale"] == "uz"


def test_arb_outdated_file_update_keeps_target_metadata(arb_project, fake_api):
    """The 'update' path (outdated files): a translated description in the target is not reverted."""
    source, target = arb_project
    translate_command.execute(language="uz")
    target.write_bytes(target.read_bytes().replace(b'"App title"', b'"Ilova nomi"'))
    before = target.read_bytes()

    _edit_source(source, ARB_SOURCE.replace('"Bye"', '"Goodbye"').encode())
    translate_command.execute(language="uz", outdated_files=[(str(target), str(source))])

    removed, added = _changed_lines(before, target.read_bytes())
    assert removed == ['  "bye": "UZ Bye"\n'] and added == ['  "bye": "UZ Goodbye"\n']


# ---------------------------------------------------------------------------
# Java .properties
# ---------------------------------------------------------------------------

PROPERTIES_SOURCE = (
    "# Greetings shown on the home screen\n"
    "welcome = Welcome, {0}!\n"
    "\n"
    "! legacy section\n"
    "broken: Broken {0}\n"
    "farewell=Bye\n"
)

PROPERTIES_EXPECTED = (
    "# Greetings shown on the home screen\n"
    "welcome = UZ Welcome, {0}!\n"
    "\n"
    "! legacy section\n"
    "farewell=UZ Bye\n"
)


@pytest.fixture
def properties_project(tmp_path, monkeypatch):
    return _project(
        tmp_path, monkeypatch, "src/messages_en.properties", "src/messages_%algebras_locale_code%.properties",
        PROPERTIES_SOURCE.encode(),
    )


def test_properties_new_target_copies_comments_and_layout(properties_project, fake_api):
    _, target = properties_project
    translate_command.execute(language="uz")
    assert target.read_bytes() == PROPERTIES_EXPECTED.encode()


def test_properties_crlf_source_gives_crlf_target(properties_project, fake_api):
    source, target = properties_project
    source.write_bytes(PROPERTIES_SOURCE.replace("\n", "\r\n").encode())
    translate_command.execute(language="uz")
    assert target.read_bytes() == PROPERTIES_EXPECTED.replace("\n", "\r\n").encode()


@pytest.mark.parametrize("via", ["translate", "update"])
def test_properties_update_touches_only_changed_lines(properties_project, fake_api, via):
    source, target = properties_project
    translate_command.execute(language="uz")
    before = target.read_bytes()

    _edit_source(
        source,
        PROPERTIES_SOURCE.replace("farewell=Bye", "farewell=Goodbye")
        .replace("welcome = Welcome, {0}!\n", "welcome = Welcome, {0}!\nhint=Tip\n")
        .encode(),
    )
    if via == "translate":
        translate_command.execute(language="uz")
    else:
        translate_command.execute(language="uz", outdated_files=[(str(target), str(source))])

    removed, added = _changed_lines(before, target.read_bytes())
    assert removed == ["farewell=UZ Bye\n"]
    assert added == ["hint=UZ Tip\n", "farewell=UZ Goodbye\n"]
    assert target.read_bytes().decode().index("hint=") < target.read_bytes().decode().index("\n\n")


def test_properties_regenerate_from_scratch_still_rewrites(properties_project, fake_api):
    _, target = properties_project
    translate_command.execute(language="uz")
    translate_command.execute(language="uz", force="__all__", regenerate_from_scratch=True)
    text = target.read_bytes().decode()
    assert "# Greetings" not in text and "! legacy" not in text  # comments are not carried over
    assert "welcome=UZ Welcome, {0}!\n" in text


# ---------------------------------------------------------------------------
# CSV / TSV
# ---------------------------------------------------------------------------

CSV_SOURCE = (
    'key,en,uz\n'
    'greeting,"Hello, {0}",\n'
    '\n'
    'plain,Plain text,\n'
    '"quoted","Always quoted",""\n'
    'broken,Broken {0},\n'
)


@pytest.fixture
def csv_project(tmp_path, monkeypatch):
    return _project(tmp_path, monkeypatch, "loc/strings.csv", "loc/strings.csv", CSV_SOURCE.encode())


def test_csv_translate_keeps_line_endings_quoting_and_blank_lines(csv_project, fake_api):
    _, target = csv_project
    translate_command.execute(language="uz")
    assert target.read_bytes() == (
        'key,en,uz\n'
        'greeting,"Hello, {0}","UZ Hello, {0}"\n'
        '\n'
        'plain,Plain text,UZ Plain text\n'
        '"quoted","Always quoted","UZ Always quoted"\n'
        'broken,Broken {0},\n'  # rejected: left empty
    ).encode()


def test_csv_new_language_column_goes_at_the_end(tmp_path, monkeypatch, fake_api):
    source, _ = _project(
        tmp_path, monkeypatch, "loc/strings.csv", "loc/strings.csv",
        b'key,en\r\ngreeting,"Hello, {0}"\r\nplain,Plain\r\n',
    )
    translate_command.execute(language="uz")
    assert source.read_bytes() == (
        b'key,en,uz\r\ngreeting,"Hello, {0}","UZ Hello, {0}"\r\nplain,Plain,UZ Plain\r\n'
    )


def test_tsv_update_changes_only_the_changed_cell(tmp_path, monkeypatch, fake_api):
    source, _ = _project(
        tmp_path, monkeypatch, "loc/strings.tsv", "loc/strings.tsv",
        b'key\ten\tuz\na\tOne\t\nb\tTwo\t\n',
    )
    translate_command.execute(language="uz")
    before = source.read_bytes()
    _edit_source(source, before.replace(b"b\tTwo\tUZ Two", b"b\tTwo!\tUZ Two"))
    translate_command.execute(language="uz")
    assert source.read_bytes() == b'key\ten\tuz\na\tOne\tUZ One\nb\tTwo!\tUZ Two!\n'


def test_csv_separate_target_gets_new_rows_at_source_position(tmp_path, monkeypatch, fake_api):
    from algebras.utils.csv_handler import write_csv_file_in_place

    path = tmp_path / "uz.csv"
    path.write_bytes(b'key,uz\na,A\n\nc,C\n')
    write_csv_file_in_place(str(path), {"b": "B", "d": "D, d"}, "uz", key_order=["a", "b", "c", "d"])
    assert path.read_bytes() == b'key,uz\na,A\nb,B\n\nc,C\nd,"D, d"\n'


def test_csv_regenerate_from_scratch_still_rewrites(csv_project, fake_api):
    _, target = csv_project
    translate_command.execute(language="uz", regenerate_from_scratch=True)
    text = target.read_bytes()
    assert b"\r\n" in text  # csv.writer's line endings
    assert b"UZ Plain text" in text
