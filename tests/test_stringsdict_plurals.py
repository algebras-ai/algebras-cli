"""
Plural forms the target language needs but the source .stringsdict lacks
(e.g. English one/other -> Russian one/few/many/other) are added, translated with
per-form context, validated, and counted by status/update.
"""

import os
import re
import shutil
from unittest.mock import MagicMock

import pytest

from algebras.commands.status_command import count_current_and_outdated_keys
from algebras.commands.translate_command import (
    _load_file_contents,
    _translate_plural_aware,
    _write_translated_content,
)
from algebras.config import Config
from algebras.services.api_client import AlgebrasAIClient
from algebras.services.batch_processor import BatchProcessor
from algebras.services.rate_limiter import RateLimiter
from algebras.services.retry_handler import RetryHandler
from algebras.services.translator import Translator
from algebras.utils.file_format_handlers import get_handler
from algebras.utils.ios_stringsdict_handler import (
    anchor_plural_contexts,
    build_plural_contexts,
    expand_plural_forms,
    extract_format_specifiers,
    extract_translatable_strings,
    read_ios_stringsdict_file,
    split_plural_passes,
    validate_plural_forms,
    write_ios_stringsdict_file,
)
from algebras.utils.lang_validator import validate_language_files
from algebras.utils.plural_rules import get_category_examples, get_plural_categories


def _plural(forms, value_type="d"):
    entry = {
        "NSStringFormatSpecTypeKey": "NSStringPluralRuleType",
        "NSStringFormatValueTypeKey": value_type,
    }
    entry.update(forms)
    return entry


EN_SOURCE = {
    "items_count": {
        "NSStringLocalizedFormatKey": "%#@count@",
        "count": _plural({"one": "One item", "other": "%d items"}),
    },
    "days_left": {
        "NSStringLocalizedFormatKey": "%#@days@",
        "days": _plural({"zero": "No days left", "one": "One day left", "other": "%ld days left"}),
    },
}


# --- plural rules (babel) ---------------------------------------------------

@pytest.mark.parametrize(
    "lang, expected",
    [
        ("en", ["one", "other"]),
        ("ru", ["one", "few", "many", "other"]),
        ("pl", ["one", "few", "many", "other"]),
        ("ar", ["zero", "one", "two", "few", "many", "other"]),
        ("ja", ["other"]),
        ("zh-Hans", ["other"]),
        ("pt-BR", ["one", "many", "other"]),
        ("pt_BR", ["one", "many", "other"]),
    ],
)
def test_plural_categories(lang, expected):
    assert get_plural_categories(lang) == expected


def test_unknown_language_falls_back_to_one_other():
    assert get_plural_categories("xx-YY") == ["one", "other"]


def test_category_examples():
    assert get_category_examples("ru", "few").startswith("2, 3, 4, 22, 23, 24")
    assert get_category_examples("ru", "one").startswith("1, 21, 31")
    assert get_category_examples("pl", "one") == "1"
    assert get_category_examples("fr", "many") == "1000000"
    assert get_category_examples("ru", "other").startswith("fractions such as")


# --- expansion --------------------------------------------------------------

def test_expand_adds_missing_target_forms_from_source_other():
    flat = extract_translatable_strings(EN_SOURCE)
    expanded = expand_plural_forms(EN_SOURCE, flat, "ru")

    assert expanded["items_count.count.few"] == "%d items"
    assert expanded["items_count.count.many"] == "%d items"
    assert expanded["items_count.count.one"] == "One item"
    # Explicit source zero is kept even though Russian doesn't use it.
    assert expanded["days_left.days.zero"] == "No days left"
    assert expanded["days_left.days.few"] == "%ld days left"
    assert set(flat) <= set(expanded)


def test_expand_adds_nothing_when_target_needs_fewer_forms():
    flat = extract_translatable_strings(EN_SOURCE)
    assert expand_plural_forms(EN_SOURCE, flat, "ja") == flat


def test_expand_uses_last_form_when_source_has_no_other():
    source = {"k": {"v": _plural({"one": "One file"})}}
    expanded = expand_plural_forms(source, extract_translatable_strings(source), "ru")
    assert expanded["k.v.other"] == "One file"
    assert expanded["k.v.few"] == "One file"


