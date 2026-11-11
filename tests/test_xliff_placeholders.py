"""
XLIFF placeholder protection: inline elements (<x/>, <ph>, <g>, <pc> …) never reach the model as
editable markup, <target> gets the source's inline elements back as elements, damaged translations
are not written, and 'algebras placeholders' reports and fixes damaged targets in place.
"""

import json
import re
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.icu_message_service import ICUMessageService
from algebras.services.placeholders import mask, profile_for_path, verify
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import xliff as xliff_format
from algebras.utils.xliff_handler import (
    build_inline_content,
    flat_to_file_xml,
    read_xliff_file,
    update_xliff_targets,
    write_xliff_file,
)

NS12 = "{urn:oasis:names:tc:xliff:document:1.2}"
NS20 = "{urn:oasis:names:tc:xliff:document:2.0}"

ANGULAR_SOURCE = """<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" datatype="plaintext" original="ng2.template">
    <body>
      <trans-unit id="greet" datatype="html">
        <source>Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>, <x id="START_BOLD_TEXT" ctype="x-b" equiv-text="&lt;b&gt;"/>welcome<x id="CLOSE_BOLD_TEXT" ctype="x-b" equiv-text="&lt;/b&gt;"/>!</source>
        <note priority="1" from="description">Greeting</note>
      </trans-unit>
      <trans-unit id="items" datatype="html">
        <source>{VAR_PLURAL, plural, =0 {no items} =1 {one <x id="START_BOLD_TEXT" ctype="x-b" equiv-text="&lt;b&gt;"/>item<x id="CLOSE_BOLD_TEXT" ctype="x-b" equiv-text="&lt;/b&gt;"/>} other {<x id="INTERPOLATION" equiv-text="{{count}}"/> items}}</source>
      </trans-unit>
      <trans-unit id="left" datatype="html">
        <source>You have <x id="ICU" equiv-text="{count, plural, =1 {...} other {...}}" xid="123"/> left</source>
      </trans-unit>
      <trans-unit id="terms">
        <source>Accept <g id="1" ctype="x-a">the <g id="2" ctype="bold">terms</g> of use</g> &amp; continue</source>
      </trans-unit>
      <trans-unit id="native">
        <source>Line one<ph id="1">&lt;br/&gt;{x}</ph>line two</source>
      </trans-unit>
      <trans-unit id="plain">
        <source>Save</source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

XLIFF20_SOURCE = """<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en">
  <file id="f1" original="messages">
    <unit id="bold">
      <segment>
        <source>This is <pc id="1" type="fmt" dispStart="&lt;b&gt;" dispEnd="&lt;/b&gt;">really bold</pc> text by <ph id="2" equiv="{user}" disp="John"/>.</source>
      </segment>
    </unit>
    <unit id="codes">
      <segment>
        <source>Press <sc id="1" type="fmt" disp="[b]"/>Enter<ec startRef="1" type="fmt" disp="[/b]"/> now</source>
      </segment>
    </unit>
  </file>
