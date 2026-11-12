"""
ICU plural branches for the target language: a plural message gets the CLDR categories the target
needs (en one/other -> ru one/few/many/other), each new branch seeded from the source 'other' and
translated with a note naming its category. Covers Flutter ARB, FormatJS JSON and the
'algebras placeholders' report (missing_form) plus --retranslate.
"""

import json
import re
from unittest.mock import MagicMock, patch

import pytest
from pyicumessageformat import Parser

from algebras.commands import placeholders_command, translate_command
from algebras.services.icu_message_service import ICUMessageService
from algebras.services.placeholders.formats import json_format
from algebras.services.placeholders.formats.arb import message_problems
from algebras.services.placeholders.formats.xliff import translation_problem

_CATEGORY = re.compile(r"ICU plural category '(\w+)'")


def _keywords(text, name="count"):
    """Branch keywords of the plural argument `name`, in order."""

    def find(nodes):
        for node in nodes:
            if isinstance(node, dict):
                if node.get("name") == name and node.get("type") == "plural":
                    return list(node["options"])
                for value in (node.get("options") or {}).values():
                    found = find(value)
                    if found:
                        return found
        return None

    return find(Parser().parse(text))


def _branch(text, keyword, name="count"):
    match = re.search(r"(?:^|[\s{])" + re.escape(keyword) + r"\s*\{", text)
    assert match, (keyword, text)
    depth, start = 0, match.end() - 1
    for i in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start + 1 : i]
    raise AssertionError(text)


def _fake_client(sent):
    """Russian-ish fake model: the noun form follows the category named in the segment's note."""
    forms = {"one": "товар", "few": "товара", "many": "товаров", "other": "товара"}
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        contexts = list(kwargs.get("contexts") or [None] * len(texts))
        sent.append((list(texts), contexts))
        out = []
        for text, context in zip(texts, contexts):
            match = _CATEGORY.search(context or "")
            if match and re.search(r"\bitems?\b", text):
                out.append(re.sub(r"\bitems?\b", forms.get(match.group(1), "товара"), text))
            else:
                out.append(f"{text} [ru]")
        return out

    client.translate_batch.side_effect = translate_batch
    return client


def _project(tmp_path, monkeypatch, source_rel, source, destination, languages=("en", "ru")):
    path = tmp_path / source_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(source, indent=2, ensure_ascii=False), encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": list(languages),
                "source_files": {source_rel: {"destination_path": destination}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    cache = MagicMock()
    cache.get.return_value = None
    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)