def test_contexts_describe_counts_and_source_forms():
    contexts = build_plural_contexts(EN_SOURCE, "en", "ru")

    few = contexts["items_count.count.few"]
    assert "'few' for Russian" in few
    assert "2, 3, 4, 22, 23, 24" in few
    assert "one: 'One item'" in few and "other: '%d items'" in few
    assert "(%d)" in few

    # Russian "one" also covers 21, 31... so the number placeholder must be used.
    one = contexts["items_count.count.one"]
    assert "1, 21, 31" in one
    assert "(%d)" in one

    assert "count is 0" in contexts["days_left.days.zero"]
    assert "(%ld)" in contexts["days_left.days.many"]


def test_contexts_skip_placeholder_hint_for_single_count_forms():
    contexts = build_plural_contexts(EN_SOURCE, "en", "pl")
    assert "count is 1." in contexts["items_count.count.one"]
    assert "number placeholder" not in contexts["items_count.count.one"]


# --- two-pass translation ----------------------------------------------------

def test_split_plural_passes_defers_forms_other_than_other():
    contexts = {"a.one": "c", "a.few": "c", "a.other": "c"}
    first, second = split_plural_passes(["a.one", "plain", "a.other", "a.few"], contexts)
    assert first == ["plain", "a.other"]
    assert second == ["a.one", "a.few"]


def test_anchor_adds_translated_other_and_skips_unknown():
    contexts = {"a.few": "ctx-a", "b.few": "ctx-b"}
    anchored = anchor_plural_contexts(
        contexts, ["a.few", "b.few"], {"a.other": "%d предметов", "b.other": ""}
    )
    assert anchored["a.few"].startswith("ctx-a ")
    assert "already translated as '%d предметов'" in anchored["a.few"]
    assert anchored["b.few"] == "ctx-b"
    assert contexts["a.few"] == "ctx-a"  # input not mutated


def _recording_translate(calls):
    def translate(source, target, keys, *args, contexts=None, **kwargs):
        calls.append((list(keys), dict(contexts or {})))
        result = dict(target)
        result.update({k: f"T({source[k]})" for k in keys})
        return result
    return translate


def test_plural_aware_translates_other_first_then_anchors_rest():
    calls = []
    source = {"a.one": "One item", "a.few": "%d items", "a.other": "%d items", "title": "Hi"}
    contexts = {k: f"ctx {k}" for k in ("a.one", "a.few", "a.other")}

    result = _translate_plural_aware(
        _recording_translate(calls), source, {}, list(source), "ru", contexts=contexts
    )

    assert [keys for keys, _ in calls] == [["a.other", "title"], ["a.one", "a.few"]]
    second_contexts = calls[1][1]
    assert "already translated as 'T(%d items)'" in second_contexts["a.few"]
    assert "already translated as 'T(%d items)'" in second_contexts["a.one"]
    assert set(result) == set(source)


def test_plural_aware_anchors_to_existing_target_other():
    # update filling only few/many: 'other' is already translated in the target file.
    calls = []
    contexts = {"a.few": "ctx few", "a.many": "ctx many", "a.other": "ctx other"}
    _translate_plural_aware(
        _recording_translate(calls),
        {"a.few": "%d items", "a.many": "%d items"},
        {"a.other": "%d предметов"},
        ["a.few", "a.many"],
        "ru",
        contexts=contexts,
    )
    assert len(calls) == 1
    assert "already translated as '%d предметов'" in calls[0][1]["a.many"]


def test_plural_aware_single_call_without_contexts():
    calls = []
    _translate_plural_aware(_recording_translate(calls), {"x": "a"}, {}, ["x"], "ru")
    assert calls == [(["x"], {})]


# --- validation -------------------------------------------------------------

def test_format_specifiers():
    assert extract_format_specifiers("%d items, %ld days, %@ and %1$@, 100%%") == sorted(
        ["%d", "%ld", "%@", "%1$@"]
    )


def _ru_target(forms):
    return {
        "items_count": {
            "NSStringLocalizedFormatKey": "%#@count@",
            "count": _plural(forms),
        }
    }


def test_validate_passes_complete_translation():
    source = {"items_count": EN_SOURCE["items_count"]}
    target = _ru_target(
        {"one": "%d товар", "few": "%d товара", "many": "%d товаров", "other": "%d товара"}
    )
    assert validate_plural_forms(target, source, "ru") == []


