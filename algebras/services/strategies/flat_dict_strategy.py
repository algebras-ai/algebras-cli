"""
Translation strategy for flat dictionaries (key-value pairs where values are strings).
"""

from typing import Dict, Any, Optional, Callable

from algebras.services.strategies.base import TranslationStrategy


class FlatDictTranslationStrategy(TranslationStrategy):
    """Strategy for translating flat dictionaries."""

    def translate(
        self,
        data: Dict[str, str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
    ) -> Dict[str, str]:
        """
        Translate a flat dictionary (key-value pairs where values are strings).

        Args:
            data: Dictionary to translate (flat, string values only)
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            on_batch_complete: Optional callback function called after each batch completes

        Returns:
            Translated dictionary
        """
        # Resolve glossary_id from config if not provided
        glossary_id = self._resolve_glossary_id(glossary_id)

        # Get string items and keys, filter out empty strings
        string_items = list(data.values())
        keys = list(data.keys())

        # Filter empty strings and maintain mapping
        non_empty_items = []
        non_empty_keys = []
        empty_key_mapping = {}  # Map empty keys to empty string

        for key, value in zip(keys, string_items):
            if isinstance(value, str) and value.strip() == "":
                empty_key_mapping[key] = ""  # Preserve empty string
            else:
                non_empty_items.append(value)
                non_empty_keys.append(key)

        # Initialize result with empty strings
        translated_values = empty_key_mapping.copy()

        # If all strings are empty, return early
        if not non_empty_items:
            return translated_values

        # Process batches
        result = self.batch_processor.process(
            texts=non_empty_items,
            source_lang=source_lang,
            target_lang=target_lang,
            ui_safe=ui_safe,
            glossary_id=glossary_id,
            on_batch_complete=None,  # We'll handle callback after mapping to keys
            translate_text_func=translate_text_func,
        )

        # Apply normalization to each translation and map back to keys
        # Also handle callbacks after mapping results to keys
        num_batches = (len(non_empty_items) + self.batch_size - 1) // self.batch_size
        for batch_idx in range(1, num_batches + 1):
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(batch_start_idx + self.batch_size, len(non_empty_items))

            batch_dict = {}
            for i in range(batch_start_idx, batch_end_idx):
                if i < len(result.translations):
                    key = non_empty_keys[i]
                    source_text = non_empty_items[i]
                    raw_translation = result.translations[i]
                    # Apply normalization
                    normalized = self.string_normalizer.normalize(
                        source_text, raw_translation
                    )
                    translated_values[key] = normalized
                    batch_dict[key] = normalized

            # Call callback if provided
            if on_batch_complete and batch_dict:
                try:
                    on_batch_complete(batch_dict, batch_idx)
                except Exception as e:
                    print(f"  ⚠ Error in batch complete callback: {str(e)}")

        return translated_values
