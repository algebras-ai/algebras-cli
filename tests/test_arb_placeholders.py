"""
Flutter ARB placeholder safety: ICU arguments, plural/select keywords, '#' and '{' quoting survive
translation; damaged files are reported and repaired in place by 'algebras placeholders'.
"""

import json
import os
import re

import pytest
from pyicumessageformat import Parser

from algebras.commands import healthcheck_command, placeholders_command
from algebras.commands.translate_command import (
    _load_file_contents,
    _translate_plural_aware,
    _write_translated_content,
)
from algebras.services.icu_message_service import ICUMessageService
from algebras.services.placeholders import extract, mask, profile_for_path, verify
from algebras.services.placeholders.file_checks import get_file_check
from algebras.services.placeholders.fix_writers import get_fix_writer
from algebras.services.placeholders.formats.arb import (
    ARB_PROFILE,
    message_problems,
    repair_message,
    scan,
    walk,
)
from algebras.services.translator import Translator
from algebras.utils.arb_handler import locale_from_filename, read_arb_file, update_arb_values
from algebras.utils.file_format_detector import FileFormat, detect_format
from algebras.utils.file_format_handlers import ARBHandler, get_handler
from algebras.utils.lang_validator import read_language_file

from tests.test_placeholders_translation import transliterate
from tests.test_stringsdict_plurals import _batch_response, _mock_config

P = ARB_PROFILE

SOURCE = {
    "@@locale": "en",
    "greeting": "Hello {name}!",
    "@greeting": {
        "description": "Greets the user",
        "placeholders": {"name": {"type": "String", "example": "Ann"}},
    },
    "cartItems": "{count, plural, =0{Your cart is empty} one{# item for {name}} other{{count} items for {name}}}",
    "@cartItems": {"placeholders": {"count": {"type": "int"}, "name": {"type": "String"}}},
    "reply": "{gender, select, male{He replied} female{She replied} other{They replied}}",
    "braces": "Type '{name}' to insert a name, or '{' alone",
    "price": "Total: {amount, number, compact}",
    "farewell": "Bye {name}",
}


def _parses(text: str) -> bool:
    try:
        Parser().parse(text)
        return True
    except Exception:
        return False


def _structure(text: str):
    """Argument names, types and branch keywords, in order: what must never change."""
    return [(a.name, a.type, a.style, [o.keyword for o in a.options]) for a in walk(scan(text))]


# --- registration -------------------------------------------------------------------------


def test_arb_is_a_registered_format():
    assert detect_format("lib/l10n/app_en.arb") == FileFormat.ARB
    assert isinstance(get_handler("lib/l10n/app_en.arb"), ARBHandler)
    assert profile_for_path("lib/l10n/app_en.arb").name == "arb"
    assert get_file_check("lib/l10n/app_ru.arb") is not None
    assert get_fix_writer("lib/l10n/app_ru.arb") is not None


def test_read_language_file_skips_metadata(tmp_path):
    path = tmp_path / "app_en.arb"
    path.write_text(json.dumps(SOURCE), encoding="utf-8")
    data = read_language_file(str(path))
    assert set(data) == {"greeting", "cartItems", "reply", "braces", "price", "farewell"}


def test_locale_from_filename():
    assert locale_from_filename("lib/l10n/app_ru.arb") == "ru"
    assert locale_from_filename("lib/l10n/my_app_pt_BR.arb") == "pt_BR"
    assert locale_from_filename("lib/l10n/app_zh_Hant_TW.arb") == "zh_Hant_TW"
    assert locale_from_filename("lib/l10n/intl.arb") is None


# --- extraction ---------------------------------------------------------------------------


def test_simple_arguments_and_quotes_are_placeholders():
    raws = [p.raw for p in extract("Hi {name}, '{x}' {n, number, compact} and '{' {name}", P)]
    assert raws == ["{name}", "'{x}'", "{n, number, compact}", "'{'", "{name}"]
    assert mask(SOURCE["braces"], P).text == "Type ⟦0⟧ to insert a name, or ⟦1⟧ alone"


