"""
XLIFF write fidelity: a new target is built from the source file (notes, context, attributes kept,
target language set), an existing target only gets its changed <target>s rewritten, translate="no"
units are never sent or changed, every segment of a 2.0 unit is translated, and nothing printed
contains the private-use characters of the flat form.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from algebras.commands import translate_command
from algebras.utils.xliff_handler import read_xliff_file, update_xliff_targets

NS12 = "{urn:oasis:names:tc:xliff:document:1.2}"
NS20 = "{urn:oasis:names:tc:xliff:document:2.0}"
PRIVATE_USE = re.compile("[-]")

SOURCE_12 = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="" datatype="plaintext" original="ng2.template">
    <header>
      <note>Exported from the app</note>
    </header>
    <body>
      <!-- home page -->
      <trans-unit id="greet" resname="home.greeting" datatype="html" approved="no">
        <source>Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>!</source>
        <context-group purpose="location">
          <context context-type="sourcefile">src/app/home.html</context>
          <context context-type="linenumber">12</context>
        </context-group>
        <note priority="1" from="description">Greeting on the home page</note>
      </trans-unit>
      <trans-unit id="brand" resname="brand" translate="no">
        <source>Algebras</source>
        <note>Product name, never translated</note>
      </trans-unit>
      <group id="codes" translate="no">
        <trans-unit id="code" resname="code">
          <source>ERR-42</source>
        </trans-unit>
      </group>
      <trans-unit id="bye" resname="footer.bye" xml:space="preserve">
        <source>Goodbye</source>
        <note from="meaning">Footer</note>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

SOURCE_20 = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en">
  <file id="f1" original="app">
    <notes>
      <note>File level note</note>
    </notes>
    <unit id="intro" name="intro.text">
      <notes>
        <note category="description">Three sentences shown together</note>
      </notes>
      <segment id="s1">
        <source>Welcome to the app.</source>
      </segment>
      <ignorable>
        <source> </source>
      </ignorable>
      <segment id="s2">
        <source>Press <ph id="1" disp="{enter}" equiv=""/> to start.</source>
      </segment>
      <ignorable>
        <source> </source>
      </ignorable>
      <segment id="s3" state="initial">
        <source>Have fun!</source>
      </segment>
    </unit>
    <unit id="title">
      <segment>
        <source>Home</source>
      </segment>
    </unit>
    <unit id="logo" translate="no">
      <segment>
        <source>ALGEBRAS</source>
      </segment>
    </unit>
  </file>
</xliff>
"""


@pytest.fixture
def fake_api(monkeypatch):
    """Fake Algebras AI: records every text and context sent; `model` maps one masked text."""
    calls = {"texts": [], "contexts": [], "model": lambda t: "FR " + t}

    def translate_batch(self, texts, *args, **kwargs):
        calls["texts"].extend(texts)
        calls["contexts"].extend(kwargs.get("contexts") or [None] * len(texts))
        return [calls["model"](t) for t in texts]

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    monkeypatch.setattr(
        "algebras.services.api_client.AlgebrasAIClient.translate",
        lambda self, text, *a, **k: calls["model"](text),
    )
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return calls


