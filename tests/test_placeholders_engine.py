"""
Placeholder engine: extract, mask/unmask, verify, context and deterministic repair.
"""

import pytest

from algebras.services.placeholders import (
    GENERIC_PROFILE,
    PlaceholderError,
    PlaceholderProfile,
    combine_context,
    count_drop_allowed,
    extract,
    mask,
    placeholder_context,
    profile_for_path,
    register_profile,
    repair,
    rewrite_context,
    unmask,
    verify,
)
from algebras.services.placeholders.plurals import drop_allowed_for_key


def raws(text, profile=GENERIC_PROFILE):
    return [p.raw for p in extract(text, profile)]


def codes(problems):
    return sorted(p.code for p in problems)


# --- extract ---------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("Sent to %1$s, retry in %2$d s", ["%1$s", "%2$d"]),
        ("%s and %d and %.2f and %,d and %05d", ["%s", "%d", "%.2f", "%,d", "%05d"]),
        ("Hi %@, you have %ld items (%1$@)", ["%@", "%ld", "%1$@"]),
        ("Year %1$tY", ["%1$tY"]),
        ("100%% done%n", ["%%", "%n"]),
        ("%#@items@ left", ["%#@items@"]),
        ("Hi %(name)s, %(count)d", ["%(name)s", "%(count)d"]),
        ("Hi %{name}, %<amount>.2f", ["%{name}", "%<amount>.2f"]),
        ("Hi {{name}}, {{- html}} $t(common.ok)", ["{{name}}", "{{- html}}", "$t(common.ok)"]),
        ("Hi {name}, {0}, {1,number}", ["{name}", "{0}", "{1,number}"]),
        ("Total ${amount}", ["${amount}"]),
        ('Hello <xliff:g id="n">%1$s</xliff:g>!', ['<xliff:g id="n">', "%1$s", "</xliff:g>"]),
        ("Press <b>OK</b><br/>", ["<b>", "</b>", "<br/>"]),
    ],
)
def test_extract_syntaxes(text, expected):
    assert raws(text) == expected


@pytest.mark.parametrize("text", ["50% off", "100% sure", "Save 20 % now", "a < b > c", "Plain text"])
def test_extract_ignores_plain_percent_and_brackets(text):
    assert raws(text) == []


def test_extract_prefers_longest_match():
    # %1$s must not also count as Qt "%1" or "$s"; {{name}} not as {name}
    assert raws("%1$s {{name}}") == ["%1$s", "{{name}}"]


def test_profile_limits_syntaxes():
    only_printf = PlaceholderProfile(name="t", syntax_names=("printf",))
    assert raws("%s {name} <b>", only_printf) == ["%s"]


def test_profile_for_path_registry_and_config_override(tmp_path):
    register_profile([".testfmt"], PlaceholderProfile(name="testfmt", syntax_names=("printf",)))
    assert profile_for_path("a/b.testfmt").name == "testfmt"
    assert profile_for_path("a/b.unknown") is GENERIC_PROFILE
    assert profile_for_path(None) is GENERIC_PROFILE

    class Cfg:
        def get_source_files(self):
            return {"a/b.json": {"placeholders": ["i18next"]}}

    assert profile_for_path("a/b.json", Cfg()).syntax_names == ("i18next",)

    class BadCfg:
        def get_source_files(self):
            return {"a/b.json": {"placeholders": ["nope"]}}

    with pytest.raises(ValueError):
        profile_for_path("a/b.json", BadCfg())


# --- mask / unmask -----------------------------------------------------------

def test_mask_replaces_placeholders_with_tokens():
    m = mask("Sent to %1$s, retry in %2$d s")
    assert m.text == "Sent to ⟦0⟧, retry in ⟦1⟧ s"
    assert [p.raw for p in m.placeholders] == ["%1$s", "%2$d"]


def test_mask_without_placeholders_is_identity():
    m = mask("Hello world")
    assert m.text == "Hello world" and not m.has_tokens


def test_unmask_restores_original_bytes_and_allows_reordering_tokens():
    m = mask("%1$d of %2$d questions left")
    assert unmask("⟦1⟧ тадан ⟦0⟧ савол қолди", m) == "%2$d тадан %1$d савол қолди"


def test_unmask_accepts_unicode_digits_and_bracket_variants():
    m = mask("Hi %s and %d")
    assert unmask("Салом ⟦٠⟧ ва [[1]]", m) == "Салом %s ва %d"
    assert unmask("Салом ⟦ 0 ⟧ ва 〚1〛", m) == "Салом %s ва %d"


