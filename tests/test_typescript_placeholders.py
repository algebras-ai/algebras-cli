"""
TypeScript translation modules (.ts): the literal parser and quote-preserving writers, profile
auto-detection, translation end to end with a model that adds apostrophes and backticks, and
'algebras placeholders' check / --fix / --dry-run (ts_unparseable included).
"""

import json
import random
import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.placeholders import extract, mask, profile_for_path, verify
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import typescript
from algebras.services.placeholders.formats.typescript import check_file
from algebras.utils.ts_handler import (
    TSParseError,
    encode_ts_string,
    parse_ts_module,
    read_ts_document,
    read_ts_translation_file,
    write_ts_translation_file_in_place,
)

SOURCE = """\
// App strings: keep keys sorted.
export const en = {
  greeting: 'Hello, {{name}}!',
  cart: "{count, plural, one {# item} other {# items}}",
  welcome: `Welcome back, ${user.name}! Your plan: ${plan}`,
  saved: 'Saved',
  nested: {
    files: "%d files uploaded", // printf from the backend
    price: "Total: {amount}",
    help: "See https://example.com/help",
    truth: "That's true, not null",
  },
};
"""


@pytest.fixture(autouse=True)
def ts_fix_writer():
    # Other tests may replace writers with recording ones; use the real one here.
    register_fix_writer([".ts"], typescript.write_fixes)
    yield


def _parses_with_node(path):
    """`node --check` on the module (plain JS syntax), when node is available; tsc when it is."""
    tsc = shutil.which("tsc")
    if tsc:
        result = subprocess.run([tsc, "--noEmit", "--allowJs", str(path)], capture_output=True, text=True)
        # Undeclared identifiers in template substitutions are type errors, not syntax errors.
        assert "error TS1" not in result.stdout, result.stdout
    node = shutil.which("node")
    if not node:
        return
    mjs = path.with_suffix(".check.mjs")
    mjs.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        result = subprocess.run([node, "--check", str(mjs)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    finally:
        mjs.unlink()


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def test_reader_keeps_values_the_old_regex_reader_broke(tmp_path):
    path = tmp_path / "en.ts"
    path.write_text(SOURCE, encoding="utf-8")
    data = read_ts_translation_file(str(path))
    assert data["welcome"] == "Welcome back, ${user.name}! Your plan: ${plan}"  # backticks parse
    assert data["nested"]["help"] == "See https://example.com/help"  # not a // comment
    assert data["nested"]["truth"] == "That's true, not null"  # not True / None
    assert data["greeting"] == "Hello, {{name}}!"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("export const en = { a: 'x', } as const;", {"a": "x"}),
        ("export const en: Record<string, string> = {\n  a: \"x\"\n};", {"a": "x"}),
        ("export default { 'a-b': 'x', 1: [true, null, 2.5] }", {"a-b": "x", "1": [True, None, 2.5]}),
        ("export const en = { /* c */ a: 'it\\'s \\u{1F600} \\x41\\n', b: \"q\\\"\" };", {"a": "it's 😀 A\n", "b": 'q"'}),
        ("export const en = { a: `x ${f({n: `y${z}`})} \\${lit} \\` w` };", {"a": "x ${f({n: `y${z}`})} ${lit} ` w"}),
        ("export const en = { a: `line1\r\nline2` };", {"a": "line1\nline2"}),
    ],
)
def test_reader_cases(text, expected):
    assert parse_ts_module(text).data == expected


def test_template_substitutions_and_quote_styles_are_recorded():
    doc = parse_ts_module(SOURCE)
    assert doc.export_name == "en"
    assert doc.literals[("greeting",)].quote == "'"
    assert doc.literals[("cart",)].quote == '"'
    welcome = doc.literals[("welcome",)]
    assert (welcome.quote, welcome.substitutions) == ("`", ("${user.name}", "${plan}"))
    assert SOURCE[welcome.start : welcome.end] == "`Welcome back, ${user.name}! Your plan: ${plan}`"
    # An escaped \${ is literal text, not a substitution.
    assert parse_ts_module("export const en = { a: `\\${x} ${y}` };").literals[("a",)].substitutions == ("${y}",)


@pytest.mark.parametrize("text", ["export const en = { a: 'Don't' };", "export const en = { a: `say `hi`` };"])
def test_unescaped_quotes_fail_strictly_and_are_recovered_leniently(text):
    with pytest.raises(TSParseError):
        parse_ts_module(text)
    doc = parse_ts_module(text, lenient=True)
    assert doc.recovered.keys() == {("a",)}
    assert doc.data["a"] in ("Don't", "say `hi`")


# ---------------------------------------------------------------------------
# Writer escaping
# ---------------------------------------------------------------------------


def test_encode_escapes_for_each_quote_style():
    assert encode_ts_string("l'été \"x\"", "'") == "'l\\'été \"x\"'"
    assert encode_ts_string("l'été \"x\"", '"') == '"l\'été \\"x\\""'
    # A translated backtick and "${" cannot end the literal or start a substitution.
    assert encode_ts_string("`ok` ${user.name} ${x} ${", "`", ("${user.name}",)) == "`\\`ok\\` ${user.name} \\${x} \\${`"


