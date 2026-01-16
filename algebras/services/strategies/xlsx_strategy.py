"""
Translation strategy for XLSX files.
"""

from typing import Dict, Any, Optional, Callable

from algebras.services.strategies.base import TranslationStrategy
from algebras.services.strategies.flat_dict_strategy import FlatDictTranslationStrategy


class XlsxTranslationStrategy(TranslationStrategy):
    """Strategy for translating XLSX content."""

    def __init__(
        self,
        config,
        batch_processor,
        string_normalizer,
        batch_size: int,
        api_config: Dict[str, Any],
    ):
        """
        Initialize XLSX translation strategy.

        Args:
            config: Config instance
            batch_processor: BatchProcessor instance
            string_normalizer: StringNormalizer instance
            batch_size: Batch size
            api_config: API configuration
        """
        super().__init__(
            config, batch_processor, string_normalizer, batch_size, api_config
        )
        # Create flat dict strategy for translating strings
        self._flat_strategy = FlatDictTranslationStrategy(
            config, batch_processor, string_normalizer, batch_size, api_config
        )

    def translate(
        self,
        xlsx_content: Dict[str, Any],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
    ) -> Dict[str, Any]:
        """
        Translate XLSX content for a specific target language.

        Args:
            xlsx_content: XLSX content dictionary
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation
            on_batch_complete: Optional callback function (not used for XLSX, but kept for interface compatibility)

        Returns:
            Updated XLSX content with translated strings
        """
        if "translations" not in xlsx_content:
            return xlsx_content

        # Extract source language strings
        source_strings = {}
        for key, lang_translations in xlsx_content["translations"].items():
            if isinstance(lang_translations, dict) and source_lang in lang_translations:
                source_strings[key] = lang_translations[source_lang]

        # Translate the strings using flat dict strategy
        translated_strings = self._flat_strategy.translate(
            source_strings, source_lang, target_lang, ui_safe, glossary_id, None, translate_text_func
        )

        # Update the XLSX content
        updated_content = xlsx_content.copy()
        for key, translated_value in translated_strings.items():
            if key in updated_content["translations"]:
                if target_lang not in updated_content["translations"][key]:
                    updated_content["translations"][key] = updated_content[
                        "translations"
                    ][key].copy()
                updated_content["translations"][key][target_lang] = translated_value

        return updated_content