def _project(tmp_path, monkeypatch, source_text):
    locale = tmp_path / "src" / "locale"
    locale.mkdir(parents=True)
    source = locale / "messages.xlf"
    source.write_text(source_text, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "fr"],
                "source_files": {
                    "src/locale/messages.xlf": {"destination_path": "src/locale/messages.%algebras_locale_code%.xlf"}
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return source, locale / "messages.fr.xlf"


def _edit_source(path, text):
    """Change the source and make it newer than the target, as an edit after a translate run does."""
    path.write_text(text, encoding="utf-8")
    stamp = os.path.getmtime(path) + 10
    os.utime(path, (stamp, stamp))


def _block(text, unit_id, tag="trans-unit"):
    m = re.search(r'<%s id="%s".*?</%s>' % (tag, re.escape(unit_id), tag), text, re.DOTALL)
    return m.group(0)


def _changed_lines(before, after):
    a, b = before.splitlines(), after.splitlines()
    return [line for line in a if line not in b], [line for line in b if line not in a]


# ---------------------------------------------------------------------------
# XLIFF 1.2
# ---------------------------------------------------------------------------


def test_new_target_is_built_from_the_source_with_all_metadata(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_12)
    translate_command.execute(language="fr")

    raw = target.read_text(encoding="utf-8")
    # Apart from the targets and the target language, the file is the source byte for byte.
    without_targets = re.sub(r"\n\s*<target\b.*?</target>", "", raw, flags=re.DOTALL)
    assert without_targets == SOURCE_12.replace('target-language=""', 'target-language="fr"')

    for kept in (
        "<!-- home page -->",
        '<note priority="1" from="description">Greeting on the home page</note>',
        '<context context-type="sourcefile">src/app/home.html</context>',
        'resname="home.greeting" datatype="html" approved="no"',
        'xml:space="preserve"',
        "<note>Exported from the app</note>",
    ):
        assert kept in raw

    units = {u.get("id"): u for u in ET.parse(target).getroot().iter(f"{NS12}trans-unit")}
    greet = units["greet"].find(f"{NS12}target")
    assert greet.get("state") == "translated"
    assert greet.text == "FR Hello " and greet[0].get("equiv-text") == "{{ name }}"
    assert units["bye"].find(f"{NS12}target").text == "FR Goodbye"
    # The target follows the source, before context and notes.
    children = [c.tag.replace(NS12, "") for c in units["greet"]]
    assert children == ["source", "target", "context-group", "note"]


def test_translate_no_units_are_never_sent_or_changed(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_12)
    translate_command.execute(language="fr")
    assert not any("Algebras" in t or "ERR-42" in t for t in fake_api["texts"])
    raw = target.read_text(encoding="utf-8")
    assert _block(raw, "brand") == _block(SOURCE_12, "brand")
    assert _block(raw, "code") == _block(SOURCE_12, "code")

    # A hand-written target of a translate="no" unit survives a forced run, even when named.
    hand = raw.replace("<source>Algebras</source>", "<source>Algebras</source>\n        <target>Algebras®</target>")
    target.write_text(hand, encoding="utf-8")
    fake_api["texts"].clear()
    translate_command.execute(language="fr", force="__all__")
    translate_command.execute(language="fr", force="brand,code")
    assert target.read_text(encoding="utf-8") == hand
    assert not any("Algebras" in t or "ERR-42" in t for t in fake_api["texts"])


def test_second_run_changes_only_the_changed_target(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_12)
    translate_command.execute(language="fr")

    # Reviewer edits in the target: a comment, a note and a state. They must all survive.
    edited = target.read_text(encoding="utf-8")
    edited = edited.replace("    <body>\n", "    <body>\n      <!-- reviewed 2026-11 -->\n")
    edited = edited.replace("<note from=\"meaning\">Footer</note>", "<note from=\"meaning\">Footer</note>\n        <note from=\"reviewer\">ok</note>")
    edited = edited.replace('<target state="translated">FR Hello', '<target state="final">FR Hello')
    target.write_text(edited, encoding="utf-8")
    os.utime(target, (os.path.getmtime(source) + 5,) * 2)

    _edit_source(source, SOURCE_12.replace("<source>Goodbye</source>", "<source>See you</source>"))
    translate_command.execute(language="fr")

    after = target.read_text(encoding="utf-8")
    removed, added = _changed_lines(edited, after)
    assert removed == ['        <target state="translated">FR Goodbye</target>']
    assert added == ['        <target state="translated">FR See you</target>']


@pytest.mark.parametrize("only_missing", [False, True], ids=["full", "only-missing"])
def test_new_source_unit_is_copied_into_an_existing_target(tmp_path, monkeypatch, fake_api, only_missing):
    source, target = _project(tmp_path, monkeypatch, SOURCE_12)
    translate_command.execute(language="fr")
    before = target.read_text(encoding="utf-8")

    new_unit = (
        '      <trans-unit id="new" resname="new.one">\n'
        "        <source>New text</source>\n"
        '        <note from="description">Added later</note>\n'
        "      </trans-unit>\n"
    )
    _edit_source(source, SOURCE_12.replace("      <trans-unit id=\"bye\"", new_unit + "      <trans-unit id=\"bye\""))
    fake_api["texts"].clear()
    translate_command.execute(language="fr", only_missing=only_missing)
    if only_missing:
        assert fake_api["texts"] == ["New text"]

    after = target.read_text(encoding="utf-8")
    removed, added = _changed_lines(before, after)
    assert removed == []
    assert _block(after, "new") == (
        '<trans-unit id="new" resname="new.one">\n'
        "        <source>New text</source>\n"
        '        <target state="translated">FR New text</target>\n'
        '        <note from="description">Added later</note>\n'
        "      </trans-unit>"
    )
    ids = [u.get("id") for u in ET.parse(target).getroot().iter(f"{NS12}trans-unit")]
    assert ids == ["greet", "brand", "code", "new", "bye"]
    # Placed in <body> after the translate="no" group, not inside it, at the source's indentation.
    assert "      </group>\n      <trans-unit id=\"new\"" in after
    group = next(ET.parse(target).getroot().iter(f"{NS12}group"))
    assert [u.get("id") for u in group] == ["code"]


def test_new_unit_of_a_translate_no_group_is_copied_unchanged(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_12)
    translate_command.execute(language="fr")
    fake_api["texts"].clear()

    code2 = '        <trans-unit id="code2">\n          <source>ERR-43</source>\n        </trans-unit>\n'
    _edit_source(source, SOURCE_12.replace("      </group>", code2 + "      </group>"))
    translate_command.execute(language="fr", force="__all__")

    raw = target.read_text(encoding="utf-8")
    assert _block(raw, "codes", "group") == _block(source.read_text(encoding="utf-8"), "codes", "group")
    assert not any("ERR-43" in t for t in fake_api["texts"])


def test_untranslated_unit_of_a_new_target_gets_no_target(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_12)
    # The model drops the inline element of 'greet' every time: it stays untranslated.
    fake_api["model"] = lambda t: "Bonjour !" if "⟦0⟧" in t else "FR " + t
    translate_command.execute(language="fr")

    units = {u.get("id"): u for u in ET.parse(target).getroot().iter(f"{NS12}trans-unit")}
    assert units["greet"].find(f"{NS12}target") is None
    assert units["bye"].find(f"{NS12}target").text == "FR Goodbye"


# ---------------------------------------------------------------------------
# XLIFF 2.0
# ---------------------------------------------------------------------------


def _segments(path):
    root = ET.parse(path).getroot()
    return {u.get("id"): u.findall(f"{NS20}segment") for u in root.iter(f"{NS20}unit")}


def test_xliff20_every_segment_is_translated_with_its_unit_as_context(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_20)
    translate_command.execute(language="fr")

    sent = dict(zip(fake_api["texts"], fake_api["contexts"]))
    assert set(sent) == {"Welcome to the app.", "Press ⟦0⟧ to start.", "Have fun!", "Home"}
    for text in ("Welcome to the app.", "Press ⟦0⟧ to start.", "Have fun!"):
        assert "Welcome to the app. Press to start. Have fun!" in sent[text]
    assert sent["Home"] is None

    raw = target.read_text(encoding="utf-8")
    assert 'trgLang="fr"' in raw
    for kept in (
        "<note>File level note</note>",
        '<note category="description">Three sentences shown together</note>',
        '<unit id="intro" name="intro.text">',
    ):
        assert kept in raw
    assert raw.count("<ignorable>\n        <source> </source>\n      </ignorable>") == 2
    assert _block(raw, "logo", "unit") == _block(SOURCE_20, "logo", "unit")

    segments = _segments(target)
    intro = segments["intro"]
    assert [s.get("id") for s in intro] == ["s1", "s2", "s3"]
    assert [s.get("state") for s in intro] == ["translated"] * 3
    targets = [s.find(f"{NS20}target") for s in intro]
    assert targets[0].text == "FR Welcome to the app."
    assert targets[1].text == "FR Press " and targets[1][0].get("disp") == "{enter}"
    assert targets[2].text == "FR Have fun!"
    assert segments["title"][0].find(f"{NS20}target").text == "FR Home"
    assert segments["logo"][0].find(f"{NS20}target") is None

    # Read back: one key per segment, and nothing left to translate.
    keys = [u["id"] for u in read_xliff_file(str(target))["files"][0]["trans-units"]]
    assert keys == ["intro#1", "intro#2", "intro#3", "title", "logo"]


def test_xliff20_second_run_changes_only_the_changed_segment(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch, SOURCE_20)
    translate_command.execute(language="fr")
    before = target.read_text(encoding="utf-8")

    _edit_source(source, SOURCE_20.replace("<source>Have fun!</source>", "<source>Enjoy!</source>"))
    translate_command.execute(language="fr")

    removed, added = _changed_lines(before, target.read_text(encoding="utf-8"))
    assert removed == ["        <target>FR Have fun!</target>"]
    assert added == ["        <target>FR Enjoy!</target>"]


# ---------------------------------------------------------------------------
# Printed output
# ---------------------------------------------------------------------------


def test_printed_output_has_no_private_use_characters(tmp_path, monkeypatch, fake_api, capsys):
    source, target = _project(tmp_path, monkeypatch, SOURCE_20.replace('disp="{enter}"', 'disp="{{ key }}"'))
    # The model loses the inline element: reported, retried and left untranslated.
    fake_api["model"] = lambda t: t.replace("⟦0⟧", "").replace("Press", "Appuyez")
    translate_command.execute(language="fr", verbose=True)

    out = capsys.readouterr().out
    assert "lost" in out and "{{ key }}" in out
    assert not PRIVATE_USE.search(out), [line for line in out.splitlines() if PRIVATE_USE.search(line)]


def test_kept_target_message_decodes_attribute_values(tmp_path, capsys):
    path = tmp_path / "messages.xlf"
    path.write_text(SOURCE_12, encoding="utf-8")
    source = read_xliff_file(str(path))
    flat = {u["id"]: u["source"] for u in source["files"][0]["trans-units"]}
    target = {"version": "1.2", "files": [{"trans-units": [
        {"id": "greet", "source": flat["greet"], "target": flat["greet"], "state": "final"},
    ]}]}
    damaged = flat["greet"].replace("name", "nom")
    updated = update_xliff_targets(target, {"greet": damaged}, source, "translated")

    assert updated["files"][0]["trans-units"][0]["target"] == flat["greet"]
    out = capsys.readouterr().out
    assert "Kept the previous target of 'greet'" in out and "{{ name }}" in out
    assert not PRIVATE_USE.search(out)