@pytest.mark.parametrize(
    "translated, code",
    [
        ("Салом ⟦0⟧", "missing"),
        ("Салом ⟦0⟧ ⟦0⟧ ⟦1⟧", "count_mismatch"),
        ("Салом ⟦0⟧ ⟦1⟧ ⟦7⟧", "extra"),
        ("Салом %с ва %д", "missing"),
    ],
)
def test_unmask_rejects_lost_duplicated_or_unknown_tokens(translated, code):
    with pytest.raises(PlaceholderError) as err:
        unmask(translated, mask("Hi %s and %d"))
    assert code in codes(err.value.problems)


def test_unmask_rejects_swapped_non_positional_printf():
    with pytest.raises(PlaceholderError) as err:
        unmask("⟦1⟧ ва ⟦0⟧", mask("%s and %d"))
    assert "reordered" in codes(err.value.problems)


def test_unmask_rejects_placeholder_written_by_the_model():
    with pytest.raises(PlaceholderError) as err:
        unmask("Привет %s", mask("Hello"))
    assert codes(err.value.problems) == ["extra"]


def test_unmask_drop_allowed_for_single_count_plural():
    m = mask("%d item")
    assert unmask("Ein Element", m, drop_allowed=frozenset({"%d"})) == "Ein Element"
    with pytest.raises(PlaceholderError):
        unmask("Ein Element", m)


def test_unmask_rejects_unbalanced_tags():
    m = mask("Press <b>OK</b> now")
    with pytest.raises(PlaceholderError) as err:
        unmask("Нажмите ⟦1⟧OK⟦0⟧ сейчас", m)
    assert "tags_unbalanced" in codes(err.value.problems)


# --- verify ----------------------------------------------------------------

def test_verify_client_case():
    problems = verify("We sent a code to %1$s", "Код %1$с рақамига юборилди")
    assert codes(problems) == ["corrupted", "missing"]


def test_verify_ok_and_positional_reorder():
    assert verify("%1$s of %2$s", "%2$s дан %1$s") == []
    assert verify("Hi {name}", "Привет {name}") == []
    assert verify("", "") == []
    assert verify("Hi %s", "") == []  # untranslated is not a placeholder problem


def test_verify_count_mismatch_and_extra():
    assert codes(verify("%s %s", "%s")) == ["count_mismatch"]
    assert codes(verify("Hi", "Привет {name}")) == ["extra"]


# --- context ---------------------------------------------------------------

def test_placeholder_context_lists_this_texts_tokens():
    m = mask("Hi %1$s, %2$d left")
    context = placeholder_context(m)
    assert "⟦0⟧, ⟦1⟧" in context and "transliterate" in context
    assert placeholder_context(mask("Plain")) is None


def test_placeholder_context_mentions_optional_count():
    m = mask("%d item")
    assert "may be left out" in placeholder_context(m, frozenset({"%d"}))


def test_rewrite_context_uses_tokens():
    m = mask("%d items")
    assert rewrite_context("Source forms: one: '%d item'; other: '%d items'.", m) == (
        "Source forms: one: '⟦0⟧ item'; other: '⟦0⟧ items'."
    )


def test_combine_context():
    m = mask("%d items")
    combined = combine_context("Plural form 'few'.", m)
    assert combined.startswith("Plural form 'few'.") and "⟦0⟧" in combined
    assert combine_context(None, mask("Plain")) is None
    assert combine_context("note", mask("Plain")) == "note"


# --- repair ----------------------------------------------------------------

@pytest.mark.parametrize(
    "source, target, expected",
    [
        ("We sent a code to %1$s. Resend in %2$d s", "Код %1$с рақамига. %2$д сониядан", "Код %1$s рақамига. %2$d сониядан"),
        ("%1$d of %2$d left", "%2$д тадан %1$д", "%2$d тадан %1$d"),
        ("%1$d points", "%1$д очко", "%1$d очко"),
        ('Hi <xliff:g id="n">%1$s</xliff:g>!', 'Салом <xliff:g id="n">%1$с</xliff:g>!', 'Салом <xliff:g id="n">%1$s</xliff:g>!'),
        ("Price %@", "Цена ％＠", "Цена %@"),
        ("Hi %s", "Привет %с", "Привет %s"),
        ("Hi {{name}}", "Привет {{ имя }}", "Привет {{name}}"),
        ("Hi %(name)s", "Привет %(имя)s", "Привет %(name)s"),
        ("Hi %1$s", "Γεια %1$σ", "Γεια %1$s"),
    ],
)
def test_repair_fixes_damaged_placeholders(source, target, expected):
    assert repair(source, target) == expected
    assert verify(source, expected) == []


