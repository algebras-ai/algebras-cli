"""
Translated YAML files keep their layout: a new target is the source file with only its values
replaced (Rails root renamed, untranslated keys left out, ru plural forms added in CLDR order); an
existing target gets only changed values replaced and new keys inserted at their source position.
Comments, blank lines, key order, quoting, CRLF line endings and target-only keys stay.
"""

import difflib
import json
import os
import re
from unittest.mock import MagicMock

import pytest
import yaml

from algebras.commands import translate_command
from algebras.utils.yaml_layout import YAMLLayoutError, render_value, render_yaml_update

_TOKEN = re.compile(r"⟦\d+⟧")

SOURCE = (
    "# Storefront strings\n"
    "en:\n"
    "  # Navigation (keep this order)\n"
    "  zeta: Zeta screen\n"
    "  alpha: 'Alpha'\n"
    "\n"
    "  nav:\n"
    '    home: "Home"   # top bar\n'
    "    cart: Cart\n"
    "\n"
    "  inbox:\n"
    "    messages:\n"
    '      one: "One message"\n'
    '      other: "%{count} messages"\n'
    '  greeting: "Hello, %{name}!"\n'
    "  about: |\n"
    "    Line one\n"
    "    Line two\n"
    "  limit: 3\n"
).replace("\n", "\r\n")

# The source with only its values translated, the root renamed and the ru plural forms added.
EXPECTED_RU = (
    "# Storefront strings\n"
    "ru:\n"
    "  # Navigation (keep this order)\n"
    "  zeta: RU Zeta screen\n"
    "  alpha: 'RU Alpha'\n"
    "\n"
    "  nav:\n"
    '    home: "RU Home"   # top bar\n'
    "    cart: RU Cart\n"
    "\n"
    "  inbox:\n"
    "    messages:\n"
    '      one: "RU %{count} messages"\n'
    "      few: RU %{count} messages\n"
    "      many: RU %{count} messages\n"
    '      other: "RU %{count} messages"\n'
    '  greeting: "RU Hello, %{name}!"\n'
    "  about: |\n"
    "    RU Line one\n"
    "    Line two\n"
    "  limit: 3\n"
).replace("\n", "\r\n")


@pytest.fixture
def fake_api(monkeypatch):
    """Prefixes 'RU '; drops the placeholders of texts containing a word in `drop` (rejected)."""
    drop = set()

    def translate(text):
        if any(word in text for word in drop):
            return "RU " + _TOKEN.sub("", text)
        return "RU " + text

    monkeypatch.setattr(
        "algebras.services.api_client.AlgebrasAIClient.translate_batch",
        lambda self, texts, *a, **k: [translate(t) for t in texts],
    )
    monkeypatch.setattr("algebras.services.api_client.AlgebrasAIClient.translate", lambda self, text, *a, **k: translate(text))
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    return drop


