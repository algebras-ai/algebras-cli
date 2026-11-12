"""
Android string resources: full inner content (xliff:g, <b>) survives read -> translate -> write,
placeholders survive a model that transliterates them, plural forms are expanded for the target
language, and 'algebras placeholders' finds and repairs the client's uz-Cyrl corruptions.
"""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.config import Config
from algebras.services.placeholders import extract, mask, profile_for_path
from algebras.services.placeholders.fix_writers import get_fix_writer, register_fix_writer
from algebras.services.placeholders.formats import android_xml as android_format
from algebras.utils import android_plurals
from algebras.utils.android_xml_handler import (
    read_android_xml_file,
    update_android_xml_values,
    write_android_xml_file,
    write_android_xml_file_in_place,
)
from tests.aapt_string_rules import assert_aapt_valid

_LATIN_TO_CYRILLIC = str.maketrans(dict(zip("sdcSDabeiklmnoprtuvxyz", "сдсСДабеиклмнопртувхйз")))


def transliterate(text: str) -> str:
    """What the model did for uz-Cyrl: every Latin letter becomes Cyrillic (tokens survive)."""
    return text.translate(_LATIN_TO_CYRILLIC)


# Java Formatter conversions. Anything else after "%[n$]" throws UnknownFormatConversionException.
_JAVA_SPECIFIER = re.compile(r"%(\d+\$)?([-#+ 0,(]*)(\d+)?(\.\d+)?([tT])?(.)")
_JAVA_CONVERSIONS = set("bBhHsScCdoxXeEfgGaA%n")


def assert_java_format_valid(text: str) -> None:
    """A Python stand-in for java.lang.String.format's conversion check."""
    for m in _JAVA_SPECIFIER.finditer(text):
        conversion = m.group(6)
        if m.group(5):
            assert conversion.isascii() and conversion.isalpha(), f"bad date conversion in {text!r}"
        else:
            assert conversion in _JAVA_CONVERSIONS, f"UnknownFormatConversion {m.group(0)!r} in {text!r}"


@pytest.fixture(autouse=True)
def android_fix_writer():
    # Other tests may replace the .xml writer with a recording one; use the real one here.
    register_fix_writer([".xml"], android_format.write_fixes)
    yield


# ---------------------------------------------------------------------------
# Reader / writer
# ---------------------------------------------------------------------------

SOURCE_RESOURCES = r"""<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">
    <!-- Greeting shown on the home screen -->
    <string name="hello">Hello <xliff:g id="name" example="Bob">%1$s</xliff:g>!</string>
    <string name="bold">It\'s <b>really</b> 100%% &amp; more</string>
    <string name="cdata"><![CDATA[<b>Hi</b> %1$s]]></string>
    <string name="literal_tag">Use &lt;b&gt; tags</string>
    <string name="percent" formatted="false">100% sure, %s and %s</string>
    <string name="app_name" translatable="false">MyApp</string>
    <string name="alias">@string/app_name</string>
    <string name="newline">Line\nTwo %n</string>
    <plurals name="Quiz.points">
        <item quantity="one">%1$d point</item>
        <item quantity="other"><xliff:g id="count">%1$d</xliff:g> points</item>
    </plurals>
</resources>
"""


@pytest.fixture
def source_xml(tmp_path):
    path = tmp_path / "values" / "strings.xml"
    path.parent.mkdir()
    path.write_text(SOURCE_RESOURCES, encoding="utf-8")
    return path


def test_reader_keeps_child_elements_and_skips_untranslatable(source_xml):
    data = read_android_xml_file(str(source_xml))

    assert data["hello"] == 'Hello <xliff:g id="name" example="Bob">%1$s</xliff:g>!'
    assert data["bold"] == "It's <b>really</b> 100%% & more"
    assert data["cdata"] == "<b>Hi</b> %1$s"
    assert data["literal_tag"] == "Use <b> tags"
    assert data["percent"] == "100% sure, %s and %s"
    assert data["newline"] == "Line\nTwo %n"
    assert data["Quiz.points.__plurals__"] == {
        "one": "%1$d point",
        "other": '<xliff:g id="count">%1$d</xliff:g> points',
    }
    assert "app_name" not in data  # translatable="false"
    assert "alias" not in data  # whole-value resource reference


