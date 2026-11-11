"""
Second-pass plural anchoring for gettext .po and YAML (Rails plural hashes), and the placeholder
retries in BatchProcessor (a batch retry, then each text alone with the API cache bypassed).
"""

import json
import re
import threading
from unittest.mock import MagicMock, patch

import yaml

from algebras.commands import translate_command
from algebras.services.batch_processor import BatchProcessor
from algebras.services.translator import Translator
from algebras.utils import po_handler

_ANCHOR = "already translated as '"


def _fake_client(sent):
    """Fake Algebras AI client: 'RU ' + text; records (texts, contexts) of every call in order."""
    client = MagicMock()

    def translate_batch(texts, *args, **kwargs):
        sent.append((list(texts), list(kwargs.get("contexts") or [None] * len(texts))))
        return ["RU " + t for t in texts]

    client.translate_batch.side_effect = translate_batch
    return client


def _config(tmp_path, monkeypatch, source_rel, destination, languages):
    (tmp_path / ".algebras.config").write_text(
        json.dumps(
            {
                "languages": languages,
                "source_files": {source_rel: {"destination_path": destination}},
                "api": {"provider": "algebras-ai"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")


def _translate(sent, **kwargs):
    with patch("algebras.services.translator.AlgebrasAIClient", return_value=_fake_client(sent)):
        translate_command.execute(language="ru", **kwargs)


# ---------------------------------------------------------------------------
# PO
# ---------------------------------------------------------------------------

SOURCE_PO = r"""msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Language: en\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

msgid "Hello"
msgstr "Hello"

#, python-format
msgid "One file"
msgid_plural "%(counter)s files"
msgstr[0] "One file"
msgstr[1] "%(counter)s files"
"""


def test_po_anchor_maps_forms_through_plural_forms():
    for language, expected in (("ru", 2), ("en", 1), ("fr", 1), ("pl", 2), ("ja", 0), ("cs", 2)):
        nplurals, expr = po_handler.plural_forms_for_language(language)
        assert po_handler.plural_anchor_index(nplurals, expr, language) == expected, language
    # A custom Plural-Forms whose forms do not match CLDR: the last form.
    assert po_handler.plural_anchor_index(2, "(n > 5)", "en") == 1


def test_po_ru_second_pass_quotes_translated_other_form(tmp_path, monkeypatch):
    source = tmp_path / "locale" / "en" / "LC_MESSAGES" / "django.po"
    source.parent.mkdir(parents=True)
    source.write_text(SOURCE_PO, encoding="utf-8")
    _config(
        tmp_path, monkeypatch, "locale/en/LC_MESSAGES/django.po",
        "locale/%algebras_locale_code%/LC_MESSAGES/django.po", ["en", "ru"],
    )
    sent = []
    _translate(sent, force="__all__")

    # Which call sent which msgstr[N], and with which context.
    calls = {}
    for call_index, (texts, contexts) in enumerate(sent):
        for text, context in zip(texts, contexts):
            m = re.match(r"gettext plural form msgstr\[(\d)\]", context or "")
            if m:
                calls[int(m.group(1))] = (call_index, text, context)
    assert sorted(calls) == [0, 1, 2]
    other_call, other_text, other_context = calls[2]
    assert _ANCHOR not in other_context
    for index in (0, 1):
        call_index, _, context = calls[index]
        assert call_index > other_call  # translated after msgstr[2]
        # msgstr[2]'s translation, placeholders as tokens, is quoted.
        assert f"{_ANCHOR}RU {other_text}'" in context, context

    data = po_handler.read_po_file(str(tmp_path / "locale" / "ru" / "LC_MESSAGES" / "django.po"))
    assert data["One file::msgstr[2]"] == "RU %(counter)s files"
    assert data["Hello"] == "RU Hello"


def test_po_damaged_other_is_not_quoted(tmp_path):
    from algebras.utils.ios_stringsdict_handler import anchor_plural_contexts

    source = tmp_path / "en.po"
    source.write_text(SOURCE_PO, encoding="utf-8")
    contexts = po_handler.build_plural_contexts(str(source), "en", "ru")
    keys = [po_handler.plural_key("One file", i) for i in (0, 1)]
    src = {po_handler.plural_key("One file", 2): "%(counter)s files"}
    damaged = anchor_plural_contexts(contexts, keys, {po_handler.plural_key("One file", 2): "файлов"}, src)
    assert all(_ANCHOR not in damaged[k] for k in keys)
    good = anchor_plural_contexts(contexts, keys, {po_handler.plural_key("One file", 2): "%(counter)s файлов"}, src)
    assert all(f"{_ANCHOR}%(counter)s файлов'" in good[k] for k in keys)


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------

RAILS_EN = """\
en:
  greeting: "Hello, %{name}!"
  inbox:
    messages:
      one: "One message"
      other: "%{count} messages"
    title: Inbox
"""


def _yaml_project(tmp_path, monkeypatch):
    source = tmp_path / "config" / "locales" / "en.yml"
    source.parent.mkdir(parents=True)
    source.write_text(RAILS_EN, encoding="utf-8")
    _config(
        tmp_path, monkeypatch, "config/locales/en.yml",
        "config/locales/%algebras_locale_code%.yml", ["en", "ru"],
    )
    return tmp_path / "config" / "locales" / "ru.yml"


def _plural_calls(sent):
    """{form: (call index, text, context)} for the Rails plural forms sent."""
    calls = {}
    for call_index, (texts, contexts) in enumerate(sent):
        for text, context in zip(texts, contexts):
            m = re.match(r"Plural form '(\w+)' for Russian", context or "")
            if m:
                calls[m.group(1)] = (call_index, text, context)
    return calls


def _assert_anchored(sent):
    calls = _plural_calls(sent)
    assert {"few", "many", "other"} <= set(calls)
    other_call, other_text, other_context = calls["other"]
    assert _ANCHOR not in other_context
    for form in ("few", "many"):
        call_index, _, context = calls[form]
        assert call_index > other_call
        assert f"{_ANCHOR}RU {other_text}'" in context, (form, context)


def test_yaml_full_file_second_pass_quotes_translated_other(tmp_path, monkeypatch):
    target = _yaml_project(tmp_path, monkeypatch)
    used = []
    original = Translator.translate_file

    def spy(self, *args, **kwargs):
        used.append(args[0])
        return original(self, *args, **kwargs)

    sent = []
    with patch.object(Translator, "translate_file", spy):
        _translate(sent, force="__all__")
    assert used, "the full-file path was not taken"
    _assert_anchored(sent)

    data = yaml.safe_load(target.read_text(encoding="utf-8"))["ru"]
    assert list(data["inbox"]["messages"]) == ["one", "few", "many", "other"]  # source order kept
    assert data["inbox"]["messages"]["other"] == "RU %{count} messages"
    assert data["greeting"] == "RU Hello, %{name}!"
    assert data["inbox"]["title"] == "RU Inbox"


def test_yaml_missing_only_second_pass_quotes_translated_other(tmp_path, monkeypatch):
    target = _yaml_project(tmp_path, monkeypatch)
    target.write_text("ru:\n  greeting: 'Привет, %{name}!'\n", encoding="utf-8")
    sent = []
    _translate(sent, only_missing=True)
    _assert_anchored(sent)

    data = yaml.safe_load(target.read_text(encoding="utf-8"))["ru"]
    assert data["greeting"] == "Привет, %{name}!"
    assert sorted(data["inbox"]["messages"]) == ["few", "many", "one", "other"]


# ---------------------------------------------------------------------------
# Placeholder retries
# ---------------------------------------------------------------------------


class _Client:
    """Fake AlgebrasAIClient recording every call (texts, contexts, per-call ignore_cache)."""

    def __init__(self, answer):
        self.answer = answer
        self.ignore_cache = False
        self.calls = []
        self.config = MagicMock()
        self._lock = threading.Lock()

    def translate_batch(self, texts, source_lang, target_lang, ui_safe=False, glossary_id="", contexts=None,
                        ignore_cache=None):
        with self._lock:
            self.calls.append((list(texts), list(contexts or []), ignore_cache))
            attempt = len(self.calls)
        return [self.answer(t, attempt, len(texts)) for t in texts]


def _processor(client, **kwargs):
    kwargs.setdefault("batch_size", 10)
    return BatchProcessor(client, max_parallel_batches=4, provider="algebras-ai", **kwargs)


def _drop_token_unless_alone(text, attempt, batch_len):
    return text if batch_len == 1 else text.replace("⟦0⟧", "")


def test_text_failing_twice_in_batch_passes_alone_and_is_accepted():
    client = _Client(_drop_token_unless_alone)
    result = _processor(client).process(["Hi %s", "Bye %s", "Plain"], "en", "ru", False, "")

    assert result.translations == ["Hi %s", "Bye %s", "Plain"]
    assert result.failed_indices == set()
    texts = [c[0] for c in client.calls]
    assert texts[0] == ["Hi ⟦0⟧", "Bye ⟦0⟧", "Plain"]
    assert texts[1] == ["Hi ⟦0⟧", "Bye ⟦0⟧"]  # batch retry
    assert sorted(texts[2:]) == [["Bye ⟦0⟧"], ["Hi ⟦0⟧"]]  # then each alone
    for _, contexts, ignore_cache in client.calls[1:]:
        assert contexts[0].startswith("IMPORTANT")
    assert [c[2] for c in client.calls[:2]] == [None, None]
    assert all(c[2] is True for c in client.calls[2:])  # cache bypassed only when alone
    assert (result.first_attempt_failures, result.retry_recovered) == (2, 2)


def test_text_that_always_fails_is_reported_after_exactly_three_attempts():
    client = _Client(lambda t, attempt, n: t.replace("⟦0⟧", "%с"))
    result = _processor(client).process(["Hi %s", "Plain"], "en", "ru", False, "")

    assert result.failed_indices == {0}
    assert result.translations == ["", "Plain"]
    attempts = [c for c in client.calls if "Hi ⟦0⟧" in c[0]]
    assert len(attempts) == 3
    assert (result.first_attempt_failures, result.retry_recovered) == (1, 0)


def test_cache_bypass_never_leaks_to_the_client_or_later_calls():
    client = _Client(_drop_token_unless_alone)
    processor = _processor(client, batch_size=1)
    processor.process(["A %s", "B %s", "C %s", "D"], "en", "ru", False, "")
    assert client.ignore_cache is False  # the shared flag is never touched

    client.calls.clear()
    processor.process(["Plain", "Other"], "en", "ru", False, "")
    assert [c[2] for c in client.calls] == [None, None]


def test_api_client_per_call_ignore_cache_does_not_change_client_setting(monkeypatch):
    from algebras.services.api_client import AlgebrasAIClient

    config = MagicMock()
    config.get_base_url.return_value = "https://api.example"
    client = AlgebrasAIClient(config, MagicMock(), sync_batch=True)
    sent = []

    def execute(call):
        return call()

    client._retry_handler.execute_with_retry.side_effect = execute
    response = MagicMock(status_code=200)
    response.json.return_value = {"data": {"translations": [{"index": 0, "content": "x"}]}}
    monkeypatch.setenv("ALGEBRAS_API_KEY", "test")
    monkeypatch.setattr(
        "algebras.services.api_client.requests.post",
        lambda url, headers, json: sent.append(json["ignoreCache"]) or response,
    )
    client.translate_batch(["a"], "en", "ru", ignore_cache=True)
    client.translate_batch(["a"], "en", "ru")
    assert sent == [True, False]
    assert client.ignore_cache is False


def test_zero_retries_disables_retrying():
    client = _Client(_drop_token_unless_alone)
    result = _processor(client, placeholder_retries=0).process(["Hi %s", "Plain"], "en", "ru", False, "")
    assert len(client.calls) == 1
    assert result.failed_indices == {0}
    assert (result.first_attempt_failures, result.retry_recovered) == (1, 0)


def test_retries_come_from_config_api_placeholder_retries():
    client = _Client(_drop_token_unless_alone)
    client.config.get_api_config.return_value = {"placeholder_retries": 0}
    assert _processor(client).placeholder_retries == 0
    client.config.get_api_config.return_value = {"placeholder_retries": "1"}
    assert _processor(client).placeholder_retries == 1
    client.config.get_api_config.return_value = {}
    assert _processor(client).placeholder_retries == 2


def test_one_retry_only_retries_in_batch():
    client = _Client(_drop_token_unless_alone)
    result = _processor(client, placeholder_retries=1).process(["Hi %s", "Bye %s"], "en", "ru", False, "")
    assert [(len(c[0]), c[2]) for c in client.calls] == [(2, None), (2, None)]  # no alone retry
    assert result.failed_indices == {0, 1}


def test_counters_and_verbose_summary(capsys):
    def answer(text, attempt, n):
        if "B" in text:
            return text.replace("⟦0⟧", "")  # never recovers
        if "A" in text and attempt == 1:
            return text.replace("⟦0⟧", "")  # recovers on the batch retry
        return text

    client = _Client(answer)
    result = _processor(client, verbose=True).process(["A %s", "B %s", "C %s", "Plain"], "en", "ru", False, "")
    assert result.first_attempt_failures == 2
    assert result.retry_recovered == 1
    assert result.failed_indices == {1}
    out = capsys.readouterr().out
    assert "2/4 passed on the first attempt, 3/4 after retries (1 recovered)" in out
    assert out.count("lost or changed placeholders") == 1  # one summary line, not one per retry