def test_branch_text_is_not_a_placeholder():
    source = "{count, plural, one{item} other{items}}"
    target = "{count, plural, one{элемент} few{элемента} many{элементов} other{элемента}}"
    assert [p.raw for p in extract(source, P)] == ["{count, plural}"]
    assert verify(source, target, P) == []


def test_plural_with_extra_target_branches_verifies_clean():
    target = (
        "{count, plural, =0{Корзина пуста} one{# товар для {name}} few{# товара для {name}} "
        "many{# товаров для {name}} other{{count} товара для {name}}}"
    )
    assert verify(SOURCE["cartItems"], target, P) == []
    assert message_problems(SOURCE["cartItems"], target, "ru") == []


def test_hash_stays_syntax_after_icu_rebuild():
    service = ICUMessageService()
    prepared = service.prepare(SOURCE["cartItems"])
    assert not any("#" in s for s in prepared.translatable_segments)
    rebuilt = service.rebuild(prepared, prepared.translatable_segments)
    assert _structure(rebuilt) == _structure(SOURCE["cartItems"])
    assert "one {# item for {name}}" in rebuilt


def test_quoted_braces_are_requoted_after_icu_rebuild():
    service = ICUMessageService()
    source = "{count, plural, one{Use '{' for # item} other{Type '{name}' for # items}}"
    prepared = service.prepare(source)
    rebuilt = service.rebuild(prepared, prepared.translatable_segments)
    assert Parser().parse(rebuilt) == Parser().parse(source)


# --- translation end to end ---------------------------------------------------------------