def test_full_write_round_trips_markup_and_escapes(source_xml, tmp_path):
    data = read_android_xml_file(str(source_xml))
    target = tmp_path / "values-de" / "strings.xml"
    target.parent.mkdir()

    write_android_xml_file(str(target), data, source_file=str(source_xml))
    raw = target.read_text(encoding="utf-8")
    assert_aapt_valid(target)

    assert '<string name="hello">Hello <xliff:g id="name" example="Bob">%1$s</xliff:g>!</string>' in raw
    assert "<b>really</b> 100%% &amp; more" in raw  # no double escaping
    assert "&lt;xliff" not in raw
    # Text that was not markup in the source stays text.
    assert '<string name="cdata">&lt;b&gt;Hi&lt;/b&gt; %1$s</string>' in raw
    assert '<string name="literal_tag">Use &lt;b&gt; tags</string>' in raw
    assert '<string name="percent" formatted="false">' in raw
    assert r"Line\nTwo %n" in raw
    assert read_android_xml_file(str(target)) == data


def test_in_place_write_restores_markup_as_elements(source_xml, tmp_path):
    target = tmp_path / "values-uz" / "strings.xml"
    target.parent.mkdir()
    target.write_text(SOURCE_RESOURCES, encoding="utf-8")
    content = read_android_xml_file(str(target))
    content["hello"] = 'Салом <xliff:g id="name" example="Bob">%1$s</xliff:g>!'
    content["Quiz.points.__plurals__"] = {
        "one": "%1$d очко",
        "few": "%1$d очка",
        "other": '<xliff:g id="count">%1$d</xliff:g> очков',
    }

    write_android_xml_file_in_place(
        str(target), content, {"hello", "Quiz.points.__plurals__.few"}, source_file=str(source_xml)
    )
    raw = target.read_text(encoding="utf-8")
    assert_aapt_valid(target)

    assert '<string name="hello">Салом <xliff:g id="name" example="Bob">%1$s</xliff:g>!</string>' in raw
    assert "<!-- Greeting shown on the home screen -->" in raw
    assert 'xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2"' in raw
    # The missing CLDR form is inserted in order, and keys are not added as <string> elements.
    assert re.search(r'quantity="one">%1\$d очко</item>\s*<item quantity="few">%1\$d очка</item>\s*<item quantity="other">', raw)
    assert "__plurals__" not in raw
    assert read_android_xml_file(str(target))["Quiz.points.__plurals__"] == content["Quiz.points.__plurals__"]


def test_update_values_changes_only_the_given_values(source_xml):
    before = source_xml.read_text(encoding="utf-8")
    update_android_xml_values(
        str(source_xml),
        {
            ("hello",): 'Hi <xliff:g id="name" example="Bob">%1$s</xliff:g>!',
            ("Quiz.points.__plurals__", "one"): "%1$d pt",
            ("bold",): "It's <b>very</b> 100%% & more",
        },
    )
    after = source_xml.read_text(encoding="utf-8")
    assert_aapt_valid(source_xml)

    expected = (
        before.replace(">Hello <xliff", ">Hi <xliff")
        .replace("%1$d point</item>", "%1$d pt</item>")
        .replace("<b>really</b>", "<b>very</b>")
    )
    assert after == expected  # \' and &amp; kept as written


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_android_profile_masks_xliff_g_as_one_token():
    profile = profile_for_path("res/values/strings.xml")
    assert profile.name == "android"
    masked = mask('Invite <xliff:g id="name" example="Bob">%1$s</xliff:g> to <b>play</b> %2$d', profile)
    assert masked.text == "Invite ⟦0⟧ to ⟦1⟧play⟦2⟧ ⟦3⟧"
    escapes = "Tap \\@ here \\" + "u2026"
    assert [p.raw for p in extract(escapes, profile)] == ["\\@", "\\" + "u2026"]


# ---------------------------------------------------------------------------
# Plurals
# ---------------------------------------------------------------------------