</xliff>
"""

TOKEN = re.compile(r"⟦\d+⟧")


@pytest.fixture(autouse=True)
def xliff_fix_writer():
    # Other tests may replace writers with recording ones; use the real one here.
    register_fix_writer([".xlf", ".xliff"], xliff_format.write_fixes)
    yield


def _inline(element):
    """(tag, attributes, text) of every inline element in a <source>/<target>, in document order."""
    return [
        (child.tag.rsplit("}", 1)[-1], dict(child.attrib), child.text if not len(child) else None)
        for child in element.iter()
        if child is not element
    ]


def _units(path, ns):
    root = ET.parse(path).getroot()
    units = {}
    for unit in root.iter(f"{ns}trans-unit"):
        units[unit.get("id")] = (unit.find(f"{ns}source"), unit.find(f"{ns}target"))
    for unit in root.iter(f"{ns}unit"):
        segment = unit.find(f"{ns}segment")
        units[unit.get("id")] = (segment.find(f"{ns}source"), segment.find(f"{ns}target"), segment)
    return units


# ---------------------------------------------------------------------------
# Reading, masking and writing
# ---------------------------------------------------------------------------


def test_reader_keeps_inline_elements_as_markup(tmp_path):
    path = tmp_path / "messages.xlf"
    path.write_text(ANGULAR_SOURCE, encoding="utf-8")
    units = {u["id"]: u["source"] for u in read_xliff_file(str(path))["files"][0]["trans-units"]}

    greet = units["greet"]
    assert greet.startswith("Hello <x id=\"INTERPOLATION\" ")
    assert "ns0" not in greet and "xmlns" not in greet
    assert greet.count("welcome") == 1  # tails are not duplicated
    assert flat_to_file_xml(greet) == (
        'Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>, '
        '<x id="START_BOLD_TEXT" ctype="x-b" equiv-text="&lt;b&gt;"/>welcome'
        '<x id="CLOSE_BOLD_TEXT" ctype="x-b" equiv-text="&lt;/b&gt;"/>!'
    )
    assert units["terms"] == 'Accept <g id="1" ctype="x-a">the <g id="2" ctype="bold">terms</g> of use</g> & continue'
    assert flat_to_file_xml(units["native"]) == 'Line one<ph id="1">&lt;br/&gt;{x}</ph>line two'


def test_profile_masks_elements_and_never_exposes_attributes(tmp_path):
    path = tmp_path / "messages.xlf"
    path.write_text(ANGULAR_SOURCE, encoding="utf-8")
    units = {u["id"]: u["source"] for u in read_xliff_file(str(path))["files"][0]["trans-units"]}
    profile = profile_for_path("src/locale/messages.xlf")
    assert profile is xliff_format.XLIFF_PROFILE

    greet = mask(units["greet"], profile)
    assert greet.text == "Hello ⟦0⟧, ⟦1⟧welcome⟦2⟧!"

    # Paired <g>: open and close tokens, the text between them is translated.
    terms = mask(units["terms"], profile)
    assert terms.text == "Accept ⟦0⟧the ⟦1⟧terms⟦2⟧ of use⟦3⟧ & continue"

    # 1.2 <ph> holds native code: one token, content included.
    native = mask(units["native"], profile)
    assert native.text == "Line one⟦0⟧line two"
    assert len(native.placeholders) == 1

    # An Angular <x id="ICU" equiv-text="{count, plural, ...}"/> is not mistaken for an ICU message.
    service = ICUMessageService()
    segments, _ = service.preprocess_texts([units["left"]])
    assert [mask(s, profile).text for s in segments] == ["You have ⟦0⟧ left"]


def test_icu_runs_first_then_inline_elements_are_masked_per_segment(tmp_path):
    path = tmp_path / "messages.xlf"
    path.write_text(ANGULAR_SOURCE, encoding="utf-8")
    items = {u["id"]: u["source"] for u in read_xliff_file(str(path))["files"][0]["trans-units"]}["items"]
    profile = xliff_format.XLIFF_PROFILE
    service = ICUMessageService()

    assert service.is_icu(items)  # equiv-text="{{count}}" does not break the ICU parse
    segments, mapping = service.preprocess_texts([items])
    masked = [mask(s, profile) for s in segments]
    assert [m.text for m in masked] == ["no items", "one ⟦0⟧item⟦1⟧", "⟦0⟧ items"]

    from algebras.services.placeholders import unmask

    translated = [unmask("FR " + m.text, m, profile) for m in masked]
    rebuilt = service.postprocess_translations(mapping, translated)[0]
    assert rebuilt.startswith("{VAR_PLURAL, plural, =0 {FR no items} =1 {FR one <x id=\"START_BOLD_TEXT\"")
    assert not verify(items, rebuilt, profile)


def test_write_rebuilds_target_inline_elements_identical_to_source(tmp_path):
    path = tmp_path / "messages.xlf"
    path.write_text(ANGULAR_SOURCE, encoding="utf-8")
    content = read_xliff_file(str(path))
    translations = {u["id"]: u["source"] for u in content["files"][0]["trans-units"]}
    out = tmp_path / "messages.fr.xlf"

    write_xliff_file(str(out), update_xliff_targets({"version": "1.2", "files": []}, translations, content, "translated"), "en", "fr", "translated")

    raw = out.read_text(encoding="utf-8")
    assert "&lt;x" not in raw and "ns0" not in raw
    assert '<target state="translated">Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>, ' in raw
    for unit_id, (source, target) in _units(out, NS12).items():
        assert _inline(target) == _inline(source), unit_id
        assert ET.tostring(target, encoding="unicode").split(">", 1)[1].rsplit("<", 1)[0] == ET.tostring(
            source, encoding="unicode"
        ).split(">", 1)[1].rsplit("<", 1)[0], unit_id
    # And the inline elements are the ones in the original file.
    original = _units(path, NS12)
    for unit_id, (source, target) in _units(out, NS12).items():
        assert _inline(target) == _inline(original[unit_id][0])


def test_build_rejects_broken_pairing():
    with pytest.raises(ValueError):
        build_inline_content('a <g id="1">b')
    with pytest.raises(ValueError):
        build_inline_content('a </g> <g id="1">b')
    with pytest.raises(ValueError):
        build_inline_content('<g id="1"><mrk id="m">b</g></mrk>')


def test_update_keeps_previous_target_and_state_when_translation_is_damaged(tmp_path):
    source = {"version": "1.2", "files": [{"trans-units": [
        {"id": "greet", "source": 'Hi <x id="INTERPOLATION" equiv-text="name"/>'},
        {"id": "new", "source": 'Go <g id="1">now</g>'},
    ]}]}
    target = {"version": "1.2", "files": [{"trans-units": [
        {"id": "greet", "source": 'Hi <x id="INTERPOLATION" equiv-text="name"/>',
         "target": 'Salut <x id="INTERPOLATION" equiv-text="name"/>', "state": "final"},
    ]}]}
    updated = update_xliff_targets(
        target,
        {"greet": 'Bonjour <x id="INTERPOLATION" equiv-text="nom"/>', "new": 'Va <g id="1">maintenant'},
        source,
        "translated",
    )
    units = {u["id"]: u for u in updated["files"][0]["trans-units"]}
    assert units["greet"]["target"] == 'Salut <x id="INTERPOLATION" equiv-text="name"/>'
    assert units["greet"]["state"] == "final"
    assert units["new"]["target"] == ""
    assert "state" not in units["new"]


# ---------------------------------------------------------------------------
# translate: a model that damages inline elements
# ---------------------------------------------------------------------------


def _project(tmp_path, monkeypatch, source_text, name="messages.xlf"):
    locale = tmp_path / "src" / "locale"
    locale.mkdir(parents=True)
    (locale / name).write_text(source_text, encoding="utf-8")
    stem, ext = name.rsplit(".", 1)
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "fr"],
                "source_files": {
                    f"src/locale/{name}": {"destination_path": f"src/locale/{stem}.%algebras_locale_code%.{ext}"}
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return locale / name, locale / f"{stem}.fr.{ext}"


def _hostile(text):
    """A model that rewrites equiv-text, drops a closing tag and swaps nesting (also on retry)."""
    if text == "Hello ⟦0⟧, ⟦1⟧welcome⟦2⟧!":
        return 'Bonjour <x id="INTERPOLATION" equiv-text="{{ nom }}"/>, ⟦1⟧bienvenue⟦2⟧ !'
    if text == "one ⟦0⟧item⟦1⟧":
        return "un ⟦0⟧article"
    if text == "Accept ⟦0⟧the ⟦1⟧terms⟦2⟧ of use⟦3⟧ & continue":
        return "Acceptez ⟦1⟧les ⟦0⟧conditions⟦2⟧ d'utilisation⟦3⟧ et continuez"
    return "FR " + text


def _client(sent, translate=_hostile):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append(list(texts))
        return [translate(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    return client


def test_translate_never_writes_damaged_inline_elements(tmp_path, monkeypatch):
    source, target = _project(tmp_path, monkeypatch, ANGULAR_SOURCE)
    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_client(sent)):
        translate_command.execute(language="fr", force="__all__")

    raw = target.read_text(encoding="utf-8")
    units = _units(target, NS12)
    original = _units(source, NS12)

    # The model never saw markup or attribute values.
    for text in (t for batch in sent for t in batch):
        assert "<" not in text and "equiv" not in text and "" not in text, text

    # Damaged units: no <target> (a new file is built from the source), so no translated state.
    for unit_id in ("greet", "items", "terms"):
        assert units[unit_id][1] is None, unit_id
    assert "nom" not in raw and "un " not in raw and "Acceptez" not in raw

    # Good units: translated, inline elements identical to the source file's.
    for unit_id in ("left", "native", "plain"):
        assert units[unit_id][1].get("state") == "translated"
        assert "FR" in ET.tostring(units[unit_id][1], encoding="unicode")
        assert _inline(units[unit_id][1]) == _inline(original[unit_id][0])
    assert '<ph id="1">&lt;br/&gt;{x}</ph>' in raw


def test_translate_retry_keeps_previous_target_and_state(tmp_path, monkeypatch):
    source, target = _project(tmp_path, monkeypatch, ANGULAR_SOURCE)
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_client([], lambda t: "FR " + t)):
        translate_command.execute(language="fr", force="__all__")
    before = _units(target, NS12)
    greet_before = ET.tostring(before["greet"][1], encoding="unicode")
    assert "FR Hello" in greet_before

    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_client(sent)):
        translate_command.execute(language="fr", force="greet,plain")

    after = _units(target, NS12)
    assert ET.tostring(after["greet"][1], encoding="unicode") == greet_before  # damaged: previous kept
    assert after["greet"][1].get("state") == "translated"
    assert "FR FR Save" not in ET.tostring(after["plain"][1], encoding="unicode")
    # Units that were not retranslated keep their translation (not replaced by the source text).
    assert "FR no items" in ET.tostring(after["items"][1], encoding="unicode")
    assert len(sent) == 3  # first attempt + a batch retry + a retry of the damaged text alone


def test_translate_xliff20_pc_and_ph(tmp_path, monkeypatch):
    source, target = _project(tmp_path, monkeypatch, XLIFF20_SOURCE)
    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_client(sent, lambda t: "FR " + t)):
        translate_command.execute(language="fr", force="__all__")

    assert sorted(t for batch in sent for t in batch) == [
        "Press ⟦0⟧Enter⟦1⟧ now",
        "This is ⟦0⟧really bold⟦1⟧ text by ⟦2⟧.",
    ]
    raw = target.read_text(encoding="utf-8")
    assert 'version="2.0"' in raw and "<segment" in raw
    original = _units(source, NS20)
    for unit_id, (src, tgt, segment) in _units(target, NS20).items():
        assert [(t, a) for t, a, _ in _inline(tgt)] == [(t, a) for t, a, _ in _inline(original[unit_id][0])]
        assert segment.get("state") == "translated"
    assert '<pc id="1" type="fmt" dispStart="&lt;b&gt;" dispEnd="&lt;/b&gt;">really bold</pc>' in raw


def test_xliff20_swapped_sc_ec_is_rejected():
    source = 'Press <sc id="1" type="fmt" disp="[b]"/>Enter<ec startRef="1" type="fmt" disp="[/b]"/> now'
    swapped = 'Appuyez <ec startRef="1" type="fmt" disp="[/b]"/>Entrée<sc id="1" type="fmt" disp="[b]"/>'
    codes = [p.code for p in verify(source, swapped, xliff_format.XLIFF_PROFILE)]
    assert codes == ["inline_nesting_broken"]
    assert xliff_format.translation_problem(source, swapped)


# ---------------------------------------------------------------------------
# 'algebras placeholders': report -> --fix -> clean -> idempotent
# ---------------------------------------------------------------------------

CHECK_SOURCE = """<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" datatype="plaintext" original="ng2.template">
    <body>
      <trans-unit id="greet" datatype="html">
        <source>Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>!</source>
      </trans-unit>
      <trans-unit id="bold" datatype="html">
        <source><x id="START_BOLD_TEXT" ctype="x-b" equiv-text="&lt;b&gt;"/>Welcome<x id="CLOSE_BOLD_TEXT" ctype="x-b" equiv-text="&lt;/b&gt;"/> back</source>
      </trans-unit>
      <trans-unit id="raw">
        <source>Hi {{ name }}, you have {count} messages</source>
      </trans-unit>
      <trans-unit id="terms">
        <source>Accept <g id="1">the <g id="2">terms</g></g></source>
      </trans-unit>
      <trans-unit id="ok">
        <source>Save <x id="INTERPOLATION" equiv-text="{{ n }}"/></source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