@pytest.fixture
def arb_project(tmp_path):
    l10n = tmp_path / "lib" / "l10n"
    l10n.mkdir(parents=True)
    source = l10n / "app_en.arb"
    source.write_text(json.dumps(SOURCE, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(source), str(l10n / "app_ru.arb")


def _fake_api(sent, answer):
    def post(url, headers=None, json=None, **kwargs):
        sent.append(json)
        return _batch_response([answer(t) for t in json["texts"]])

    return post


def _translate(source, target, lang, monkeypatch, answer):
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    sent = []
    monkeypatch.setattr("algebras.services.api_client.requests.post", _fake_api(sent, answer))
    config = _mock_config()
    translator = Translator(config=config)
    translator.api_client.set_sync_batch(True)
    handler = get_handler(source, config)
    source_content, target_content, source_raw, target_raw, contexts = _load_file_contents(
        source, target, handler, "en", lang, config
    )
    missing = sorted(set(source_content) - set(target_content))
    translated = _translate_plural_aware(
        translator.translate_missing_keys_batch,
        source_content,
        target_content,
        missing,
        lang,
        source_file_path=source,
        contexts=contexts,
    )
    _write_translated_content(
        target, translated, handler, set(missing), os.path.exists(target),
        source_file=source, source_language="en", target_language=lang,
        source_raw_content=source_raw, target_raw_content=target_raw,
    )
    return sent


_ARG_WORDS = ("name", "count", "gender", "amount", "plural", "select", "number", "compact", "male", "other")


def _renaming_model(text: str) -> str:
    """Translates argument-looking words and transliterates the rest, like the uz-Cyrl incident."""
    text = re.sub(r"\{(\w+)\}", lambda m: "{" + transliterate(m.group(1)) + "}", text)
    for word in _ARG_WORDS:
        text = text.replace(word, transliterate(word))
    return transliterate(text)


def test_transliterating_model_keeps_icu_structure(arb_project, monkeypatch):
    source, target = arb_project
    sent = _translate(source, target, "ru", monkeypatch, _renaming_model)

    written = read_arb_file(target)
    for key, value in SOURCE.items():
        if key.startswith("@"):
            continue
        assert key in written, key
        assert _parses(written[key]), (key, written[key])
        assert _structure(written[key]) == _structure(value), key
        assert message_problems(value, written[key], "ru") == [], key
    assert "'{name}'" in written["braces"] and "'{'" in written["braces"]
    assert written["greeting"].count("{name}") == 1

    # Argument names, types, keywords and quoted literals never reach the API.
    texts = [t for body in sent for t in body["texts"]]
    assert texts
    for t in texts:
        assert "{" not in t and "#" not in t, t
        assert not re.search(r"\b(count|gender|amount|plural|select|compact)\b", t), t


def test_damaged_tokens_are_not_written(arb_project, monkeypatch):
    source, target = arb_project
    _translate(source, target, "ru", monkeypatch, lambda t: re.sub(r"⟦\d+⟧", "", t) + " [ru]")
    written = read_arb_file(target)
    for key in ("greeting", "braces", "price", "farewell"):
        assert key not in written, key  # every token dropped: left missing, not written damaged
    assert written["reply"].startswith("{gender, select, male {")  # no placeholders: translated


def test_in_place_update_keeps_order_indentation_and_metadata(arb_project, monkeypatch):
    source, target = arb_project
    original = (
        '{\n    "@@locale": "ru",\n    "greeting": "Привет, {name}!",\n'
        '    "@greeting": {\n        "description": "Приветствие"\n    }\n}\n'
    )
    with open(target, "w", encoding="utf-8") as f:
        f.write(original)
    _translate(source, target, "ru", monkeypatch, lambda t: t + " [ru]")
    text = open(target, encoding="utf-8").read()
    assert text.startswith(original[: original.rindex("\n}")])  # existing entries byte for byte
    data = json.loads(text)
    assert list(data)[:3] == ["@@locale", "greeting", "@greeting"]
    assert data["farewell"] == "Bye [ru] {name}" or data["farewell"].endswith("{name} [ru]")
    assert '\n    "farewell": ' in text


def test_update_arb_values_changes_only_given_values(tmp_path):
    path = tmp_path / "app_ru.arb"
    original = '{\n\t"a": "x\\u0410",\n\t"@a": {"description": "d"},\n\t"b": "y"\n}'
    path.write_text(original, encoding="utf-8")
    assert update_arb_values(str(path), {"b": "z", "c": "new"}, add_missing=False) == ["c"]
    assert path.read_text(encoding="utf-8") == original.replace('"y"', '"z"')
    update_arb_values(str(path), {"c": "new"})
    assert path.read_text(encoding="utf-8").endswith('"z",\n\t"c": "new"\n}')


# --- check + autofix ----------------------------------------------------------------------


TARGET = {
    "@@locale": "ru",
    "greeting": "Привет, {имя}!",
    "@greeting": {"description": "Приветствие пользователя"},
    "cartItems": (
        "{count, plural, =0{Корзина пуста} one{# товар для {name}} few{# товара для {name}} "
        "many{# товаров для {name}} другое{{count} товара для {name}}}"
    ),
    "reply": "{gender, select, male{Он ответил} женский{Она ответила} other{Они ответили}}",
    "braces": "Введите '{name}', чтобы вставить имя, или '{' отдельно",
    "price": "Итого: {amount, number, компакт}",
    "farewell": "Пока!",
}


def _dump(data):
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


@pytest.fixture
def check_project(tmp_path, monkeypatch):
    l10n = tmp_path / "lib" / "l10n"
    l10n.mkdir(parents=True)
    (l10n / "app_en.arb").write_text(json.dumps(SOURCE, indent=2), encoding="utf-8")
    (l10n / "app_ru.arb").write_text(_dump(TARGET), encoding="utf-8")
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": ["en", "ru"],
                "source_files": {
                    "lib/l10n/app_en.arb": {"destination_path": "lib/l10n/app_%algebras_locale_code%.arb"}
                },
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _report(capsys):
    capsys.readouterr()
    code = placeholders_command.execute(output_format="json")
    return code, json.loads(capsys.readouterr().out)


EXPECTED_FIXED = {
    "greeting": "Привет, {name}!",
    "cartItems": TARGET["cartItems"].replace("другое{", "other{"),
    "reply": TARGET["reply"].replace("женский{", "female{"),
    "price": "Итого: {amount, number, compact}",
}


def test_check_reports_exact_codes(check_project, capsys):
    code, report = _report(capsys)
    assert code == 1
    issues = {i["key"]: i for i in report["issues"]}
    assert set(issues) == {"greeting", "cartItems", "reply", "price", "farewell"}
    codes = {k: sorted({p["code"] for p in v["problems"]}) for k, v in issues.items()}
    assert codes == {
        "greeting": ["icu_arg_renamed"],
        "cartItems": ["icu_keyword_changed", "icu_unparseable"],
        "reply": ["icu_keyword_changed"],  # select accepts any keyword: still parses
        "price": ["icu_type_changed"],
        "farewell": ["missing"],
    }
    for key, fixed in EXPECTED_FIXED.items():
        assert issues[key]["fixed"] == fixed, key
    assert issues["farewell"]["fixed"] is None


def test_fix_repairs_in_place_and_is_idempotent(check_project, capsys):
    target = check_project / "lib" / "l10n" / "app_ru.arb"
    assert placeholders_command.execute(fix=True, output_format="json") == 2  # 'farewell' needs retranslation

    expected = _dump({**TARGET, **EXPECTED_FIXED})
    assert target.read_text(encoding="utf-8") == expected  # order, 4-space indent, metadata kept
    for key in EXPECTED_FIXED:
        assert _parses(json.loads(expected)[key])

    code, report = _report(capsys)
    assert [i["key"] for i in report["issues"]] == ["farewell"]

    placeholders_command.execute(fix=True, output_format="json")
    assert target.read_text(encoding="utf-8") == expected


def test_dry_run_writes_nothing(check_project):
    target = check_project / "lib" / "l10n" / "app_ru.arb"
    assert placeholders_command.execute(fix=True, dry_run=True, output_format="json") == 1
    assert target.read_text(encoding="utf-8") == _dump(TARGET)


def test_healthcheck_covers_arb(check_project):
    issues, keys_checked, errors, _ = healthcheck_command.validate_file_pair(
        "lib/l10n/app_en.arb", "lib/l10n/app_ru.arb", "en", "ru", None, False
    )
    assert keys_checked == 6
    placeholder_keys = {i.key for i in issues if i.category == "placeholders"}
    assert {"greeting", "farewell"} <= placeholder_keys
    assert "system" not in {i.category for i in issues}


def test_iter_file_pairs_matches_arb_by_locale_suffix(tmp_path):
    source_files = [os.path.join("l10n", "app_en.arb")]
    assert healthcheck_command.find_source_file(os.path.join("l10n", "app_ru.arb"), source_files, "en", "ru") == source_files[0]


# --- repair unit cases --------------------------------------------------------------------


def test_repair_renamed_plural_argument_and_type():
    source = SOURCE["cartItems"]
    target = "{счёт, множественное, =0{Пусто} one{# товар для {name}} other{{счёт} товаров для {name}}}"
    problems = {p.code for p in message_problems(source, target, "ru")}
    assert {"icu_unparseable", "icu_arg_renamed"} <= problems
    assert repair_message(source, target, "ru") == (
        "{count, plural, =0{Пусто} one{# товар для {name}} other{{count} товаров для {name}}}"
    )


def test_declared_placeholders_are_known_names():
    # @key.placeholders declares {name}: using it in the target is not an unknown argument.
    assert message_problems("Hello", "Привет, {name}", "ru", declared=["name"]) == []
    assert message_problems("Hello", "Привет, {имя}", "ru")[0].code == "extra"


def test_branch_without_count_is_reported_for_multi_count_forms():
    source = "{count, plural, one{# item} other{# items}}"
    assert message_problems(source, "{count, plural, one{Ein Element} other{# Elemente}}", "de") == []
    problems = message_problems(source, "{count, plural, one{элемент} few{# элемента} other{# элементов}}", "ru")
    assert [(p.code, p.placeholder) for p in problems] == [("missing", "{count}")]