def _project(tmp_path, monkeypatch, source_text=SOURCE):
    source = tmp_path / "config" / "locales" / "en.yml"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(source_text.encode("utf-8"))
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {"config/locales/en.yml": {"destination_path": "config/locales/%algebras_locale_code%.yml"}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return source, source.parent / "ru.yml"


def _text(path):
    return path.read_bytes().decode("utf-8")


def _changed_lines(before, after):
    return [line for line in difflib.ndiff(before.splitlines(True), after.splitlines(True)) if line[:1] in "+-"]


def _touch_newer(source, target):
    stamp = os.path.getmtime(target) + 10
    os.utime(source, (stamp, stamp))


def test_new_target_is_the_source_with_only_values_changed(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    assert _text(target).splitlines(True) == EXPECTED_RU.splitlines(True)


def test_left_out_key_is_omitted_from_a_new_target(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    fake_api.add("Hello")  # greeting's %{name} is lost: rejected
    translate_command.execute(language="ru", force="__all__")
    expected = EXPECTED_RU.replace('  greeting: "RU Hello, %{name}!"\r\n', "")
    assert _text(target) == expected
    assert "Hello" not in _text(target)  # no source text written for it


def test_left_out_parent_is_omitted_whole(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch, SOURCE.replace("Cart", "Cart %{n}").replace('"Home"', '"Home %{n}"'))
    fake_api.update({"Home", "Cart"})
    translate_command.execute(language="ru", force="__all__")
    data = yaml.safe_load(_text(target))["ru"]
    assert "nav" not in data
    assert "  nav:" not in _text(target)
    assert data["zeta"] == "RU Zeta screen" and data["limit"] == 3


@pytest.mark.parametrize("mode", ["translate", "only_missing", "update"])
def test_update_touches_only_the_changed_lines(tmp_path, monkeypatch, fake_api, mode):
    source, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    # The team edits the target: a comment and a key the source does not have stay.
    edited = _text(target).replace("  nav:\r\n", "  nav:\r\n    # reviewed\r\n") + "  legacy: Старое\r\n"
    target.write_bytes(edited.encode("utf-8"))

    # The source gets a new nested key between home and cart, and a changed value.
    changed = SOURCE.replace("    cart: Cart\r\n", "    orders: Orders\r\n    cart: Cart\r\n")
    if mode != "only_missing":
        changed = changed.replace("Zeta screen", "Zeta page")
    source.write_bytes(changed.encode("utf-8"))
    _touch_newer(source, target)

    if mode == "translate":
        translate_command.execute(language="ru")
    elif mode == "only_missing":
        translate_command.execute(language="ru", only_missing=True)
    else:
        # What 'algebras update' does for a file whose keys changed (outdated + missing keys).
        translate_command.execute(
            language="ru",
            outdated_keys_files=[(str(target), {"en.zeta"}, str(source))],
            missing_keys_files=[(str(target), {"en.nav.orders"}, str(source))],
        )

    after = _text(target)
    expected_changes = ["+     orders: RU Orders\r\n"]
    if mode != "only_missing":
        expected_changes = ["-   zeta: RU Zeta screen\r\n", "+   zeta: RU Zeta page\r\n"] + expected_changes
    assert _changed_lines(edited, after) == expected_changes
    # Inside nav, after home (its preceding source sibling), before cart.
    assert "    home: \"RU Home\"   # top bar\r\n    orders: RU Orders\r\n    cart: RU Cart\r\n" in after


def test_missing_parent_is_created_at_its_source_position(tmp_path, monkeypatch, fake_api):
    source, target = _project(tmp_path, monkeypatch)
    target.write_bytes("ru:\r\n  zeta: Зета\r\n  greeting: 'Привет, %{name}!'\r\n".encode("utf-8"))
    translate_command.execute(language="ru", only_missing=True)
    lines = _text(target).split("\r\n")
    assert lines[:2] == ["ru:", "  zeta: Зета"]
    assert lines[2:4] == ["  alpha: RU Alpha", "  nav:"]
    assert lines[4:6] == ["    home: RU Home", "    cart: RU Cart"]
    assert lines[6:12] == [
        "  inbox:",
        "    messages:",
        "      one: RU %{count} messages",
        "      few: RU %{count} messages",
        "      many: RU %{count} messages",
        "      other: RU %{count} messages",
    ]
    assert lines[12] == "  greeting: 'Привет, %{name}!'"
    # A new multi-line value is a literal block, as in the source.
    assert lines[13:16] == ["  about: |", "    RU Line one", "    Line two"]
    assert yaml.safe_load(_text(target))["ru"]["about"] == "RU Line one\nLine two\n"


def test_plural_forms_the_target_needs_are_added_in_cldr_order(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    target.write_bytes(
        "ru:\r\n  inbox:\r\n    messages:\r\n      one: '%{count} сообщение'\r\n      other: '%{count} сообщений'\r\n".encode()
    )
    translate_command.execute(language="ru", only_missing=True)
    text = _text(target)
    assert (
        "      one: '%{count} сообщение'\r\n"
        "      few: RU %{count} messages\r\n"
        "      many: RU %{count} messages\r\n"
        "      other: '%{count} сообщений'\r\n"
    ) in text


def test_regenerate_from_scratch_still_dumps(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="ru", force="__all__")
    translate_command.execute(language="ru", force="__all__", regenerate_from_scratch=True)
    text = _text(target)
    assert "#" not in text and "\r\n" not in text  # yaml.dump: no comments, sorted keys
    data = yaml.safe_load(text)["ru"]
    assert list(data) == sorted(data)
    assert data["greeting"] == "RU Hello, %{name}!"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["%{count} items", "{name} joined", "@user said", "yes", "12", "null", "a: b", "# x"])
def test_values_that_need_quotes_are_quoted(value):
    rendered = render_value(value)
    assert rendered[0] in "'\""
    assert yaml.safe_load(f"k: {rendered}") == {"k": value}
    assert render_value("plain text") == "plain text"


def test_existing_target_keeps_untouched_quoting_and_final_newline():
    base = "a: 'x'\nb: \"y\"\nc: z"  # no final newline
    out = render_yaml_update(base, "a: x\nb: y\nc: z\nd: w\n", {"a": "x", "b": "Y2", "c": "z", "d": "%{n} w"})
    assert out == "a: 'x'\nb: \"Y2\"\nc: z\nd: '%{n} w'"


def test_aliases_are_not_edited_as_text():
    with pytest.raises(YAMLLayoutError):
        render_yaml_update("a: &x hi\nb: *x\n", None, {"a": "salut", "b": "hi"})