CHECK_TARGET = """<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="ru" datatype="plaintext" original="ng2.template">
    <body>
      <!-- reviewed by the client -->
      <trans-unit id="greet" datatype="html">
        <source>Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>!</source>
        <target state="translated">Привет <x id="INTERPOLATION" equiv-text="{{ имя }}"/>!</target>
        <note from="description">Greeting</note>
      </trans-unit>
      <trans-unit id="bold" datatype="html">
        <source><x id="START_BOLD_TEXT" ctype="x-b" equiv-text="&lt;b&gt;"/>Welcome<x id="CLOSE_BOLD_TEXT" ctype="x-b" equiv-text="&lt;/b&gt;"/> back</source>
        <target state="final"><x id="START_BOLD_TEXT" ctype="x-b" equiv-text="&lt;b&gt;"/>С возвращением</target>
      </trans-unit>
      <trans-unit id="raw">
        <source>Hi {{ name }}, you have {count} messages</source>
        <target state="translated">Привет {{ имя }}, у вас {count} сообщений</target>
      </trans-unit>
      <trans-unit id="terms">
        <source>Accept <g id="1">the <g id="2">terms</g></g></source>
        <target state="needs-review-translation">Примите <g id="2">условия <g id="1">использования</g></g></target>
      </trans-unit>
      <trans-unit id="ok">
        <source>Save <x id="INTERPOLATION" equiv-text="{{ n }}"/></source>
        <target state="final">Сохранить <x id="INTERPOLATION" equiv-text="{{ n }}"/></target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


@pytest.fixture
def check_project(tmp_path, monkeypatch):
    locale = tmp_path / "src" / "locale"
    locale.mkdir(parents=True)
    (locale / "messages.xlf").write_text(CHECK_SOURCE, encoding="utf-8")
    target = locale / "messages.ru.xlf"
    target.write_text(CHECK_TARGET, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {
                    "src/locale/messages.xlf": {"destination_path": "src/locale/messages.%algebras_locale_code%.xlf"}
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return target


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_inline_problems(check_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    codes = {i["key"]: sorted(p["code"] for p in i["problems"]) for i in report["issues"]}
    assert codes == {
        "greet": ["inline_attr_changed"],
        "bold": ["inline_nesting_broken", "missing"],
        "raw": ["extra", "missing"],
        "terms": ["inline_nesting_broken"],
    }
    greet = next(i for i in report["issues"] if i["key"] == "greet")
    assert "equiv-text" in greet["problems"][0]["message"]
    assert "{{ имя }}" in greet["target"]  # reports show attribute values as written
    fixable = {i["key"] for i in report["issues"] if i["fixed"] is not None}
    assert fixable == {"greet", "raw"}


def test_fix_repairs_in_place_and_is_idempotent(check_project, capsys):
    code, report = _report(capsys, fix=True)
    assert code == 2  # bold and terms need retranslation
    status = {i["key"]: i["status"] for i in report["issues"]}
    assert status == {"greet": "fixed", "raw": "fixed", "bold": "unresolved", "terms": "unresolved"}

    expected = CHECK_TARGET.replace('equiv-text="{{ имя }}"', 'equiv-text="{{ name }}"').replace(
        "Привет {{ имя }},", "Привет {{ name }},"
    )
    assert check_project.read_text(encoding="utf-8") == expected  # only the two targets changed

    code, report = _report(capsys)
    assert {i["key"] for i in report["issues"]} == {"bold", "terms"}

    code, report = _report(capsys, fix=True)
    assert code == 2
    assert check_project.read_text(encoding="utf-8") == expected


def test_dry_run_writes_nothing(check_project, capsys):
    _report(capsys, fix=True, dry_run=True)
    assert check_project.read_text(encoding="utf-8") == CHECK_TARGET


def test_changed_id_is_restored_by_unique_slot():
    source = 'Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>!'
    target = 'Привет <x id="ИНТЕРПОЛЯЦИЯ" equiv-text="{{ name }}"/>!'
    assert xliff_format.repair_unit(source, target) == 'Привет <x id="INTERPOLATION" equiv-text="{{ name }}"/>!'