def test_encode_round_trips_through_the_reader():
    rng = random.Random(1234)
    alphabet = "ab '\"`$\\{}\n\r\t é😀⟦⟧"
    for _ in range(500):
        value = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 16)))
        for quote in ("'", '"', "`"):
            literal = encode_ts_string(value, quote, ())
            doc = parse_ts_module(f"export const en = {{ k: {literal} }};")
            assert doc.data["k"] == value, (quote, value, literal)
            if quote == "`":
                assert doc.literals[("k",)].substitutions == ()


def test_in_place_writer_keeps_layout_and_quote_styles(tmp_path):
    source = tmp_path / "en.ts"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "fr.ts"
    target.write_text(SOURCE.replace("const en", "const fr"), encoding="utf-8")
    write_ts_translation_file_in_place(
        str(target),
        {"greeting": "Bonjour, {{name}} ! C'est l'été", "welcome": "Re`bonjour`, ${user.name} ! ${plan} ${x}"},
        source_file=str(source),
    )
    text = target.read_text(encoding="utf-8")
    assert "greeting: 'Bonjour, {{name}} ! C\\'est l\\'été'," in text
    assert "welcome: `Re\\`bonjour\\`, ${user.name} ! ${plan} \\${x}`," in text
    assert text.startswith("// App strings") and "// printf from the backend" in text
    assert text.replace("Bonjour, {{name}} ! C\\'est l\\'été", "Hello, {{name}}!").replace(
        "Re\\`bonjour\\`, ${user.name} ! ${plan} \\${x}", "Welcome back, ${user.name}! Your plan: ${plan}"
    ) == SOURCE.replace("const en", "const fr")
    _parses_with_node(target)


def test_new_keys_take_the_source_quote_style(tmp_path):
    source = tmp_path / "en.ts"
    source.write_text(SOURCE, encoding="utf-8")
    target = tmp_path / "fr.ts"
    write_ts_translation_file_in_place(str(target), {"greeting": "C'est {{name}}"}, "fr", source_file=str(source))
    write_ts_translation_file_in_place(
        str(target), {"welcome": "Salut ${user.name}, ${plan}", "nested.truth": "C'est vrai"}, "fr", source_file=str(source)
    )
    doc = read_ts_document(str(target))
    assert doc.data == {"greeting": "C'est {{name}}", "welcome": "Salut ${user.name}, ${plan}", "nested": {"truth": "C'est vrai"}}
    assert doc.literals[("greeting",)].quote == "'"
    assert doc.literals[("welcome",)].substitutions == ("${user.name}", "${plan}")
    assert doc.literals[("nested", "truth")].quote == '"'
    _parses_with_node(target)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_profile_is_detected_from_the_module(tmp_path):
    path = tmp_path / "en.ts"
    path.write_text(SOURCE, encoding="utf-8")
    profile = profile_for_path(str(path))
    assert set(profile.syntax_names) == {"i18next", "js_template", "icu_simple", "printf"}
    masked = mask("Welcome back, ${user.name}! {{name}} {amount} %d ${fmt({n: count})}", profile)
    assert masked.text == "Welcome back, ⟦0⟧! ⟦1⟧ ⟦2⟧ ⟦3⟧ ⟦4⟧"
    assert masked.placeholders[4].raw == "${fmt({n: count})}"
    other = tmp_path / "plain.ts"
    other.write_text("export const en = { a: 'Hi {{name}}' };", encoding="utf-8")
    assert profile_for_path(str(other)).syntax_names == ("i18next",)


# ---------------------------------------------------------------------------
# Translation end to end
# ---------------------------------------------------------------------------

NAMES = {"user": "utilisateur", "name": "nom", "plan": "forfait", "count": "nombre", "amount": "montant"}


def fake_translate(text):
    """A French model: translates every word it knows (names too), adds apostrophes and backticks."""
    out = text.replace("Hello", "Bonjour").replace("Welcome back", "Re`bonjour`").replace("Saved", "C'est enregistré")
    for en, fr in NAMES.items():
        out = out.replace(en, fr)
    if "⟦" in out:
        out += " — c'est `top` ${ok"
    return out


