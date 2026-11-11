"""
Translated TypeScript modules keep their layout: a new target is the source module with only its
values replaced (export renamed, untranslated keys left out); an existing target gets only changed
literals replaced and new keys inserted at their source position, each value in its quote style.
The incremental (per batch) writer gives the same file as writing everything at once.
"""

import difflib
import json
import os
import re
from unittest.mock import MagicMock

import pytest

from algebras.commands import translate_command
from algebras.utils.ts_handler import read_ts_document, write_ts_translations
from algebras.utils.ts_layout import LayoutError, render_ts_update

_TOKEN = re.compile(r"⟦\d+⟧")

SOURCE = (
    "// App strings: keep this order.\n"
    "export const en = {\n"
    "  // Shown on the home page\n"
    "  greeting: 'Hello, {{name}}!',\n"
    "\n"
    '  zeta: "Zeta screen",\n'
    "  nested: {\n"
    '    files: "%d files uploaded", // printf from the backend\n'
    "    price: `Total: {amount}`,\n"
    "  },\n"
    "  limit: 3,\n"
    "  alpha: 'Alpha'\n"
    "};\n"
).replace("\n", "\r\n")

EXPECTED_FR = (
    "// App strings: keep this order.\n"
    "export const fr = {\n"
    "  // Shown on the home page\n"
    "  greeting: 'FR Hello, {{name}}!',\n"
    "\n"
    '  zeta: "FR Zeta screen",\n'
    "  nested: {\n"
    '    files: "FR %d files uploaded", // printf from the backend\n'
    "    price: `FR Total: {amount}`,\n"
    "  },\n"
    "  limit: 3,\n"
    "  alpha: 'FR Alpha'\n"
    "};\n"
).replace("\n", "\r\n")


