"""
Translation strategy for CSV files.
"""

from typing import Dict, Any, Optional, Callable, List

from algebras.services.strategies.base import TranslationStrategy
from algebras.services.strategies.flat_dict_strategy import FlatDictTranslationStrategy


class CsvTranslationStrategy(TranslationStrategy):
    """Strategy for translating CSV content."""

    def __init__(
        self,
        config,
        batch_processor,
        string_normalizer,
        batch_size: int,
        api_config: Dict[str, Any],
    ):
        """
        Initialize CSV translation strategy.

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

    def _column(self, languages: List[str], language: str, default: Optional[str] = None) -> Optional[str]:
        """The header of `language`'s column: locale mapping, then exact or "(code)" match."""
        from algebras.utils.csv_handler import _find_matching_column

        mapped = language
        try:
            mapped = self.config.get_destination_locale_code(language)
        except Exception:
            pass
        return _find_matching_column(languages, mapped) or _find_matching_column(languages, language) or default

    def translate(
        self,
        csv_content: Dict[str, Any],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
        placeholder_profile=None,
    ) -> Dict[str, Any]:
        """
        Translate CSV content for a specific target language.

        Args:
            csv_content: CSV content dictionary
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation
            on_batch_complete: Optional callback function (not used for CSV, but kept for interface compatibility)
            placeholder_profile: Placeholder syntaxes to protect (the file's detected profile)

        Returns:
            Updated CSV content with translated strings. "target_column" is the header the
            translations were put under, and "translated_keys" lists the rows whose
            target cell was translated; a cell whose placeholders did not survive translation
            (even after the retry) is not in it and keeps its previous value (empty if it had none).
        """
        if "translations" not in csv_content:
            return csv_content

        languages = list(csv_content.get("languages", []))
        source_column = self._column(languages, source_lang, source_lang)
        target_column = self._column(languages, target_lang, target_lang)

        # Extract source language strings
        source_strings = {}
        for key, lang_translations in csv_content["translations"].items():
            if isinstance(lang_translations, dict) and source_column in lang_translations:
                source_strings[key] = lang_translations[source_column]

        # Translate the strings using flat dict strategy. Each cell is masked once for this
        # language; cells rejected by the placeholder check are left out of the result.
        translated_strings = self._flat_strategy.translate(
            source_strings,
            source_lang,
            target_lang,
            ui_safe,
            glossary_id,
            None,
            translate_text_func,
            placeholder_profile=placeholder_profile,
        )

        # Gate per cell before anything is written: the batch processor already rejects texts
        # whose tokens did not survive, and this also catches a placeholder the model invented
        # or one damaged by normalization.
        from algebras.services.placeholders import GENERIC_PROFILE, verify

        profile = placeholder_profile or GENERIC_PROFILE
        for key in list(translated_strings):
            source_text = source_strings.get(key, "")
            if source_text.strip() and verify(source_text, translated_strings[key], profile):
                del translated_strings[key]

        rejected = [k for k, v in source_strings.items() if v.strip() and k not in translated_strings]
        for key in rejected:
            print(
                f"  ✗ Row '{key}', column '{target_column}': placeholders were lost or damaged; "
                "cell not written"
            )

        # Update the CSV content
        updated_content = csv_content.copy()
        updated_content["translations"] = dict(csv_content["translations"])
        if target_column not in languages:
            updated_content["languages"] = languages + [target_column]
        for key, translated_value in translated_strings.items():
            if key in updated_content["translations"]:
                row = dict(updated_content["translations"][key])
                row[target_column] = translated_value
                updated_content["translations"][key] = row
        # Empty source cells are not translated, so an existing target value is not erased.
        updated_content["translated_keys"] = [
            k for k in translated_strings if k in source_strings and source_strings[k].strip()
        ]
        updated_content["rejected_keys"] = rejected
        updated_content["target_column"] = target_column

        return updated_content