def test_validate_reports_missing_forms_and_placeholders():
    source = {"items_count": EN_SOURCE["items_count"]}
    target = _ru_target({"one": "Один товар", "other": "%@ товара", "few": "товара"})
    warnings = validate_plural_forms(target, source, "ru")

    assert "items_count.count: missing plural forms many" in warnings
    assert "items_count.count.other: placeholders not in source: %@" in warnings
    assert "items_count.count.few: missing placeholder %d" in warnings
    assert "items_count.count.one: missing placeholder %d" in warnings


def test_validate_allows_word_for_single_count_form():
    source = {"items_count": EN_SOURCE["items_count"]}
    target = _ru_target(
        {"one": "Jeden element", "few": "%d elementy", "many": "%d elementów", "other": "%d elementu"}
    )
    assert validate_plural_forms(target, source, "pl") == []


# --- contexts in API requests -----------------------------------------------

def _mock_config():
    config = MagicMock(spec=Config)
    config.exists.return_value = True
    config.load.return_value = {}
    config.get_api_config.return_value = {"provider": "algebras-ai"}
    config.get_base_url.return_value = "https://platform.algebras.ai"
    config.get_source_language.return_value = "en"
    config.has_setting.return_value = False
    config.get_setting.side_effect = lambda key, default=None: default
    return config


def _batch_response(texts):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": {"translations": [{"index": i, "content": t} for i, t in enumerate(texts)]}
    }
    return response


def test_sync_batch_sends_contexts_aligned_after_dropping_empty_texts(monkeypatch):
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    mock_post = MagicMock(return_value=_batch_response(["A", "C"]))
    monkeypatch.setattr("algebras.services.api_client.requests.post", mock_post)
    client = AlgebrasAIClient(_mock_config(), RetryHandler(rate_limiter=RateLimiter()), sync_batch=True)

    result = client.translate_batch(
        ["a", "", "c"], "en", "ru", contexts=["ctx-a", "ctx-empty", None]
    )

    assert result == ["A", "", "C"]
    body = mock_post.call_args[1]["json"]
    assert body["texts"] == ["a", "c"]
    assert body["contexts"] == ["ctx-a", None]


def test_batch_omits_contexts_when_none_given(monkeypatch):
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    mock_post = MagicMock(return_value=_batch_response(["A"]))
    monkeypatch.setattr("algebras.services.api_client.requests.post", mock_post)
    client = AlgebrasAIClient(_mock_config(), RetryHandler(rate_limiter=RateLimiter()), sync_batch=True)

    client.translate_batch(["a"], "en", "ru", contexts=[None])
    assert "contexts" not in mock_post.call_args[1]["json"]


def test_async_batch_sends_contexts(monkeypatch):
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    submit = MagicMock(status_code=200)
    submit.json.return_value = {"data": {"job_id": "job-1", "status": "PENDING"}}
    mock_post = MagicMock(return_value=submit)
    poll = MagicMock(status_code=200)
    poll.json.return_value = {
        "data": {"id": "job-1", "status": "READY", "result": {"translations": [{"index": 0, "content": "A"}]}}
    }
    monkeypatch.setattr("algebras.services.api_client.requests.post", mock_post)
    monkeypatch.setattr("algebras.services.api_client.requests.get", MagicMock(return_value=poll))
    client = AlgebrasAIClient(_mock_config(), RetryHandler(rate_limiter=RateLimiter()))

    assert client.translate_batch(["a"], "en", "ru", contexts=["ctx-a"]) == ["A"]
    assert mock_post.call_args[1]["json"]["contexts"] == ["ctx-a"]


def test_batch_processor_chunks_contexts_with_texts():
    api_client = MagicMock()
    api_client.translate_batch.side_effect = lambda texts, *a, **kw: [t.upper() for t in texts]
    processor = BatchProcessor(api_client, batch_size=2, max_parallel_batches=1, provider="algebras-ai")

    result = processor.process(
        ["a", "", "b", "c"], "en", "ru", False, "", contexts=["ca", "c-empty", None, "cc"]
    )

    assert result.translations == ["A", "", "B", "C"]
    sent = sorted(
        (call.args[0], call.kwargs.get("contexts")) for call in api_client.translate_batch.call_args_list
    )
    assert sent == [(["a", "b"], ["ca", None]), (["c"], ["cc"])]


