"""
Translation strategy for nested dictionaries.
"""

from typing import Dict, Any, Optional, Callable

from algebras.services.strategies.base import TranslationStrategy


# Marks a value that is left out of the target: its placeholders were rejected, or its API batch failed.
_LEFT_OUT = object()


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
        placeholder_profile=None,
        contexts: Optional[Dict[str, str]] = None,
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
            contexts: Optional translator notes by dotted key path (plural forms). Those keys
                also get the single-count plural exemption for their count placeholder.

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

        extra_kwargs: Dict[str, Any] = {}
        if contexts:
            from algebras.services.placeholders import GENERIC_PROFILE
            from algebras.services.placeholders.plurals import drop_allowed_for_key

            dotted = [".".join(str(k) for k in path) for path in paths]
            aligned = [contexts.get(key) for key in dotted]
            if any(aligned):
                extra_kwargs["contexts"] = aligned
                extra_kwargs["drop_allowed"] = [
                    drop_allowed_for_key(key, text, target_lang, placeholder_profile or GENERIC_PROFILE)
                    if key in contexts
                    else frozenset()
                    for key, text in zip(dotted, string_items)
                ]

        # Process batches
        result = self.batch_processor.process(
            texts=string_items,
            source_lang=source_lang,
            target_lang=target_lang,
            ui_safe=ui_safe,
            glossary_id=glossary_id,
            on_batch_complete=None,  # We'll handle callback after mapping to paths
            translate_text_func=translate_text_func,
            **({"placeholder_profile": placeholder_profile} if placeholder_profile is not None else {}),
            **extra_kwargs,
        )

        # Map translations back to paths and apply normalization
        # Also handle callbacks and track failed translations
        num_batches = (len(string_items) + self.batch_size - 1) // self.batch_size

        # Build set of failed indices from failed batches
        failed_indices = set()
        for batch_idx in result.failed_batches:
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(batch_start_idx + self.batch_size, len(string_items))
            for idx in range(batch_start_idx, batch_end_idx):
                failed_indices.add(idx)
        # Translations rejected because their placeholders did not survive
        failed_indices |= result.failed_indices

        for i, (source_text, path) in enumerate(zip(string_items, paths)):
            if i < len(result.translations):
                raw_translation = result.translations[i]
                path_key = tuple(path)

                if i in failed_indices:
                    # Placeholders did not survive translation, or the API batch failed: leave
                    # the key out of the target so 'status' reports it and the next run retries it.
                    translated_values[path_key] = _LEFT_OUT
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
                        if translation is not None and translation is not _LEFT_OUT:
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
            print(f"    Keys from failed batches are left out and will be retried on the next run")

        # Build the result dictionary with translations
        result_dict = {}
        left_out_count = 0

        def build_result(src_data, dest_data, current_path=None):
            nonlocal left_out_count
            if current_path is None:
                current_path = []

            for key, value in src_data.items():
                path = current_path + [key]
                if isinstance(value, dict):
                    created = key not in dest_data
                    if created:
                        dest_data[key] = {}
                    build_result(value, dest_data[key], path)
                    if created and value and not dest_data[key]:
                        del dest_data[key]  # every value inside was left out
                elif isinstance(value, str):
                    translated_value = translated_values.get(tuple(path), _LEFT_OUT)
                    if translated_value is _LEFT_OUT:
                        left_out_count += 1
                    else:
                        dest_data[key] = translated_value
                else:
                    dest_data[key] = value

        # Build the translated dictionary
        build_result(data, result_dict)

        if left_out_count > 0:
            print(
                f"  ⚠ {left_out_count} keys were left out (placeholders lost or damaged, or the API "
                "batch failed); they will be retried on the next run"
            )

        return result_dict
