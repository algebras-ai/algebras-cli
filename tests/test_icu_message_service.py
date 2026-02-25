from unittest.mock import MagicMock

from algebras.services.batch_processor import BatchProcessor
from algebras.services.icu_message_service import ICUMessageService
from algebras.services.translator import Translator


def _mock_config():
    config = MagicMock()
    config.exists.return_value = True
    config.load.return_value = {}
    config.get_api_config.return_value = {"provider": "algebras-ai"}
    config.get_setting.return_value = ""
    config.has_setting.return_value = False
    config.get_source_language.return_value = "en"
    config.get_languages.return_value = ["en", "fr"]
    config.get_base_url.return_value = "https://platform.algebras.ai"
    return config


def test_icu_service_detect_prepare_rebuild_roundtrip():
    service = ICUMessageService()
    message = (
        "{count, plural, one {# course available} few {# courses available} "
        "other {# courses available}}"
    )

    assert service.is_icu(message) is True
    prepared = service.prepare(message)
    assert prepared.has_target_icu is True
    assert "course available" in prepared.translatable_segments
    assert "courses available" in prepared.translatable_segments

    translated = [
        seg.replace("course available", "curso disponible").replace(
            "courses available", "cursos disponibles"
        )
        for seg in prepared.translatable_segments
    ]
    rebuilt = service.rebuild(prepared, translated)
    assert service.validate(rebuilt) is True
    assert "plural" in rebuilt
    assert "one {# curso disponible}" in rebuilt
    assert "other {" in rebuilt


def test_icu_service_validation_failure_keeps_raw_with_warning(capsys):
    service = ICUMessageService()
    message = "{gender, select, male {He} female {She} other {They}}"
    flattened, mapping = service.preprocess_texts([message])

    # Invalid rebuild payload: unbalanced brace in translated literal.
    rebuilt = service.postprocess_translations(mapping, ["He}", "She", "They"])
    captured = capsys.readouterr()

    assert len(flattened) == 3
    assert "ICU validation failed" in captured.out
    # Raw translated output is kept even when invalid.
    assert rebuilt[0].startswith("{gender, select,")


def test_batch_processor_rebuilds_icu_messages():
    class FakeApiClient:
        def translate_batch(self, texts, *_args, **_kwargs):
            return [f"{text} [tr]" for text in texts]

    processor = BatchProcessor(
        api_client=FakeApiClient(),
        batch_size=10,
        max_parallel_batches=2,
        provider="algebras-ai",
        verbose=False,
    )

    source = "{count, plural, one {# item} other {# items}}"
    result = processor.process(
        texts=[source, "Plain text"],
        source_lang="en",
        target_lang="fr",
        ui_safe=False,
        glossary_id="",
    )

    assert len(result.translations) == 2
    assert "one {# item [tr]}" in result.translations[0]
    assert "other {# items [tr]}" in result.translations[0]
    assert result.translations[1] == "Plain text [tr]"


def test_translator_translate_text_handles_icu_plural(monkeypatch):
    config = _mock_config()
    cache = MagicMock()
    cache.get.return_value = None
    cache.get_cache_key.return_value = "cache-key"

    monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: cache)

    translator = Translator(config=config)

    def fake_translate(text, *_args, **_kwargs):
        return text.replace("item", "élément").replace("items", "éléments")

    translator.api_client.translate = fake_translate

    message = "{count, plural, one {# item} other {# items}}"
    translated = translator.translate_text(message, "en", "fr")

    assert "one {# élément}" in translated
    assert "other {# éléments}" in translated
    assert cache.set.called


def test_icu_service_preserves_whitespace_around_hash():
    service = ICUMessageService()
    message = "{count, plural, one {# course} other {# courses}}"

    prepared = service.prepare(message)
    rebuilt = service.rebuild(prepared, ["kurs", "kurslar"])

    assert "{# kurs}" in rebuilt
    assert "{#kurs}" not in rebuilt
    assert service.validate(rebuilt) is True


def test_icu_service_skips_selectordinal_suffix_translation():
    service = ICUMessageService()
    message = "{position, selectordinal, one {You finished #st} other {You finished #th}}"

    prepared = service.prepare(message)
    # Only sentence parts should be translated; suffix literals are skipped.
    assert prepared.translatable_segments == ["You finished", "You finished"]

    rebuilt = service.rebuild(prepared, ["Bitirdin", "Bitirdin"])
    assert "{position, selectordinal," in rebuilt
    assert "#st" in rebuilt
    assert "#th" in rebuilt