def test_other_provider_warns_that_contexts_are_not_sent(capsys):
    translate_text = MagicMock(side_effect=lambda text, *a: text.upper())
    processor = BatchProcessor(MagicMock(), batch_size=2, max_parallel_batches=1, provider="openai")

    result = processor.process(
        ["a", "b"], "en", "ru", False, "", translate_text_func=translate_text, contexts=["ca", None]
    )

    assert result.translations == ["A", "B"]
    assert translate_text.call_count == 2
    assert "only sent to Algebras AI" in capsys.readouterr().out


def test_algebras_provider_does_not_warn_about_contexts(capsys):
    api_client = MagicMock()
    api_client.translate_batch.side_effect = lambda texts, *a, **kw: texts
    processor = BatchProcessor(api_client, batch_size=2, max_parallel_batches=1, provider="algebras-ai")

    processor.process(["a"], "en", "ru", False, "", contexts=["ca"])
    assert "only sent to Algebras AI" not in capsys.readouterr().out


# --- end to end: en -> ru ---------------------------------------------------

@pytest.fixture
def ios_project(tmp_path):
    en_dir = tmp_path / "en.lproj"
    en_dir.mkdir()
    source = str(en_dir / "Localizable.stringsdict")
    write_ios_stringsdict_file(source, EN_SOURCE)
    target = str(tmp_path / "ru.lproj" / "Localizable.stringsdict")
    os.makedirs(os.path.dirname(target))
    return source, target


def _fake_translate(sent_bodies):
    form_pattern = re.compile(r"plural form '(\w+)'")

    def post(url, headers=None, json=None, **kwargs):
        sent_bodies.append(json)
        contexts = json.get("contexts") or [None] * len(json["texts"])
        out = []
        for text, context in zip(json["texts"], contexts):
            match = form_pattern.search(context or "")
            out.append(f"RU[{match.group(1) if match else '-'}] {text}")
        return _batch_response(out)

    return post


def test_translate_en_to_ru_writes_all_russian_forms(ios_project, monkeypatch):
    source, target = ios_project
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test-key")
    sent = []
    monkeypatch.setattr("algebras.services.api_client.requests.post", _fake_translate(sent))

    config = _mock_config()
    translator = Translator(config=config)
    translator.api_client.set_sync_batch(True)
    handler = get_handler(source, config)

    source_content, target_content, source_raw, target_raw, contexts = _load_file_contents(
        source, target, handler, "en", "ru", config
    )
    missing = sorted(set(source_content) - set(target_content))
    translated = _translate_plural_aware(
        translator.translate_missing_keys_batch,
        source_content, target_content, missing, "ru", contexts=contexts,
    )
    _write_translated_content(
        target, translated, handler, set(missing), False,
        source_file=source, source_language="en", target_language="ru",
        source_raw_content=source_raw, target_raw_content=target_raw,
    )

    written = read_ios_stringsdict_file(target)["items_count"]["count"]
    assert written["one"] == "RU[one] One item"
    assert written["few"] == "RU[few] %d items"
    assert written["many"] == "RU[many] %d items"
    assert written["other"] == "RU[other] %d items"
    assert written["NSStringFormatValueTypeKey"] == "d"

    # Pass 1 sends the 'other' forms; pass 2 the rest, anchored to the translated 'other'.
    assert len(sent) == 2
    for body in sent:
        assert len(body["contexts"]) == len(body["texts"])
        assert all(c and "plural form" in c for c in body["contexts"])
    assert all("plural form 'other'" in c for c in sent[0]["contexts"])
    assert all("already translated as 'RU[other] " in c for c in sent[1]["contexts"])

    # Status and update now see a complete file with no outdated keys.
    assert validate_language_files(source, target, target_language="ru") == (True, set())
    current, outdated = count_current_and_outdated_keys(source, target, None, "ru")
    assert outdated == 0
    assert current == len(source_content)


def test_existing_ru_file_with_only_one_other_is_reported_incomplete(ios_project):
    source, target = ios_project
    shutil.copy(source, target)  # same keys as English: one/other only

    is_valid, missing = validate_language_files(source, target, target_language="ru")
    assert not is_valid
    assert missing == {
        "items_count.count.few",
        "items_count.count.many",
        "days_left.days.few",
        "days_left.days.many",
    }
    # Without a target language (other formats' behaviour) nothing changes.
    assert validate_language_files(source, target) == (True, set())
