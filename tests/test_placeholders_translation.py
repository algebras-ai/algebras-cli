"""
Placeholders survive translation: masking in BatchProcessor, retry, rejection, and the
Translator/strategies never writing a value whose placeholders were damaged.
"""

import re
from unittest.mock import MagicMock

from algebras.services.batch_processor import BatchProcessor, BatchResult
from algebras.services.strategies.flat_dict_strategy import FlatDictTranslationStrategy
from algebras.utils.ios_stringsdict_handler import anchor_plural_contexts

_LATIN_TO_CYRILLIC = str.maketrans(
    dict(zip("sdcSDabeiklmnoprtuvxyz", "сдсСДабеиклмнопртувхйз"))
)


def transliterate(text: str) -> str:
    """What the model did for uz-Cyrl: every Latin letter becomes Cyrillic."""
    return text.translate(_LATIN_TO_CYRILLIC)


def make_processor(translate_batch, provider="algebras-ai", batch_size=10):
    api_client = MagicMock()
    api_client.translate_batch.side_effect = translate_batch
    return BatchProcessor(api_client, batch_size=batch_size, max_parallel_batches=1, provider=provider), api_client


def test_transliterating_model_cannot_damage_placeholders():
    processor, api = make_processor(lambda texts, *a, **k: [transliterate(t) for t in texts])
    texts = [
        "We sent a code to %1$s. Resend in %2$d s",
        "%1$d of %2$d questions left",
        'Hello <xliff:g id="n">%1$s</xliff:g>!',
        "Hi {{name}}, {count} new",
    ]
    result = processor.process(texts, "en", "uz-Cyrl", False, "")

    assert result.failed_indices == set()
    assert result.translations[0].count("%1$s") == 1 and result.translations[0].count("%2$d") == 1
    assert "%1$d" in result.translations[1] and "%2$d" in result.translations[1]
    assert '<xliff:g id="n">%1$s</xliff:g>' in result.translations[2]
    assert "{{name}}" in result.translations[3] and "{count}" in result.translations[3]
    # The model only ever saw tokens.
    sent = api.translate_batch.call_args_list[0].args[0]
    assert sent[0] == "We sent a code to ⟦0⟧. Resend in ⟦1⟧ s"
    assert not any("%" in t for t in sent)


def test_each_masked_text_gets_a_context_listing_its_tokens():
    processor, api = make_processor(lambda texts, *a, **k: list(texts))
    processor.process(["Hi %s", "Plain", "%d of %d"], "en", "ru", False, "", contexts=[None, "note", None])

    contexts = api.translate_batch.call_args_list[0].kwargs["contexts"]
    assert "⟦0⟧" in contexts[0] and "transliterate" in contexts[0]
    assert contexts[1] == "note"
    assert "⟦0⟧, ⟦1⟧" in contexts[2]


def test_existing_context_is_rewritten_to_tokens():
    processor, api = make_processor(lambda texts, *a, **k: list(texts))
    processor.process(["%d items"], "en", "ru", False, "", contexts=["Source forms: other: '%d items'."])
    context = api.translate_batch.call_args_list[0].kwargs["contexts"][0]
    assert context.startswith("Source forms: other: '⟦0⟧ items'.")


def test_lost_token_is_retried_once_then_accepted():
    calls = []

    def translate(texts, *a, **k):
        calls.append(list(texts))
        if len(calls) == 1:
            return [t.replace("⟦0⟧", "") for t in texts]  # first answer loses the token
        return list(texts)

    processor, _ = make_processor(translate)
    result = processor.process(["Hi %s", "Plain"], "en", "ru", False, "")

    assert result.translations == ["Hi %s", "Plain"]
    assert result.failed_indices == set()
    assert calls[1] == ["Hi ⟦0⟧"]  # only the failed text is retried


def test_text_that_keeps_losing_tokens_is_rejected_not_returned_damaged():
    processor, api = make_processor(lambda texts, *a, **k: [t.replace("⟦0⟧", "%с") for t in texts])
    result = processor.process(["Hi %s", "Plain"], "en", "uz", False, "")

    assert result.failed_indices == {0}
    assert result.translations[0] == ""
    assert result.translations[1] == "Plain"
    assert api.translate_batch.call_count == 2
    retry_context = api.translate_batch.call_args_list[1].kwargs["contexts"][0]
    assert retry_context.startswith("IMPORTANT")


def test_drop_allowed_lets_single_count_form_omit_count():
    processor, _ = make_processor(lambda texts, *a, **k: ["Ein Element" for _ in texts])
    result = processor.process(["%d item"], "en", "de", False, "", drop_allowed=[frozenset({"%d"})])
    assert result.failed_indices == set()
    assert result.translations == ["Ein Element"]


def test_icu_message_segments_are_masked_and_failure_maps_to_message():
    def translate(texts, *a, **k):
        return [t.replace("⟦0⟧", "") for t in texts]  # drop every token, always

    processor, _ = make_processor(translate)
    result = processor.process(
        ["{count, plural, one {# item for %s} other {# items for %s}}", "Plain"], "en", "ru", False, ""
    )
    assert result.failed_indices == {0}
    assert result.translations[0] == ""
    assert result.translations[1] == "Plain"


def test_other_provider_path_is_protected_too():
    translate_text = MagicMock(side_effect=lambda text, *a: transliterate(text))
    processor = BatchProcessor(MagicMock(), batch_size=5, max_parallel_batches=1, provider="openai")
    result = processor.process(["Sent to %1$s"], "en", "uz", False, "", translate_text_func=translate_text)
    assert "%1$s" in result.translations[0]
    assert result.failed_indices == set()


def test_batch_result_failed_indices_defaults_to_empty():
    result = BatchResult(translations=[], error_stats={}, failed_batches=[], successful_batches=0, total_batches=0)
    assert result.failed_indices == set()


def test_flat_strategy_skips_rejected_translations():
    batch_processor = MagicMock()
    batch_processor.process.return_value = BatchResult(
        translations=["", "Привет"],
        error_stats={"5xx": [], "429": [], "other": []},
        failed_batches=[],
        successful_batches=1,
        total_batches=1,
        failed_indices={0},
    )
    normalizer = MagicMock()
    normalizer.normalize.side_effect = lambda s, t: t
    strategy = FlatDictTranslationStrategy(MagicMock(), batch_processor, normalizer, 10, {})
    out = strategy.translate({"a": "Hi %s", "b": "Hello"}, "en", "ru", False, "g", None, None)
    assert out == {"b": "Привет"}


def test_anchor_skips_damaged_other_translation():
    contexts = {"k.one": "ctx-one", "k.few": "ctx-few"}
    translated = {"k.other": "%д очко"}
    source = {"k.other": "%d points"}
    anchored = anchor_plural_contexts(contexts, ["k.one", "k.few"], translated, source)
    assert anchored == contexts

    good = anchor_plural_contexts(contexts, ["k.few"], {"k.other": "%d очков"}, source)
    assert "already translated as '%d очков'" in good["k.few"]
