"""
translate / update keep the layout of iOS .strings and Android strings.xml files: a new target is
the source with only the values changed, an existing target changes only the lines whose value
changed plus the lines of new keys (at their source position). --regenerate-from-scratch still
rewrites the file sorted by key.

The model is a fake that upper-cases the text it gets (placeholders are masked, so they survive).
"""

import difflib
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import translate_command, update_command
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.ios_strings_handler import read_ios_strings_file


def _fake_model(monkeypatch, reject=()):
    """Upper-case every text; a text containing one of `reject` loses its placeholders."""
    sent = []

    def translate_batch(self, texts, *args, **kwargs):
        sent.extend(texts)
        out = []
        for t in texts:
            if any(r in t for r in reject):
                out.append("BROKEN")  # no placeholder token left: the key is rejected
            else:
                out.append(t.upper())
        return out

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return sent


def _changed_lines(before: str, after: str):
    """(removed, added) lines between two texts."""
    removed, added = [], []
    for line in difflib.ndiff(before.splitlines(), after.splitlines()):
        if line.startswith("- "):
            removed.append(line[2:])
        elif line.startswith("+ "):
            added.append(line[2:])
    return removed, added


def _make_source_newer(source, target):
    t = os.path.getmtime(target)
    os.utime(source, (t + 10, t + 10))