@pytest.fixture
def fake_api(monkeypatch):
    """Prefixes 'FR '; drops the placeholders of texts containing a word in `drop` (rejected)."""
    drop = set()

    def translate(text):
        if any(word in text for word in drop):
            return "FR " + _TOKEN.sub("", text)
        return "FR " + text

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
    source = tmp_path / "src" / "i18n" / "en.ts"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(source_text.encode("utf-8"))
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "fr"],
                "source_files": {"src/i18n/en.ts": {"destination_path": "src/i18n/%algebras_locale_code%.ts"}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return source, source.parent / "fr.ts"


def _text(path):
    return path.read_bytes().decode("utf-8")


def _changed_lines(before, after):
    return [line for line in difflib.ndiff(before.splitlines(True), after.splitlines(True)) if line[:1] in "+-"]


def test_new_target_is_the_source_with_only_values_changed(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="fr", force="__all__")
    assert _text(target).splitlines(True) == EXPECTED_FR.splitlines(True)


def test_batches_give_the_same_file(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="fr", force="__all__", batch_size=1, max_parallel_batches=1)
    assert _text(target) == EXPECTED_FR


def test_left_out_key_is_omitted_from_a_new_target(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    fake_api.add("Total")  # price's {amount} is lost: rejected
    translate_command.execute(language="fr", force="__all__")
    expected = EXPECTED_FR.replace("    price: `FR Total: {amount}`,\r\n", "")
    assert _text(target) == expected
    assert "Total" not in _text(target)


@pytest.mark.parametrize("mode", ["translate", "only_missing", "update"])
def test_update_touches_only_the_changed_lines(tmp_path, monkeypatch, fake_api, mode):
    source, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="fr", force="__all__")
    # The team edits the target: a comment and a key the source does not have stay.
    edited = _text(target).replace("  nested: {\r\n", "  nested: {\r\n    // relu\r\n").replace(
        "  limit: 3,\r\n", "  limit: 3,\r\n  legacy: 'Ancien',\r\n"
    )
    target.write_bytes(edited.encode("utf-8"))

    changed = SOURCE.replace("    price:", "    size: 'Size: {size}',\r\n    price:")
    if mode != "only_missing":
        changed = changed.replace("Zeta screen", "Zeta page")
    source.write_bytes(changed.encode("utf-8"))
    stamp = os.path.getmtime(target) + 10
    os.utime(source, (stamp, stamp))

    if mode == "translate":
        translate_command.execute(language="fr")
    elif mode == "only_missing":
        translate_command.execute(language="fr", only_missing=True)
    else:
        translate_command.execute(
            language="fr",
            outdated_keys_files=[(str(target), {"zeta"}, str(source))],
            missing_keys_files=[(str(target), {"nested.size"}, str(source))],
        )

    after = _text(target)
    expected_changes = ["+     size: 'FR Size: {size}',\r\n"]
    if mode != "only_missing":
        expected_changes = ['-   zeta: "FR Zeta screen",\r\n', '+   zeta: "FR Zeta page",\r\n'] + expected_changes
    assert _changed_lines(edited, after) == expected_changes
    assert '// printf from the backend\r\n    size: \'FR Size: {size}\',\r\n    price:' in after


def test_missing_parent_and_keys_go_to_their_source_position(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    target.write_bytes("export const fr = {\n    zeta: 'Zêta',\n    alpha: \"Alpha FR\"\n};\n".encode())
    translate_command.execute(language="fr", only_missing=True)
    assert _text(target) == (
        "export const fr = {\n"
        "    greeting: 'FR Hello, {{name}}!',\n"
        "    zeta: 'Zêta',\n"
        "    nested: {\n"
        '        files: "FR %d files uploaded",\n'
        "        price: `FR Total: {amount}`,\n"
        "    },\n"
        "    alpha: \"Alpha FR\"\n"
        "};\n"
    )
    read_ts_document(str(target))


def test_regenerate_from_scratch_still_rewrites(tmp_path, monkeypatch, fake_api):
    _, target = _project(tmp_path, monkeypatch)
    translate_command.execute(language="fr", force="__all__")
    translate_command.execute(language="fr", force="__all__", regenerate_from_scratch=True)
    text = _text(target)
    assert "//" not in text and "\r\n" not in text  # written from scratch
    assert read_ts_document(str(target)).data["nested"]["price"] == "FR Total: {amount}"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def test_values_are_escaped_for_their_quote_style():
    base = "export const fr = {\n  a: 'x',\n  b: `y ${n}`,\n};\n"
    source = "export const en = {\n  a: 'x',\n  b: `y ${n}`,\n  c: \"z\",\n};\n"
    out = render_ts_update(base, source, {"a": "l'été", "b": "`${n}` ${x}", "c": 'dit "oui"'})
    assert out == "export const fr = {\n  a: 'l\\'été',\n  b: `\\`${n}\\` \\${x}`,\n  c: \"dit \\\"oui\\\"\",\n};\n"


def test_inline_object_and_missing_trailing_comma():
    base = "export const fr = { a: 'A' };"
    source = "export const en = { a: 'A', b: 'B' };"
    assert render_ts_update(base, source, {"b": "Bé"}) == "export const fr = { a: 'A', b: 'Bé' };"
    base = "export const fr = {\n  a: 'A'\n};\n"
    assert render_ts_update(base, source, {"b": "Bé"}) == "export const fr = {\n  a: 'A',\n  b: 'Bé'\n};\n"


def test_structure_mismatch_falls_back_to_a_full_write(tmp_path):
    with pytest.raises(LayoutError):
        render_ts_update("export const fr = { a: 'x' };", "export const en = { a: { b: 'y' } };", {"a.b": "z"})
    target = tmp_path / "fr.ts"
    source = tmp_path / "en.ts"
    source.write_text("export const en = { a: { b: 'y' } };", encoding="utf-8")
    # An unparseable target is written again from scratch.
    write_ts_translations(str(target), {"a.b": "z"}, "fr", str(source), base_text="export const fr = { a: 'x ;")
    assert read_ts_document(str(target)).data == {"a": {"b": "z"}}