def test_plural_forms_expanded_for_target_language():
    source = {"Quiz.points.__plurals__": {"one": "%1$d point", "other": "%1$d points"}, "ok": "OK"}

    ru = android_plurals.expand_plural_forms(source, "ru")
    assert {k for k in ru if k.startswith("Quiz.points")} == {
        f"Quiz.points.__plurals__.{f}" for f in ("one", "few", "many", "other")
    }
    assert all("%1$d" in ru[f"Quiz.points.__plurals__.{f}"] for f in ("one", "few", "many", "other"))
    assert ru["ok"] == "OK"

    uz = android_plurals.expand_plural_forms(source, "uz-Cyrl")
    assert {k for k in uz if k.startswith("Quiz.points")} == {
        "Quiz.points.__plurals__.one",
        "Quiz.points.__plurals__.other",
    }

    contexts = android_plurals.build_plural_contexts(source, "en", "ru")
    assert "2, 3, 4" in contexts["Quiz.points.__plurals__.few"]
    assert "(%1$d)" in contexts["Quiz.points.__plurals__.few"]
    assert "Android" in contexts["Quiz.points.__plurals__.one"]


def test_multi_count_form_without_count_placeholder_uses_other_text():
    plural = {"one": "One point", "other": "%1$d points"}
    # Russian "one" is 1, 21, 31 ...: it needs the number, so it is translated from 'other'.
    assert android_plurals.plural_source_text(plural, "one", "ru") == "%1$d points"
    # German "one" is only 1: "One point" is fine.
    assert android_plurals.plural_source_text(plural, "one", "de") == "One point"


# ---------------------------------------------------------------------------
# End to end: 'algebras translate' with a transliterating model
# ---------------------------------------------------------------------------

TRANSLATE_SOURCE = """<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">
    <string name="code_disclaimer">We sent a code to %1$s. Resend in %2$d s</string>
    <string name="remaining">%1$d of %2$d questions left</string>
    <string name="invite">Invite <xliff:g id="name" example="Bob">%1$s</xliff:g> to <b>play</b></string>
    <plurals name="Quiz.points">
        <item quantity="one">One point</item>
        <item quantity="other">%1$d points</item>
    </plurals>
    <plurals name="Quiz.timer">
        <item quantity="one">%1$d minute</item>
        <item quantity="other">%1$d minutes</item>
    </plurals>
</resources>
"""