def test_repair_returns_none_when_nothing_to_fix_or_ambiguous():
    assert repair("Hi %s", "Привет %s") is None
    # two different placeholders lost, no candidates: needs retranslation
    assert repair("%1$s and %2$s", "и") is None
    # two unknown names for two missing names: ambiguous
    assert repair("{a} {b}", "{икс} {игрек}") is None


def test_repair_is_idempotent():
    fixed = repair("%1$d points", "%1$д очко")
    assert repair("%1$d points", fixed) is None


# --- plural exemption ------------------------------------------------------

def test_count_drop_allowed():
    assert count_drop_allowed("%1$d of {count} by %s and {name}") == frozenset({"%1$d", "{count}"})


def test_drop_allowed_for_key_depends_on_target_language():
    # German "one" is only 1; Russian "one" also covers 21, 31 …
    assert drop_allowed_for_key("items.__plurals__.one", "%d item", "de") == frozenset({"%d"})
    assert drop_allowed_for_key("items.__plurals__.one", "%d item", "ru") == frozenset()
    assert drop_allowed_for_key("items.__plurals__.other", "%d items", "de") == frozenset()
    assert drop_allowed_for_key("title", "%d", "de") == frozenset()


def test_no_false_positives_for_icu_branches_and_plain_percent():
    icu = "{count, plural, one {# item} other {# items}}"
    assert verify(icu, "{count, plural, one {# предмет} few {# предмета} other {# предметов}}") == []
    assert verify("Save 50% more", "Скидка 50%больше") == []
    # …but a damaged printf is still found when the source uses printf
    assert codes(verify("Save %d%% more", "Скидка %д%% больше")) == ["corrupted", "missing"]


def test_detect_profile_keeps_only_syntaxes_in_use():
    from algebras.services.placeholders import detect_profile

    texts = ["Hi {{name}}", "You have {{count}} items", "Plain"]
    profile = detect_profile(texts, ["i18next", "icu_simple", "printf"], "json", always=["xml_tag"])
    assert profile.syntax_names == ("xml_tag", "i18next")
    assert profile.name == "json:i18next"
    assert detect_profile(["Plain"], ["printf"], "x").syntax_names == ()


def test_profile_resolver_is_used_and_cached(tmp_path):
    from algebras.services.placeholders import register_profile_resolver

    calls = []

    def resolver(path, config):
        calls.append(path)
        return PlaceholderProfile(name="resolved", syntax_names=("printf",))

    register_profile_resolver([".resolvedfmt"], resolver)
    f = tmp_path / "a.resolvedfmt"
    f.write_text("x")
    assert profile_for_path(str(f)).name == "resolved"
    assert profile_for_path(str(f)).name == "resolved"
    assert len(calls) == 1


def test_healthcheck_reports_codes_added_by_format_checks():
    from algebras.services.placeholders.syntaxes import SYNTAXES, Syntax
    from algebras.utils.translation_validator import check_placeholders
    import re

    def check(src, tgt, problems):
        from algebras.services.placeholders import Problem
        return problems + [Problem("custom_code", "@@x", "custom problem")]

    SYNTAXES["test_custom"] = Syntax(name="test_custom", kind="named", pattern=re.compile(r"@@\w+"), check=check)
    profile = PlaceholderProfile(name="t", syntax_names=("test_custom",))
    issues = check_placeholders("Hi @@x", "Привет @@x", "k", profile)
    assert [(i.severity, i.message) for i in issues] == [("error", "custom problem")]
    del SYNTAXES["test_custom"]


def test_percent_before_cjk_text_is_not_a_damaged_placeholder():
    # Seen against the real API: Japanese "50%オフ" ("50% off") right after a percent sign.
    assert verify("Save 50% now, only %d left", "今なら50%オフ、残りわずか%d点") == []
    # Cyrillic/Greek/fullwidth letters after % are still caught.
    assert codes(verify("Only %d left", "Осталось %д")) == ["corrupted", "missing"]
    assert codes(verify("Only %d left", "Μόνο %δ")) == ["corrupted", "missing"]
    assert codes(verify("Only %d left", "残り%ｄ")) == ["corrupted", "missing"]