def _fake_client(sent):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.extend(texts)
        return [fake_translate(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    client.translate.side_effect = lambda text, *a, **k: fake_translate(text)
    return client


@pytest.fixture
def project(tmp_path, monkeypatch):
    source = tmp_path / "src" / "i18n" / "en.ts"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE, encoding="utf-8")
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
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    return source, source.parent / "fr.ts"


def _translate(sent, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        translate_command.execute(language="fr", **kwargs)


@pytest.mark.parametrize("mode", ["full", "missing"])
def test_translated_module_parses_and_keeps_placeholders(project, mode):
    source, target = project
    if mode == "missing":
        target.write_text("export const fr = {\n  saved: 'Enregistré',\n};\n", encoding="utf-8")
    sent = []
    _translate(sent, force="__all__" if mode == "full" else None, only_missing=mode == "missing")

    doc = read_ts_document(str(target))  # parses with the handler's own reader
    _parses_with_node(target)
    src = read_ts_document(str(source))
    profile = profile_for_path(str(source))
    for path, literal in src.literals.items():
        value = doc.data
        for part in path:
            value = value[part]
        source_text = src.data
        for part in path:
            source_text = source_text[part]
        assert verify(source_text, value, profile) == [], (path, value)
        assert sorted(p.raw for p in extract(value, profile)) == sorted(p.raw for p in extract(source_text, profile))

    welcome = doc.literals[("welcome",)]
    assert welcome.quote == "`"
    assert welcome.substitutions == ("${user.name}", "${plan}")  # evaluated, byte-identical
    # The model's "${" is literal text in the template literal, not a new substitution.
    # Raw text: the parser's offsets count every character, including \r on Windows.
    with open(target, encoding="utf-8", newline="") as f:
        text = f.read()
    assert text[welcome.start : welcome.end].endswith("c'est \\`top\\` \\${ok`")
    assert doc.data["welcome"].endswith("c'est `top` ${ok")
    assert doc.data["welcome"].startswith("Re`bonjour`, ${user.name}!")
    assert doc.literals[("greeting",)].quote == "'" and "c\\'est" in target.read_text(encoding="utf-8")
    if mode == "missing":
        assert doc.data["saved"] == "Enregistré"
    assert check_file(str(source), str(target), "en", "fr") == []
    # The model never saw a placeholder, so it could not translate a name inside one.
    for raw in ("{{", "${user", "${plan", "%d", "{amount}"):
        assert not any(raw in t for t in sent), raw


# ---------------------------------------------------------------------------
# 'algebras placeholders'
# ---------------------------------------------------------------------------

BROKEN_FR = """\
// Traductions
export const fr = {
  greeting: 'Bonjour, {{nom}}, c'est vous !',
  cart: "{count, plural, one {# article} other {# articles}}",
  welcome: `Re-bonjour, ${utilisateur.name} ! Votre forfait : ${plan}`,
  saved: 'C'est enregistré',
  nested: {
    files: "%д fichiers envoyés", // printf
    price: "Total : {amount}",
    help: "Voir https://example.com/help",
    truth: "C'est vrai, pas nul",
  },
};
"""


@pytest.fixture
def broken(project):
    source, target = project
    target.write_text(BROKEN_FR, encoding="utf-8")
    return source, target


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_exact_codes(broken, capsys):
    code, report = _report(capsys)
    assert code == 1
    assert report["skipped"] == []
    problems = {i["key"]: sorted(p["code"] for p in i["problems"]) for i in report["issues"]}
    assert problems == {
        "greeting": ["extra", "missing", "ts_unparseable"],
        "welcome": ["extra", "missing"],
        "saved": ["ts_unparseable"],
        "nested.files": ["corrupted", "missing"],
    }
    fixed = {i["key"]: i["fixed"] for i in report["issues"]}
    assert fixed == {
        "greeting": "Bonjour, {{name}}, c'est vous !",
        "welcome": "Re-bonjour, ${user.name} ! Votre forfait : ${plan}",
        "saved": "C'est enregistré",
        "nested.files": "%d fichiers envoyés",
    }


def test_fix_repairs_in_place_and_is_idempotent(broken, capsys):
    source, target = broken
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert {i["status"] for i in report["issues"]} == {"fixed"}
    text = target.read_text(encoding="utf-8")
    assert text == (
        BROKEN_FR.replace("'Bonjour, {{nom}}, c'est vous !'", "'Bonjour, {{name}}, c\\'est vous !'")
        .replace("${utilisateur.name}", "${user.name}")
        .replace("'C'est enregistré'", "'C\\'est enregistré'")
        .replace("%д", "%d")
    )
    read_ts_document(str(target))
    _parses_with_node(target)

    code, report = _report(capsys)
    assert (code, report["issues"]) == (0, [])
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert target.read_text(encoding="utf-8") == text


def test_dry_run_writes_nothing(broken, capsys):
    _, target = broken
    code, _ = _report(capsys, fix=True, dry_run=True)
    assert code == 1
    assert target.read_text(encoding="utf-8") == BROKEN_FR


def test_unreadable_module_is_reported_not_skipped(project, capsys):
    _, target = project
    target.write_text("export const fr = {\n  greeting: 'Bonjour\n};\n", encoding="utf-8")
    code, report = _report(capsys)
    assert code == 1
    assert [(i["key"], [p["code"] for p in i["problems"]], i["fixed"]) for i in report["issues"]] == [
        ("(file)", ["ts_unparseable"], None)
    ]
    code, report = _report(capsys, fix=True)
    assert code == 2