def _project(tmp_path, monkeypatch, languages, locale_dir):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values" / "strings.xml").write_text(TRANSLATE_SOURCE, encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": languages,
                "source_files": {
                    "res/values/strings.xml": {
                        "destination_path": "res/values-%algebras_locale_code%/strings.xml"
                    }
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return tmp_path / "res" / locale_dir / "strings.xml"


def _fake_client(sent):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append((list(texts), list(kwargs.get("contexts") or [])))
        return [transliterate(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    return client


@pytest.mark.parametrize(
    "languages,language,locale_dir,forms",
    [
        (["en", {"uz-Cyrl": "b+uz+Cyrl"}], "uz-Cyrl", "values-b+uz+Cyrl", ["one", "other"]),
        (["en", "ru"], "ru", "values-ru", ["one", "few", "many", "other"]),
    ],
)
def test_translate_never_writes_a_transliterated_placeholder(tmp_path, monkeypatch, languages, language, locale_dir, forms):
    target = _project(tmp_path, monkeypatch, languages, locale_dir)
    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        translate_command.execute(language=language, force="__all__")

    raw = target.read_text(encoding="utf-8")
    assert_aapt_valid(target)
    data = read_android_xml_file(str(target))

    assert "%1$s" in data["code_disclaimer"] and "%2$d" in data["code_disclaimer"]
    assert "%1$d" in data["remaining"] and "%2$d" in data["remaining"]
    assert '<xliff:g id="name" example="Bob">%1$s</xliff:g>' in raw  # element, not &lt;
    assert "<b>" in raw and "&lt;b&gt;" not in raw
    for name in ("Quiz.points.__plurals__", "Quiz.timer.__plurals__"):
        assert list(data[name]) == forms
        for form in forms:
            if (name, form, language) == ("Quiz.points.__plurals__", "one", "uz-Cyrl"):
                # Uzbek "one" is only 1, so "One point" needs no number.
                assert "%" not in data[name][form]
                continue
            # Russian "one" (1, 21, 31 ...) is translated from "%1$d points", so it has the number.
            assert "%1$d" in data[name][form], (name, form, data[name][form])
    for value in [v for v in data.values() if isinstance(v, str)] + [
        t for v in data.values() if isinstance(v, dict) for t in v.values()
    ]:
        assert_java_format_valid(value)
    # The model never saw a raw placeholder, and plural forms had their notes.
    assert not any("%" in t for texts, _ in sent for t in texts)
    assert any(c and "Android <plurals>" in c for _, contexts in sent for c in contexts)


def test_translate_missing_keys_in_place_expands_plurals(tmp_path, monkeypatch):
    target = _project(tmp_path, monkeypatch, ["en", "ru"], "values-ru")
    target.parent.mkdir(parents=True)
    target.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        "    <!-- keep me -->\n"
        '    <string name="code_disclaimer">Мы отправили код на %1$s. Повтор через %2$d с</string>\n'
        '    <plurals name="Quiz.timer">\n'
        '        <item quantity="one">%1$d минута</item>\n'
        '        <item quantity="other">%1$d минуты</item>\n'
        "    </plurals>\n</resources>\n",
        encoding="utf-8",
    )
    sent = []
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        translate_command.execute(language="ru", only_missing=True)

    raw = target.read_text(encoding="utf-8")
    assert_aapt_valid(target)
    data = read_android_xml_file(str(target))
    assert "<!-- keep me -->" in raw
    assert data["code_disclaimer"].startswith("Мы отправили код")  # untouched
    assert '<xliff:g id="name" example="Bob">%1$s</xliff:g>' in raw
    assert list(data["Quiz.points.__plurals__"]) == ["one", "few", "many", "other"]
    assert all("%1$d" in t for t in data["Quiz.points.__plurals__"].values())
    # 'other' is translated in the first pass, the other forms after it.
    first_contexts = " ".join(c or "" for c in sent[0][1])
    later_contexts = " ".join(c or "" for _, contexts in sent[1:] for c in contexts or [])
    assert "quantity 'other'" in first_contexts and "quantity 'few'" not in first_contexts
    assert "quantity 'few'" in later_contexts and "already translated as" in later_contexts


# ---------------------------------------------------------------------------
# 'algebras placeholders': the client's uz-Cyrl case
# ---------------------------------------------------------------------------

CLIENT_SOURCE = """<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">
    <string name="PhoneRegistration.code_disclaimer">We sent a code to %1$s. Resend in %2$d s</string>
    <string name="Quiz.remaining_questions_format">%1$d of %2$d questions left</string>
    <string name="Profile.greeting">Hello, %1$s!</string>
    <string name="Quiz.score_format">Score: %1$d</string>
    <string name="Invite.message">Invite <xliff:g id="name" example="Bob">%1$s</xliff:g> to play</string>
    <string name="Leaderboard.rank">You are #%1$d of %2$s</string>
    <string name="Common.ok">OK</string>
    <string name="Promo.discount" formatted="false">100% free, %s</string>
    <string name="App.name" translatable="false">Quiz</string>
    <plurals name="Quiz.points">
        <item quantity="one">%1$d point</item>
        <item quantity="other">%1$d points</item>
    </plurals>
    <plurals name="Quiz.timer_format">
        <item quantity="one">%1$d minute</item>
        <item quantity="other">%1$d minutes</item>
    </plurals>
</resources>
"""

CLIENT_TARGET = """<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">
    <!-- translated by algebras -->
    <string name="PhoneRegistration.code_disclaimer">Код %1$с рақамига юборилди. %2$д сониядан сўнг қайта юборинг</string>
    <string name="Quiz.remaining_questions_format">%2$d тадан %1$д савол қолди</string>
    <string name="Profile.greeting">Салом, %1$с!</string>
    <string name="Quiz.score_format">Балл: %1$д</string>
    <string name="Invite.message">Ўйнашга <xliff:g id="name" example="Bob">%1$с</xliff:g> ни таклиф қилинг</string>
    <string name="Leaderboard.rank">Сиз %2$s дан #%1$д ўриндасиз</string>
    <string name="Common.ok">ОК</string>
    <string name="Promo.discount" formatted="false">100% бепул, %s</string>
    <plurals name="Quiz.points">
        <item quantity="one">%1$д очко</item>
        <item quantity="other">%1$д очко</item>
    </plurals>
    <plurals name="Quiz.timer_format">
        <item quantity="one">%1$д дақиқа</item>
        <item quantity="other">%1$д дақиқа</item>
    </plurals>
</resources>
"""

CORRUPTED_KEYS = {
    "PhoneRegistration.code_disclaimer",
    "Quiz.remaining_questions_format",
    "Profile.greeting",
    "Quiz.score_format",
    "Invite.message",
    "Leaderboard.rank",
    "Quiz.points.__plurals__.one",
    "Quiz.points.__plurals__.other",
    "Quiz.timer_format.__plurals__.one",
    "Quiz.timer_format.__plurals__.other",
}


@pytest.fixture(params=["source_files", "scanner"])
def client_project(request, tmp_path, monkeypatch):
    (tmp_path / "res" / "values").mkdir(parents=True)
    (tmp_path / "res" / "values-b+uz+Cyrl").mkdir(parents=True)
    (tmp_path / "res" / "values" / "generic_strings.xml").write_text(CLIENT_SOURCE, encoding="utf-8")
    target = tmp_path / "res" / "values-b+uz+Cyrl" / "generic_strings.xml"
    target.write_text(CLIENT_TARGET, encoding="utf-8")
    config = {"languages": ["en", {"uz-Cyrl": "b+uz+Cyrl"}], "api": {"provider": "algebras-ai"}}
    if request.param == "source_files":
        config["source_files"] = {
            "res/values/generic_strings.xml": {
                "destination_path": "res/values-%algebras_locale_code%/generic_strings.xml"
            }
        }
    (tmp_path / ".algebras.config").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return target


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_b_plus_locale_directory_pairs_with_values(client_project):
    from algebras.commands.healthcheck_command import iter_file_pairs
    from algebras.services.file_scanner import FileScanner

    config = Config()
    config.load()
    files = FileScanner(config=config).group_files_by_language()
    pairs = list(iter_file_pairs(config, "en", "uz-Cyrl", files))
    assert [(Path(s).as_posix(), Path(t).as_posix()) for s, t in pairs] == [
        ("res/values/generic_strings.xml", "res/values-b+uz+Cyrl/generic_strings.xml")
    ]


def test_check_reports_eleven_corruptions_in_ten_strings(client_project, capsys):
    code, report = _report(capsys)

    assert code == 1
    assert report["files_checked"] == 1
    assert {i["key"] for i in report["issues"]} == CORRUPTED_KEYS
    # Damaged specifiers are "corrupted"; inside an atomic <xliff:g> block the block is "extra".
    damaged = [p for i in report["issues"] for p in i["problems"] if p["code"] in ("corrupted", "extra")]
    assert len(damaged) == 11
    assert all(i["fixed"] is not None for i in report["issues"])


def test_fix_repairs_only_the_damaged_characters_and_is_idempotent(client_project, capsys):
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert {i["status"] for i in report["issues"]} == {"fixed"}

    expected = CLIENT_TARGET.replace("%1$с", "%1$s").replace("%2$д", "%2$d").replace("%1$д", "%1$d")
    assert_aapt_valid(client_project)
    assert client_project.read_text(encoding="utf-8") == expected
    fixed = read_android_xml_file(str(client_project))
    fixed.pop("Promo.discount")  # formatted="false": never passed to String.format
    for value in fixed.values():
        for text in value.values() if isinstance(value, dict) else [value]:
            assert_java_format_valid(text)

    code, report = _report(capsys)
    assert (code, report["issues"]) == (0, [])

    code, report = _report(capsys, fix=True)
    assert code == 0
    assert client_project.read_text(encoding="utf-8") == expected


def test_dry_run_writes_nothing(client_project, capsys):
    _report(capsys, fix=True, dry_run=True)
    assert client_project.read_text(encoding="utf-8") == CLIENT_TARGET


def test_check_compares_multi_count_forms_with_the_text_they_come_from(tmp_path):
    source = tmp_path / "values" / "strings.xml"
    target = tmp_path / "values-ru" / "strings.xml"
    source.parent.mkdir()
    target.parent.mkdir()
    source.write_text(
        '<resources><plurals name="p"><item quantity="one">One point</item>'
        '<item quantity="other">%1$d points</item></plurals></resources>',
        encoding="utf-8",
    )
    target.write_text(
        '<resources><plurals name="p"><item quantity="one">%1$d очко</item>'
        '<item quantity="few">%1$д очка</item><item quantity="many">%1$d очков</item>'
        '<item quantity="other">%1$d очка</item></plurals></resources>',
        encoding="utf-8",
    )
    findings = android_format.check_file(str(source), str(target), "en", "ru")

    # "one" may (and must) carry %1$d; the damaged "few", which the source lacks, is found.
    assert [(f.key, f.fixed) for f in findings] == [("p.__plurals__.few", "%1$d очка")]
    assert get_fix_writer(str(target)) is android_format.write_fixes