def _read(path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


@pytest.fixture(autouse=True)
def default_normalization():
    # _escape_ios_string reads the project config; keep tests independent of it.
    cfg = MagicMock()
    cfg.exists.return_value = False
    with patch("algebras.utils.ios_strings_handler.Config", return_value=cfg):
        yield


# ---------------------------------------------------------------------------
# iOS .strings
# ---------------------------------------------------------------------------

IOS_SOURCE = (
    "/* Login screen */\r\n"
    "\r\n"
    "/* Title of the login screen */\r\n"
    '"login.title" = "Sign in";\r\n'
    '"login.button"="Continue";\r\n'
    "\r\n"
    "// MARK: - Profile\r\n"
    '"profile.greeting" = "Hello, %@!"; // shown on top\r\n'
    '"profile.quote" = "Tap \\"Edit\\" to change";\r\n'
    "\r\n"
    "/* Shown when the upload fails */\r\n"
    '"upload.error" = "Upload of %@ failed";\r\n'
    '"about" = "About";\r\n'
)

IOS_EXPECTED = (
    "/* Login screen */\r\n"
    "\r\n"
    "/* Title of the login screen */\r\n"
    '"login.title" = "SIGN IN";\r\n'
    '"login.button"="CONTINUE";\r\n'
    "\r\n"
    "// MARK: - Profile\r\n"
    '"profile.greeting" = "HELLO, %@!"; // shown on top\r\n'
    '"profile.quote" = "TAP \\"EDIT\\" TO CHANGE";\r\n'
    "\r\n"
    "/* Shown when the upload fails */\r\n"
    '"upload.error" = "UPLOAD OF %@ FAILED";\r\n'
    '"about" = "ABOUT";\r\n'
)


@pytest.fixture
def ios_project(tmp_path, monkeypatch):
    source = tmp_path / "App" / "en.lproj" / "Localizable.strings"
    _write(source, IOS_SOURCE)
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "fr"],
                "source_files": {
                    "App/en.lproj/Localizable.strings": {
                        "destination_path": "App/%algebras_locale_code%.lproj/Localizable.strings"
                    }
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return source, tmp_path / "App" / "fr.lproj" / "Localizable.strings"


def test_strings_new_file_is_the_source_with_values_changed(ios_project, monkeypatch):
    source, target = ios_project
    _fake_model(monkeypatch)
    translate_command.execute(language="fr", force="__all__")

    out = _read(target)
    assert out.split("\r\n") == IOS_EXPECTED.split("\r\n")
    assert out == IOS_EXPECTED  # CRLF and trailing newline included


def test_strings_untranslated_key_is_left_out(ios_project, monkeypatch):
    source, target = ios_project
    _fake_model(monkeypatch, reject=("Upload of",))
    translate_command.execute(language="fr", force="__all__")

    out = _read(target)
    assert "upload.error" not in out and "Upload of" not in out
    assert "Shown when the upload fails" not in out  # its comment goes with it
    expected = IOS_EXPECTED.replace(
        '\r\n\r\n/* Shown when the upload fails */\r\n"upload.error" = "UPLOAD OF %@ FAILED";', ""
    )
    assert out.split("\r\n") == expected.split("\r\n")
    assert "upload.error" not in read_ios_strings_file(str(target))


def _change_ios_source(source):
    text = _read(source)
    text = text.replace('"Continue"', '"Next"')
    text = text.replace(
        '"profile.quote" = "Tap \\"Edit\\" to change";\r\n',
        '"profile.quote" = "Tap \\"Edit\\" to change";\r\n/* Logout button */\r\n"profile.logout" = "Log out";\r\n',
    )
    _write(source, text)


@pytest.mark.parametrize("how", ["translate", "update", "only_missing"])
def test_strings_second_run_touches_only_changed_lines(ios_project, monkeypatch, how):
    source, target = ios_project
    _fake_model(monkeypatch)
    translate_command.execute(language="fr", force="__all__")
    # Edits made to the target by hand (here a comment) must survive.
    first = _read(target).replace("/* Login screen */", "/* Écran */")
    _write(target, first)

    _change_ios_source(source)
    _make_source_newer(source, target)
    if how == "translate":
        translate_command.execute(language="fr")
    elif how == "update":
        update_command.execute(language="fr", only_missing=False, skip_git_validation=True)
    else:
        translate_command.execute(language="fr", only_missing=True)

    second = _read(target)
    removed, added = _changed_lines(first, second)
    if how == "only_missing":
        assert removed == []
        assert added == ["/* Logout button */", '"profile.logout" = "LOG OUT";']
    else:
        assert removed == ['"login.button"="CONTINUE";']
        assert added == ['"login.button"="NEXT";', "/* Logout button */", '"profile.logout" = "LOG OUT";']
    lines = second.split("\r\n")
    # The new key sits at its source position, right after the key before it in the source.
    i = lines.index('"profile.quote" = "TAP \\"EDIT\\" TO CHANGE";')
    assert lines[i + 1 : i + 3] == ["/* Logout button */", '"profile.logout" = "LOG OUT";']
    assert "/* Écran */" in second
    assert second.count("\r\n") == len(lines) - 1 and "\n" not in second.replace("\r\n", "")


def test_strings_force_keys_update_in_place(ios_project, monkeypatch):
    source, target = ios_project
    _fake_model(monkeypatch)
    translate_command.execute(language="fr", force="__all__")
    first = _read(target).replace('"ABOUT"', '"À propos"').replace('"SIGN IN"', '"Connexion"')
    _write(target, first)

    translate_command.execute(language="fr", force="about")
    removed, added = _changed_lines(first, _read(target))
    assert (removed, added) == (['"about" = "À propos";'], ['"about" = "ABOUT";'])


def test_strings_kept_keys_no_longer_in_source(ios_project, monkeypatch):
    source, target = ios_project
    _write(target, '/* old */\n"obsolete" = "Ancien";\n"about" = "À propos";\n')
    _fake_model(monkeypatch)
    translate_command.execute(language="fr", force="__all__")
    out = _read(target)
    lines = out.split("\n")
    assert lines[:2] == ["/* old */", '"obsolete" = "Ancien";']
    # Keys before "about" in the source go before it, the rest after it; LF line endings kept.
    assert "\r" not in out
    keys = list(read_ios_strings_file(str(target)))
    assert keys == [
        "obsolete", "login.title", "login.button", "profile.greeting", "profile.quote", "upload.error", "about",
    ]


def test_strings_regenerate_from_scratch_still_sorts(ios_project, monkeypatch):
    source, target = ios_project
    _fake_model(monkeypatch)
    translate_command.execute(language="fr", force="__all__", regenerate_from_scratch=True)
    out = _read(target)
    assert "/*" not in out and "//" not in out
    keys = list(read_ios_strings_file(str(target)))
    assert keys == sorted(keys)

    # And on an existing file too.
    _write(target, IOS_EXPECTED)
    translate_command.execute(language="fr", force="__all__", regenerate_from_scratch=True)
    keys = list(read_ios_strings_file(str(target)))
    assert keys == sorted(keys) and "/*" not in _read(target)


# ---------------------------------------------------------------------------
# Android strings.xml
# ---------------------------------------------------------------------------

XML_SOURCE = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<resources xmlns:tools="http://schemas.android.com/tools"\r\n'
    '    xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2" tools:locale="en">\r\n'
    "    <!-- Login -->\r\n"
    '    <string name="login_title">Sign in</string>\r\n'
    '    <string name="app_id" translatable="false">com.example</string>\r\n'
    '    <string name="login_hint" tools:ignore="MissingTranslation">It\\\'s your e-mail</string>\r\n'
    "\r\n"
    "    <!-- Counters -->\r\n"
    '    <plurals name="points" formatted="false">\r\n'
    '        <item quantity="one">%d point</item>\r\n'
    '        <item quantity="other">%d points</item>\r\n'
    "    </plurals>\r\n"
    '    <string name="greeting">Hi <xliff:g id="name">%1$s</xliff:g>!</string>\r\n'
    '    <color name="brand">#ff0000</color>\r\n'
    '    <string name="about">About</string>\r\n'
    "</resources>\r\n"
)

