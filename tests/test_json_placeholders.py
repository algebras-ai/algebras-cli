"""
JSON placeholder protection: profile auto-detection per i18n library (i18next, FormatJS, vue-i18n,
Chrome messages.json), translation end to end with a transliterating model, i18next plural forms,
and 'algebras placeholders' check / --fix / --dry-run.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from algebras.commands import placeholders_command, translate_command
from algebras.services.placeholders import extract, mask, profile_for_path, verify
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.formats import json_format
from algebras.services.placeholders.formats.json_format import check_file, repair_value, string_spans, write_fixes
from algebras.utils.json_i18n import plan_json_translation

I18NEXT = {
    "greeting": "Hello, {{name}}!",
    "html": "Click {{- link}} to continue",
    "nested": {
        "terms": "Read $t(legal.terms) before you start",
        "item_one": "One item",
        "item_other": "{{count}} items",
        "price": "Total: {{value, number}}",
    },
    "trans": "Press <0>Save</0> to keep {{name}}'s changes",
    "legal": {"terms": "Terms of use"},
}

FORMATJS = {
    "welcome": "Welcome, {name}!",
    "cart": "{count, plural, one {# item} other {# items}} in <b>your cart</b>",
    "promo": "Get <b>{percent}%</b> off with <link>this offer</link>",
}

VUE = {
    "brand": "Algebras",
    "about": "About @:brand",
    "title": "@.capitalize:brand home",
    "apples": "no apples | one apple | {count} apples",
    "hello": "Hello {name}",
}

CHROME = {
    "appName": {"message": "Tab Saver", "description": "Extension name"},
    "greeting": {
        "message": "Hello $USER$, you have $1 open tabs",
        "description": "Greeting shown in the popup",
        "placeholders": {"user": {"content": "$1", "example": "Alice"}},
    },
}

FIXTURES = {
    "i18next": I18NEXT,
    "formatjs": FORMATJS,
    "vue": VUE,
    "chrome": CHROME,
}


@pytest.fixture(autouse=True)
def json_fix_writer():
    # Other tests may replace writers with recording ones; use the real one here.
    register_fix_writer([".json"], json_format.write_fixes)
    yield


def _write_json(path, data, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    return path


def _source_path(tmp_path, name):
    if name == "chrome":
        return tmp_path / "_locales" / "en" / "messages.json"
    return tmp_path / "locales" / "en" / f"{name}.json"


def _target_path(tmp_path, name, locale):
    if name == "chrome":
        return tmp_path / "_locales" / locale / "messages.json"
    return tmp_path / "locales" / locale / f"{name}.json"


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected, absent",
    [
        ("i18next", {"i18next_nesting", "i18next", "indexed_tag"}, {"icu_simple", "vue_linked", "chrome"}),
        ("formatjs", {"icu_simple", "xml_tag"}, {"i18next", "vue_linked", "vue_pipe", "chrome"}),
        ("vue", {"vue_linked", "vue_pipe", "icu_simple"}, {"i18next", "i18next_nesting", "chrome"}),
        ("chrome", {"chrome"}, {"i18next", "icu_simple", "printf"}),
    ],
)
def test_profile_is_detected_per_library(tmp_path, name, expected, absent):
    path = _write_json(_source_path(tmp_path, name), FIXTURES[name])
    profile = profile_for_path(str(path))
    assert expected <= set(profile.syntax_names), profile
    assert not absent & set(profile.syntax_names), profile


def test_more_specific_syntax_wins():
    profile = profile_for_path_from(I18NEXT)
    # {{name}} is one i18next token, not an ICU {name} inside braces; $t() is a linked key.
    assert [(p.raw, p.syntax) for p in extract("Hi {{name}}, $t(a.b)", profile)] == [
        ("{{name}}", "i18next"),
        ("$t(a.b)", "i18next_nesting"),
    ]


def profile_for_path_from(data, tmp_dir=None):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = f"{d}/x.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return profile_for_path(path)


def test_config_pins_the_profile(tmp_path):
    path = _write_json(_source_path(tmp_path, "vue"), VUE)
    config = MagicMock()
    config.get_source_files.return_value = {str(path): {"placeholders": ["icu_simple"]}}
    assert profile_for_path(str(path), config).syntax_names == ("icu_simple",)


def test_vue_pipe_and_linked_keys_are_masked():
    profile = profile_for_path_from(VUE)
    assert mask("no apples | one apple | {count} apples", profile).text == "no apples ⟦0⟧ one apple ⟦1⟧ ⟦2⟧ apples"
    assert mask("About @.lower:brand, see @:docs.intro.", profile).text == "About ⟦0⟧, see ⟦1⟧."
    # Losing a plural form (a pipe) is caught.
    assert [p.code for p in verify("a | b | c", "а | б", profile)] == ["count_mismatch"]


def test_formatjs_rich_text_tags_are_paired_tokens():
    profile = profile_for_path_from(FORMATJS)
    masked = mask("Get <b>{percent}%</b> off with <link>this offer</link>", profile)
    assert masked.text == "Get ⟦0⟧⟦1⟧%⟦2⟧ off with ⟦3⟧this offer⟦4⟧"


# ---------------------------------------------------------------------------
# Chrome messages.json and i18next plurals in the translation plan
# ---------------------------------------------------------------------------


def test_chrome_sends_only_messages():
    plan = plan_json_translation(CHROME, ["greeting", "appName.description", "appName.message"], "en", "ru", None)
    assert plan.source == {"appName": {"message": "Tab Saver"}, "greeting": {"message": CHROME["greeting"]["message"]}}
    assert plan.keys == ["greeting", "appName.message"]
    result = plan.finish({"greeting": {"message": "Привет"}, "appName": {"message": "Вкладки"}}, ["greeting", "appName.message"])
    assert result["greeting"] == {
        "message": "Привет",
        "description": "Greeting shown in the popup",
        "placeholders": {"user": {"content": "$1", "example": "Alice"}},
    }
    assert result["appName"] == {"message": "Вкладки", "description": "Extension name"}


def test_i18next_multi_count_form_is_translated_from_other():
    profile = profile_for_path_from(I18NEXT)
    ru = plan_json_translation(I18NEXT, None, "en", "ru", profile)
    assert ru.source["nested"]["item_one"] == "{{count}} items"  # ru one = 1, 21, 31 …
    assert "keep the count placeholder ({{count}})" in ru.contexts["nested.item_one"]
    de = plan_json_translation(I18NEXT, None, "en", "de", profile)
    assert de.source["nested"]["item_one"] == "One item"  # de one = 1 only


# ---------------------------------------------------------------------------
# Translation end to end
# ---------------------------------------------------------------------------

_LATIN_TO_CYRILLIC = str.maketrans(dict(zip("sdcSDabeiklmnoprtuvxyzUSER", "сдсСДабеиклмнопртувхйзУСЕР")))


def transliterate(text: str) -> str:
    """The uz-Cyrl failure: every Latin letter becomes Cyrillic, and braces get spaces."""
    return text.translate(_LATIN_TO_CYRILLIC).replace("{{", "{{ ").replace("}}", " }}")


def _fake_client(sent):
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append((list(texts), list(kwargs.get("contexts") or [])))
        return [transliterate(t) for t in texts]

    client.translate_batch.side_effect = translate_batch
    client.translate.side_effect = lambda text, *a, **k: transliterate(text)
    return client


def _project(tmp_path, monkeypatch, languages=("en", "ru", "de")):
    source_files = {}
    for name, data in FIXTURES.items():
        path = _write_json(_source_path(tmp_path, name), data)
        rel = str(path.relative_to(tmp_path))
        source_files[rel] = {"destination_path": rel.replace("/en/", "/%algebras_locale_code%/")}
    (tmp_path / ".algebras.config").write_text(
        json.dumps({"languages": list(languages), "source_files": source_files, "api": {"provider": "algebras-ai"}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")


def _translate(languages, sent, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        for language in languages:
            translate_command.execute(language=language, **kwargs)


def _all_placeholders(text, profile):
    return sorted(p.raw for p in extract(text, profile))


def test_transliterating_model_keeps_every_placeholder(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    sent = []
    _translate(["ru", "de"], sent, force="__all__")

    for name in FIXTURES:
        source = _source_path(tmp_path, name)
        profile = profile_for_path(str(source))
        for locale in ("ru", "de"):
            target = _target_path(tmp_path, name, locale)
            data = json.loads(target.read_text(encoding="utf-8"))
            assert check_file(str(source), str(target), "en", locale) == [], (name, locale)
            if name == "chrome":
                assert data["greeting"]["description"] == CHROME["greeting"]["description"]
                assert data["greeting"]["placeholders"] == CHROME["greeting"]["placeholders"]
                assert sorted(data["greeting"]["message"].split(" ")[1:2]) == ["$USER$,"]
                assert "$1" in data["greeting"]["message"]
                assert list(data["greeting"]) == ["message", "description", "placeholders"]
                continue
            for path, text in _strings(FIXTURES[name]):
                translated = _get(data, path)
                if path == ("nested", "item_one"):
                    expected = ["{{count}}"] if locale == "ru" else []
                    assert _all_placeholders(translated, profile) == expected, (locale, translated)
                else:
                    assert _all_placeholders(translated, profile) == _all_placeholders(text, profile), (name, path, translated)

    # The model never saw a raw placeholder, linked key or pipe; Chrome descriptions were not sent.
    texts = [t for batch, _ in sent for t in batch]
    for raw in ("{{", "$t(", "@:", "@.", "|", "{name}", "$USER$", "$1", "<b>", "<0>", "Extension name"):
        assert not any(raw in t for t in texts), raw


def _strings(data, prefix=()):
    for key, value in data.items():
        if isinstance(value, dict):
            yield from _strings(value, prefix + (key,))
        else:
            yield prefix + (key,), value


def _get(data, path):
    for part in path:
        data = data[part]
    return data


def test_missing_keys_keep_chrome_fields_and_existing_values(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, ("en", "ru"))
    target = _write_json(
        _target_path(tmp_path, "chrome", "ru"),
        {"appName": {"message": "Сохранятель вкладок", "description": "Название"}},
    )
    sent = []
    _translate(["ru"], sent, only_missing=True)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["appName"] == {"message": "Сохранятель вкладок", "description": "Название"}
    assert data["greeting"]["placeholders"] == CHROME["greeting"]["placeholders"]
    assert data["greeting"]["description"] == CHROME["greeting"]["description"]
    assert "$USER$" in data["greeting"]["message"] and "$1" in data["greeting"]["message"]
    assert not any("Greeting shown" in t or t == "Alice" for batch, _ in sent for t in batch)


def test_missing_plural_keys_get_count_and_plural_notes(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, ("en", "ru"))
    existing = {"greeting": "Привет, {{name}}!", "nested": {"terms": "См. $t(legal.terms)"}}
    target = _write_json(_target_path(tmp_path, "i18next", "ru"), existing, indent=4)
    sent = []
    _translate(["ru"], sent, only_missing=True)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["greeting"] == existing["greeting"]
    assert "{{count}}" in data["nested"]["item_one"] and "{{count}}" in data["nested"]["item_other"]
    assert data["nested"]["price"].endswith("{{value, number}}")
    # One text can be sent several times (ru one and other both use "{{count}} items"), so keep
    # every (text, context) pair instead of a dict keyed by text.
    pairs = [(t, c) for batch, contexts in sent for t, c in zip(batch, contexts or [None] * len(batch))]
    assert "One item" not in {t for t, _ in pairs}  # ru one is translated from "{{count}} items"
    notes = [c for _, c in pairs if c and "i18next plural form 'one' for Russian" in c]
    assert notes and "keep the count placeholder (⟦0⟧)" in notes[0]


# ---------------------------------------------------------------------------
# 'algebras placeholders'
# ---------------------------------------------------------------------------

I18NEXT_RU = {
    "greeting": "Привет, {{ имя }}!",
    "html": "Нажмите {{- link}}, чтобы продолжить",
    "nested": {
        "terms": "Прочтите $t(юридический.условия) перед началом",
        "item_one": "{{count}} товар",
        "item_few": "{{count}} товара",
        "item_many": "{{count}} товаров",
        "item_other": "{{count}} товара",
        "price": "Итого: {{ value, number }}",
    },
    "trans": "Нажмите <0>Сохранить</0>, чтобы сохранить изменения {{name}}",
    "legal": {"terms": "Условия использования"},
}

VUE_RU = {
    "brand": "Algebras",
    "about": "О компании @:бренд",
    "title": "@.capitalize:brand — главная",
    "apples": "нет яблок | одно яблоко | {количество} яблок",
    "hello": "Привет {name}",
}

CHROME_RU = {
    "appName": {"message": "Сохранятель вкладок", "description": "Extension name"},
    "greeting": {
        "message": "Привет $ПОЛЬЗОВАТЕЛЬ$, у вас открыто $1 вкладок",
        "description": "Greeting shown in the popup",
        "placeholders": {"user": {"content": "$1", "example": "Alice"}},
    },
}

@pytest.fixture
def ru_project(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, ("en", "ru"))
    # Different layouts: 4-space indent, a tab indent with escaped non-ASCII, the usual 2 spaces.
    i18n = _target_path(tmp_path, "i18next", "ru")
    i18n.parent.mkdir(parents=True, exist_ok=True)
    i18n.write_text(json.dumps(I18NEXT_RU, ensure_ascii=False, indent=4), encoding="utf-8")
    vue = _target_path(tmp_path, "vue", "ru")
    vue.write_text(json.dumps(VUE_RU, ensure_ascii=True, indent="\t") + "\n", encoding="utf-8")
    chrome = _write_json(_target_path(tmp_path, "chrome", "ru"), CHROME_RU)
    formatjs = _write_json(_target_path(tmp_path, "formatjs", "ru"), {
        "welcome": "Добро пожаловать, {name}!",
        "cart": "{count, plural, one {# товар} other {# товаров}} в <b>корзине</b>",
        "promo": "Скидка <b>{percent}%</b> по <link>этому предложению</link>",
    })
    return {"i18next": i18n, "vue": vue, "chrome": chrome, "formatjs": formatjs}


def _report(capsys, **kwargs):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json", **kwargs)
    return code, json.loads(capsys.readouterr().out)


def test_check_reports_exact_codes(ru_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    problems = {
        (i["source_file"].split("/")[-1], i["key"]): sorted(p["code"] for p in i["problems"])
        for i in report["issues"]
    }
    assert problems == {
        ("i18next.json", "greeting"): ["extra", "missing"],
        ("i18next.json", "nested.terms"): ["linked_key_changed"],
        ("i18next.json", "nested.price"): ["extra", "missing"],
        ("vue.json", "about"): ["linked_key_changed"],
        ("vue.json", "apples"): ["corrupted", "missing"],
        ("messages.json", "greeting.message"): ["corrupted", "missing"],
    }
    assert all(i["fixed"] is not None for i in report["issues"])


def test_multi_count_form_without_count_is_reported(ru_project, capsys):
    data = dict(I18NEXT_RU, nested=dict(I18NEXT_RU["nested"], item_one="Один товар", item_few="товара"))
    ru_project["i18next"].write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    _, report = _report(capsys)
    issues = {i["key"]: i for i in report["issues"] if i["source_file"].endswith("i18next.json")}
    # ru one covers 1, 21, 31 …: checked against the _other text, so {{count}} is required.
    assert issues["nested.item_one"]["source"] == "{{count}} items"
    assert [p["code"] for p in issues["nested.item_one"]["problems"]] == ["missing"]
    # A target-only form is checked against _other too.
    assert issues["nested.item_few"]["source"] == "{{count}} items"


def test_single_count_form_may_spell_out_the_number(tmp_path):
    source = _write_json(tmp_path / "en" / "a.json", {"item_one": "{{count}} item", "item_other": "{{count}} items"})
    target = _write_json(tmp_path / "de" / "a.json", {"item_one": "Ein Element", "item_other": "{{count}} Elemente"})
    assert check_file(str(source), str(target), "en", "de") == []
    ru = _write_json(tmp_path / "ru" / "a.json", {"item_one": "Один элемент", "item_other": "{{count}} элемента"})
    assert [f.key for f in check_file(str(source), str(ru), "en", "ru")] == ["item_one"]


def test_fix_repairs_in_place_and_is_idempotent(ru_project, capsys):
    before = {name: path.read_text(encoding="utf-8") for name, path in ru_project.items()}
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert {i["status"] for i in report["issues"]} == {"fixed"}

    i18n = ru_project["i18next"].read_text(encoding="utf-8")
    assert i18n == (
        before["i18next"]
        .replace("{{ имя }}", "{{name}}")
        .replace("$t(юридический.условия)", "$t(legal.terms)")
        .replace("{{ value, number }}", "{{value, number}}")
    )
    vue = ru_project["vue"].read_text(encoding="utf-8")
    # Tab indent, \\u escapes and the trailing newline are kept; only the fixed values change.
    assert vue == before["vue"].replace(
        json.dumps("О компании @:бренд"), json.dumps("О компании @:brand")
    ).replace(json.dumps("нет яблок | одно яблоко | {количество} яблок"), json.dumps("нет яблок | одно яблоко | {count} яблок"))
    assert json.loads(vue)["apples"] == "нет яблок | одно яблоко | {count} яблок"
    chrome = json.loads(ru_project["chrome"].read_text(encoding="utf-8"))
    assert chrome["greeting"]["message"] == "Привет $USER$, у вас открыто $1 вкладок"
    assert ru_project["formatjs"].read_text(encoding="utf-8") == before["formatjs"]

    fixed = {name: path.read_text(encoding="utf-8") for name, path in ru_project.items()}
    code, report = _report(capsys)
    assert (code, report["issues"]) == (0, [])
    code, report = _report(capsys, fix=True)
    assert code == 0
    assert {name: path.read_text(encoding="utf-8") for name, path in ru_project.items()} == fixed


def test_dry_run_writes_nothing(ru_project, capsys):
    before = {name: path.read_text(encoding="utf-8") for name, path in ru_project.items()}
    code, _ = _report(capsys, fix=True, dry_run=True)
    assert code == 1
    assert {name: path.read_text(encoding="utf-8") for name, path in ru_project.items()} == before


# ---------------------------------------------------------------------------
# Repair and writer details
# ---------------------------------------------------------------------------


def test_linked_keys_restored_by_order_without_undoing_a_reorder():
    profile = profile_for_path_from(I18NEXT)
    source = "$t(a.one) and $t(b.two)"
    # Intact keys may move; only the changed one is replaced by the key it lost.
    assert repair_value(source, "$t(b.two) и $t(а.один)", profile) == "$t(b.two) и $t(a.one)"
    assert repair_value(source, "$т(a.one) и $t(b.two)", profile) == "$t(a.one) и $t(b.two)"


def test_string_spans_and_writer_keep_everything_else(tmp_path):
    text = '{\n  "a" : "x",\n  "list": [1, "y", {"b": "z"}],\n  "n": {"k\\u00e9": "v", "e": null}\n}'
    spans = string_spans(text)
    assert text[slice(*spans[("a",)])] == '"x"'
    assert text[slice(*spans[("list", "2", "b")])] == '"z"'
    assert text[slice(*spans[("n", "ké")])] == '"v"'
    path = tmp_path / "t.json"
    path.write_text(text, encoding="utf-8")
    write_fixes(str(path), {("n", "ké"): 'new "é"'})
    assert path.read_text(encoding="utf-8") == text.replace('"v"', '"new \\"\\u00e9\\""')
    with pytest.raises(ValueError):
        write_fixes(str(path), {("missing",): "x"})
