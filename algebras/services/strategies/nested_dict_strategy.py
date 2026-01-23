"""
Translation strategy for nested dictionaries.
"""

from typing import Dict, Any, Optional, Callable

from algebras.services.strategies.base import TranslationStrategy


class NestedDictTranslationStrategy(TranslationStrategy):
    """Strategy for translating nested dictionaries."""

    def translate(
        self,
        data: Dict[str, Any],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
    ) -> Dict[str, Any]:
        """
        Recursively translate a nested dictionary.

        Args:
            data: Dictionary to translate
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

        # Collect all string values that need translation, filter empty strings
        string_items = []
        paths = []
        empty_paths = []  # Track paths with empty strings

        def collect_strings(current_data, current_path=None):
            if current_path is None:
                current_path = []

            for key, value in current_data.items():
                path = current_path + [key]
                if isinstance(value, dict):
                    collect_strings(value, path)
                elif isinstance(value, str):
                    # Filter empty strings - preserve them but don't send to API
                    if value.strip() == "":
                        empty_paths.append(path)
                    else:
                        string_items.append(value)
                        paths.append(path)

        # Collect all strings that need translation
        collect_strings(data)

        # Initialize translated_values with empty strings
        translated_values = {}
        for empty_path in empty_paths:
            path_key = tuple(empty_path)
            translated_values[path_key] = ""  # Preserve empty string

        # If all strings are empty, return early
        if not string_items:
            # Build result with empty strings only
            result = {}

            def build_result(src_data, dest_data, current_path=None):
                if current_path is None:
                    current_path = []
                for key, value in src_data.items():
                    path = current_path + [key]
                    if isinstance(value, dict):
                        if key not in dest_data:
                            dest_data[key] = {}
                        build_result(value, dest_data[key], path)
                    elif isinstance(value, str):
                        path_key = tuple(path)
                        if path_key in translated_values:
                            dest_data[key] = translated_values[path_key]
                        else:
                            dest_data[key] = value
                    else:
                        dest_data[key] = value

            build_result(data, result)
            return result

        # Process batches
        result = self.batch_processor.process(
            texts=string_items,
            source_lang=source_lang,
            target_lang=target_lang,
            ui_safe=ui_safe,
            glossary_id=glossary_id,
            on_batch_complete=None,  # We'll handle callback after mapping to paths
            translate_text_func=translate_text_func,
        )

        # Map translations back to paths and apply normalization
        # Also handle callbacks and track failed translations
        num_batches = (len(string_items) + self.batch_size - 1) // self.batch_size
        failed_keys_count = 0

        # Build set of failed indices from failed batches
        failed_indices = set()
        for batch_idx in result.failed_batches:
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(batch_start_idx + self.batch_size, len(string_items))
            for idx in range(batch_start_idx, batch_end_idx):
                failed_indices.add(idx)

        for i, (source_text, path) in enumerate(zip(string_items, paths)):
            if i < len(result.translations):
                raw_translation = result.translations[i]
                path_key = tuple(path)

                # Check if this translation failed
                if i in failed_indices:
                    # Mark as failed - will use source value in build_result
                    translated_values[path_key] = None
                    failed_keys_count += 1
                else:
                    # Apply normalization
                    normalized = self.string_normalizer.normalize(
                        source_text, raw_translation
                    )
                    translated_values[path_key] = normalized

        # Handle callbacks after mapping to paths
        for batch_idx in range(1, num_batches + 1):
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(batch_start_idx + self.batch_size, len(string_items))

            batch_dict = {}
            for i in range(batch_start_idx, batch_end_idx):
                if i < len(paths):
                    path = paths[i]
                    path_key = tuple(path)
                    if path_key in translated_values:
                        path_str = ".".join(str(p) for p in path)
                        translation = translated_values[path_key]
                        if translation is not None:
                            batch_dict[path_str] = translation

            # Call callback if provided
            if on_batch_complete and batch_dict:
                try:
                    on_batch_complete(batch_dict, batch_idx)
                except Exception as e:
                    print(f"  ⚠ Error in batch complete callback: {str(e)}")

        # Print summary if there were failures
        if result.failed_batches:
            print(f"\n  Summary:")
            print(f"    Total batches: {result.total_batches}")
            print(
                f"    Successful: {result.successful_batches} ({result.successful_batches / result.total_batches * 100:.1f}%)"
            )
            print(
                f"    Failed: {len(result.failed_batches)} ({len(result.failed_batches) / result.total_batches * 100:.1f}%)"
            )
            if result.error_stats["5xx"]:
                print(
                    f"      - 5xx errors: {len(result.error_stats['5xx'])} batches ({', '.join(map(str, result.error_stats['5xx']))})"
                )
            if result.error_stats["429"]:
                print(
                    f"      - 429 errors: {len(result.error_stats['429'])} batches ({', '.join(map(str, result.error_stats['429']))})"
                )
            if result.error_stats["other"]:
                print(
                    f"      - Other errors: {len(result.error_stats['other'])} batches ({', '.join(map(str, result.error_stats['other']))})"
                )
            print(f"    Failed batches will use source language values")

        # Build the result dictionary with translations
        result_dict = {}
        failed_keys_count = 0

        def build_result(src_data, dest_data, current_path=None):
            nonlocal failed_keys_count
            if current_path is None:
                current_path = []

            for key, value in src_data.items():
                path = current_path + [key]
                if isinstance(value, dict):
                    if key not in dest_data:
                        dest_data[key] = {}
                    build_result(value, dest_data[key], path)
                elif isinstance(value, str):
                    path_key = tuple(path)
                    if path_key in translated_values:
                        translated_value = translated_values[path_key]
                        if translated_value is None:
                            # Failed translation - use source value
                            dest_data[key] = value
                            failed_keys_count += 1
                        else:
                            dest_data[key] = translated_value
                    else:
                        # Not translated (shouldn't happen, but use source value as fallback)
                        dest_data[key] = value
                        failed_keys_count += 1
                else:
                    dest_data[key] = value

        # Build the translated dictionary
        build_result(data, result_dict)

        if failed_keys_count > 0:
            print(
                f"  ⚠ {failed_keys_count} keys were not translated and will use source language values"
            )

        return result_dict