XML_EXPECTED_RU = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<resources xmlns:tools="http://schemas.android.com/tools"\r\n'
    '    xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\r\n'
    "    <!-- Login -->\r\n"
    '    <string name="login_title">SIGN IN</string>\r\n'
    '    <string name="login_hint" tools:ignore="MissingTranslation">IT\\\'S YOUR E-MAIL</string>\r\n'
    "\r\n"
    "    <!-- Counters -->\r\n"
    '    <plurals name="points" formatted="false">\r\n'
    '        <item quantity="one">%d POINT</item>\r\n'
    '        <item quantity="few">%d POINTS</item>\r\n'
    '        <item quantity="many">%d POINTS</item>\r\n'
    '        <item quantity="other">%d POINTS</item>\r\n'
    "    </plurals>\r\n"
    '    <string name="greeting">HI <xliff:g id="name">%1$s</xliff:g>!</string>\r\n'
    '    <string name="about">ABOUT</string>\r\n'
    "</resources>\r\n"
)


@pytest.fixture
def android_project(tmp_path, monkeypatch):
    source = tmp_path / "res" / "values" / "strings.xml"
    _write(source, XML_SOURCE)
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {
                    "res/values/strings.xml": {"destination_path": "res/values-%algebras_locale_code%/strings.xml"}
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return source, tmp_path / "res" / "values-ru" / "strings.xml"


def test_xml_new_file_is_the_source_with_values_changed(android_project, monkeypatch):
    source, target = android_project
    _fake_model(monkeypatch)
    translate_command.execute(language="ru", force="__all__")

    out = _read(target)
    assert out.split("\r\n") == XML_EXPECTED_RU.split("\r\n")
    assert out == XML_EXPECTED_RU
    data = read_android_xml_file(str(target))
    # Plural forms Russian needs are added in CLDR order.
    assert list(data["points.__plurals__"]) == ["one", "few", "many", "other"]


def test_xml_new_file_keeps_source_plural_item_order(android_project, monkeypatch):
    source, target = android_project
    _write(source, _read(source).replace(
        '        <item quantity="one">%d point</item>\r\n        <item quantity="other">%d points</item>\r\n',
        '        <item quantity="other">%d points</item>\r\n        <item quantity="one">%d point</item>\r\n',
    ))
    _fake_model(monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    data = read_android_xml_file(str(target))
    # Source order kept; each new form goes before the first form that comes later in CLDR order.
    assert list(data["points.__plurals__"]) == ["few", "many", "other", "one"]


def test_xml_untranslated_key_is_left_out(android_project, monkeypatch):
    source, target = android_project
    _fake_model(monkeypatch, reject=("Hi ",))
    translate_command.execute(language="ru", force="__all__")
    out = _read(target)
    assert 'name="greeting"' not in out and "Hi " not in out
    expected = XML_EXPECTED_RU.replace(
        '    <string name="greeting">HI <xliff:g id="name">%1$s</xliff:g>!</string>\r\n', ""
    )
    assert out.split("\r\n") == expected.split("\r\n")


def _change_xml_source(source):
    text = _read(source)
    text = text.replace(">About<", ">About us<")
    text = text.replace(
        '    <string name="login_title">Sign in</string>\r\n',
        '    <string name="login_title">Sign in</string>\r\n'
        "    <!-- Shown under the title -->\r\n"
        '    <string name="login_subtitle" formatted="false">Welcome back, 100%</string>\r\n',
    )
    _write(source, text)


@pytest.mark.parametrize("how", ["translate", "update", "only_missing"])
def test_xml_second_run_touches_only_changed_lines(android_project, monkeypatch, how):
    source, target = android_project
    _fake_model(monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    first = _read(target).replace("<!-- Login -->", "<!-- Вход -->")
    _write(target, first)

    _change_xml_source(source)
    _make_source_newer(source, target)
    if how == "translate":
        translate_command.execute(language="ru")
    elif how == "update":
        # What 'algebras update --full' runs for a target older than its source. (update does not
        # pair values-ru/ with values/ by itself yet, so the pair is given here.)
        translate_command.execute(
            language="ru", force=True, only_missing=False, outdated_files=[(str(target), str(source))]
        )
    else:
        translate_command.execute(language="ru", only_missing=True)

    second = _read(target)
    removed, added = _changed_lines(first, second)
    new_lines = [
        "    <!-- Shown under the title -->",
        '    <string name="login_subtitle" formatted="false">WELCOME BACK, 100%</string>',
    ]
    if how == "only_missing":
        assert removed == [] and added == new_lines
    else:
        assert removed == ['    <string name="about">ABOUT</string>']
        assert added == new_lines + ['    <string name="about">ABOUT US</string>']
    lines = second.split("\r\n")
    i = lines.index('    <string name="login_title">SIGN IN</string>')
    assert lines[i + 1 : i + 3] == new_lines
    assert "<!-- Вход -->" in second
    assert "\n" not in second.replace("\r\n", "")


def test_xml_new_key_without_preceding_key_goes_before_the_following_one(android_project, monkeypatch):
    source, target = android_project
    _write(
        target,
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        "    <!-- mine -->\n"
        '    <string name="about">О нас</string>\n'
        '    <string name="old">Старое</string>\n'
        "</resources>",  # no trailing newline
    )
    _fake_model(monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    out = _read(target)
    assert not out.endswith("\n") and "\r" not in out
    names = [line.split('"')[1] for line in out.split("\n") if "<string name=" in line or "<plurals name=" in line]
    # Everything before "about" in the source goes before it; "old" (gone from the source) stays.
    assert names == ["login_title", "login_hint", "points", "greeting", "about", "old"]
    assert '<string name="about">ABOUT</string>' in out  # changed value replaced
    assert "<!-- mine -->" in out and "<!-- Login -->" in out
    # tools:ignore is copied, so the prefix gets declared on <resources>.
    assert 'xmlns:tools="http://schemas.android.com/tools"' in out
    assert list(read_android_xml_file(str(target))["points.__plurals__"]) == ["one", "few", "many", "other"]


def test_xml_existing_plurals_get_missing_forms_in_cldr_order(android_project, monkeypatch):
    source, target = android_project
    existing = XML_EXPECTED_RU.replace(
        '        <item quantity="few">%d POINTS</item>\r\n        <item quantity="many">%d POINTS</item>\r\n', ""
    )
    _write(target, existing)
    _make_source_newer(source, target)
    _fake_model(monkeypatch)
    translate_command.execute(language="ru")
    out = _read(target)
    removed, added = _changed_lines(existing, out)
    assert removed == []
    assert added == ['        <item quantity="few">%d POINTS</item>', '        <item quantity="many">%d POINTS</item>']
    assert out == XML_EXPECTED_RU


def test_xml_regenerate_from_scratch_still_sorts(android_project, monkeypatch):
    source, target = android_project
    _fake_model(monkeypatch)
    translate_command.execute(language="ru", force="__all__", regenerate_from_scratch=True)
    out = _read(target)
    assert "<!--" not in out
    names = [line.split('"')[1] for line in out.splitlines() if "<string name=" in line or "<plurals name=" in line]
    assert names == sorted(names)

    _write(target, XML_EXPECTED_RU)
    translate_command.execute(language="ru", force="__all__", regenerate_from_scratch=True)
    out = _read(target)
    names = [line.split('"')[1] for line in out.splitlines() if "<string name=" in line or "<plurals name=" in line]
    assert names == sorted(names) and "<!--" not in out


def test_xml_escaping_rules_still_apply_to_new_and_changed_values(android_project, monkeypatch):
    source, target = android_project
    _write(target, XML_EXPECTED_RU)

    def translate_batch(self, texts, *args, **kwargs):
        return ["L'" + t + ' "Q" @x' for t in texts]

    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate_batch", translate_batch)
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    translate_command.execute(language="ru", force="about")
    out = _read(target)
    assert '<string name="about">L\\\'About \\"Q\\" @x</string>' in out
    assert read_android_xml_file(str(target))["about"] == 'L\'About "Q" @x'