def _run(sent, fn, *args, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        return fn(*args, **kwargs)


ARB_EN = {
    "@@locale": "en",
    "items": "{count, plural, one {# item} other {{count} items}}",
    "@items": {"placeholders": {"count": {"type": "int"}}},
    "cart": "{count, plural, =0 {Your cart is empty} one {# item in your cart} other {# items in your cart}}",
    "@cart": {"placeholders": {"count": {"type": "int"}}},
    "reply": "{gender, select, male {He replied} other {They replied}}",
}
ARB_DEST = "lib/l10n/app_%algebras_locale_code%.arb"


# --- service ------------------------------------------------------------------------------


def test_prepare_adds_target_categories_in_order():
    service = ICUMessageService()
    prepared = service.prepare(ARB_EN["cart"], "ru", "en")
    rebuilt = service.rebuild(prepared, prepared.translatable_segments)
    assert _keywords(rebuilt) == ["=0", "one", "few", "many", "other"]
    assert _branch(rebuilt, "few") == "# items in your cart"  # seeded from 'other'
    assert _branch(rebuilt, "=0") == "Your cart is empty"


def test_prepare_without_target_or_for_japanese_keeps_branches():
    service = ICUMessageService()
    for prepared in (service.prepare(ARB_EN["items"]), service.prepare(ARB_EN["items"], "ja", "en")):
        rebuilt = service.rebuild(prepared, prepared.translatable_segments)
        assert rebuilt == "{count, plural, one {# item} other {{count} items}}"


def test_select_and_selectordinal_are_not_expanded():
    service = ICUMessageService()
    for message in (
        ARB_EN["reply"],
        "{n, selectordinal, one {#st} two {#nd} few {#rd} other {#th}}",
    ):
        prepared = service.prepare(message, "ru", "en")
        assert service.rebuild(prepared, prepared.translatable_segments) == service.rebuild(
            service.prepare(message), prepared.translatable_segments
        )


def test_nested_plurals_are_all_expanded():
    service = ICUMessageService()
    message = "{a, plural, one {# file {b, plural, one {# dir} other {# dirs}}} other {# files {b, plural, one {# dir} other {# dirs}}}}"
    prepared = service.prepare(message, "ru", "en")
    rebuilt = service.rebuild(prepared, prepared.translatable_segments)
    assert service.validate(rebuilt)
    assert _keywords(rebuilt, "a") == ["one", "few", "many", "other"]
    inner = [m.group(0) for m in re.finditer(r"\{b, plural, [^{}]*(?:\{[^{}]*\}[^{}]*)*\}", rebuilt)]
    assert len(inner) == 4
    assert all("few {# dirs}" in i and "many {# dirs}" in i for i in inner)
    assert all(note for note in prepared.segment_notes)  # copies of the inner plural get notes too


def test_explicit_branch_covering_the_only_count_is_enough():
    service = ICUMessageService()
    prepared = service.prepare("{count, plural, =1 {One file} other {# files}}", "de", "en")
    assert _keywords(service.rebuild(prepared, prepared.translatable_segments)) == ["=1", "other"]


# --- ARB translation end to end -----------------------------------------------------------


def test_arb_en_to_ru_gets_all_categories(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, "lib/l10n/app_en.arb", ARB_EN, ARB_DEST)
    sent = []
    _run(sent, translate_command.execute, language="ru")
    written = json.loads((tmp_path / "lib" / "l10n" / "app_ru.arb").read_text(encoding="utf-8"))

    for key in ("items", "cart"):
        text = written[key]
        assert ICUMessageService().validate(text), text
        assert message_problems(ARB_EN[key], text, "ru") == [], key
        for category in ("one", "few", "many", "other"):
            body = _branch(text, category)
            assert "#" in body or "{count}" in body, (category, text)
    assert _keywords(written["items"]) == ["one", "few", "many", "other"]
    assert _keywords(written["cart"]) == ["=0", "one", "few", "many", "other"]
    assert _branch(written["cart"], "=0") == "Your cart is empty [ru]"
    assert _branch(written["items"], "few") == "{count} товара"
    assert _branch(written["items"], "many") == "{count} товаров"
    assert written["reply"].startswith("{gender, select, male {")

    # Every segment of a plural branch was sent with a note naming its category.
    pairs = [(t, c) for texts, contexts in sent for t, c in zip(texts, contexts)]
    categories = {_CATEGORY.search(c).group(1) for t, c in pairs if c and _CATEGORY.search(c)}
    assert categories == {"one", "few", "many", "other"}
    few_notes = [c for t, c in pairs if c and "category 'few'" in c]
    assert few_notes and all("2, 3, 4" in c and "English source branches" in c for c in few_notes)


def test_arb_en_to_ja_keeps_message_branches(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, "lib/l10n/app_en.arb", ARB_EN, ARB_DEST, ("en", "ja"))
    _run([], translate_command.execute, language="ja")
    written = json.loads((tmp_path / "lib" / "l10n" / "app_ja.arb").read_text(encoding="utf-8"))
    assert _keywords(written["items"]) == ["one", "other"]
    assert _keywords(written["cart"]) == ["=0", "one", "other"]


# --- FormatJS JSON ------------------------------------------------------------------------


FORMATJS_EN = {
    "cart": {"items": "{count, plural, one {# item for {name}} other {{count} items for {name}}}"},
    "hello": "Hello {name}",
}


def test_formatjs_json_gets_the_same_treatment(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch, "locales/en.json", FORMATJS_EN, "locales/%algebras_locale_code%.json")
    sent = []
    _run(sent, translate_command.execute, language="ru")
    target = tmp_path / "locales" / "ru.json"
    text = json.loads(target.read_text(encoding="utf-8"))["cart"]["items"]
    assert _keywords(text) == ["one", "few", "many", "other"]
    assert _branch(text, "many") == "{count} товаров for {name}"
    assert any("category 'many'" in (c or "") for _, contexts in sent for c in contexts)

    # The added branches repeat {count} and {name}: the placeholder check accepts them.
    findings = json_format.check_file(str(tmp_path / "locales" / "en.json"), str(target), "en", "ru")
    assert findings == []


def test_xliff_gate_accepts_added_branches():
    source = '{VAR_PLURAL, plural, =0 {no items} other {<x id="INTERPOLATION" equiv-text="count"/> items}}'
    target = (
        '{VAR_PLURAL, plural, =0 {нет товаров} one {<x id="INTERPOLATION" equiv-text="count"/> товар} '
        'few {<x id="INTERPOLATION" equiv-text="count"/> товара} '
        'many {<x id="INTERPOLATION" equiv-text="count"/> товаров} '
        'other {<x id="INTERPOLATION" equiv-text="count"/> товара}}'
    )
    assert translation_problem(source, target) is None
    assert translation_problem(source, target.replace("товаров", "много")) is None
    assert translation_problem(source, target.replace('many {<x id="INTERPOLATION" equiv-text="count"/>', "many {")) is not None


# --- algebras placeholders ----------------------------------------------------------------


def test_placeholders_reports_missing_form_and_retranslate_fills_it(tmp_path, monkeypatch, capsys):
    _project(tmp_path, monkeypatch, "lib/l10n/app_en.arb", ARB_EN, ARB_DEST)
    target = tmp_path / "lib" / "l10n" / "app_ru.arb"
    old = {
        "@@locale": "ru",
        "items": "{count, plural, one {# товар} other {{count} товара}}",
        "cart": "{count, plural, =0 {Корзина пуста} one {# товар в корзине} few {# товара в корзине} "
        "many {# товаров в корзине} other {# товара в корзине}}",
        "reply": "{gender, select, male {Он ответил} other {Они ответили}}",
    }
    target.write_text(json.dumps(old, indent=2, ensure_ascii=False), encoding="utf-8")

    capsys.readouterr()
    assert placeholders_command.execute(output_format="json") == 1
    report = json.loads(capsys.readouterr().out)
    assert [(i["key"], [p["code"] for p in i["problems"]], i["fixed"]) for i in report["issues"]] == [
        ("items", ["missing_form"], None)
    ]
    assert "few many" == report["issues"][0]["problems"][0]["placeholder"]

    # --fix alone cannot add a branch.
    assert placeholders_command.execute(output_format="json", fix=True) == 2
    capsys.readouterr()

    sent = []
    code = _run(sent, placeholders_command.execute, output_format="json", fix=True, retranslate=True)
    out = capsys.readouterr().out
    report = json.loads(out[out.index("\n{\n") + 1 :])
    assert code == 0
    assert {i["key"]: i["status"] for i in report["issues"]} == {"items": "fixed"}
    written = json.loads(target.read_text(encoding="utf-8"))
    assert _keywords(written["items"]) == ["one", "few", "many", "other"]
    assert written["cart"] == old["cart"]  # only the reported key was retranslated
    assert placeholders_command.execute(output_format="json") == 0


def test_source_branch_without_count_is_seeded_from_other_when_target_covers_several_counts():
    from algebras.services.icu_message_service import ICUMessageService

    svc = ICUMessageService()
    msg = "{count, plural, =0{No items} one{One item} other{{count} items}}"
    # ru one also covers 21, 31 …: translate it from 'other', which shows the count.
    assert svc.prepare(msg, "ru", "en").translatable_segments == ["No items", "items", "items", "items", "items"]
    # de one is exactly 1: "One item" is right as written.
    assert svc.prepare(msg, "de", "en").translatable_segments == ["No items", "One item", "items"]


def test_healthcheck_accepts_added_branches_and_reseeded_one():
    from algebras.utils.translation_validator import check_placeholders

    source = "{count, plural, one{One item for {name}} other{{count} items for {name}}}"
    target = (
        "{count, plural, one{{count} товар для {name}} few{{count} товара для {name}} "
        "many{{count} товаров для {name}} other{{count} товара для {name}}}"
    )
    assert check_placeholders(source, target, "k") == []
