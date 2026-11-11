"""
Batch processor for translation operations.
Handles batch splitting, parallel processing, and error handling.
"""

import concurrent.futures
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, FrozenSet, Set

from algebras.services.api_client import AlgebrasAIClient
from algebras.services.icu_message_service import ICUMessageService
from algebras.utils.lang_validator import api_language_code
from algebras.services.placeholders import (
    GENERIC_PROFILE,
    PlaceholderError,
    PlaceholderProfile,
    combine_context,
    mask,
    unmask,
)

_RETRY_NOTE = (
    "IMPORTANT: a previous translation of this text lost or changed its placeholder tokens. "
    "Copy every token exactly."
)

# Default number of placeholder retries: once in a batch with the other failed texts, then once
# alone with the API cache bypassed. Config: api.placeholder_retries.
DEFAULT_PLACEHOLDER_RETRIES = 2


def _configured_placeholder_retries(api_client: Any) -> int:
    """api.placeholder_retries from the client's config, else DEFAULT_PLACEHOLDER_RETRIES."""
    try:
        value = api_client.config.get_api_config().get("placeholder_retries")
    except Exception:
        return DEFAULT_PLACEHOLDER_RETRIES
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return DEFAULT_PLACEHOLDER_RETRIES
    try:
        return max(0, int(value))
    except ValueError:
        return DEFAULT_PLACEHOLDER_RETRIES


# The platform's answer for a language code it does not support, e.g. 'Invalid language: pt-BR'.
_INVALID_LANGUAGE = re.compile(r"Invalid language(?:\s*code)?\s*:?\s*['\"]?([A-Za-z0-9_+-]*)")


@dataclass
class BatchResult:
    """Result of batch processing operation."""

    translations: List[str]  # List of translations in the same order as input texts
    error_stats: Dict[str, List[int]]  # {"5xx": [...], "429": [...], "other": [...]}
    failed_batches: List[int]  # Indices of failed batches
    successful_batches: int
    total_batches: int
    # Indices of input texts whose translation was rejected because placeholders were lost or
    # damaged (after the retries). Their entry in `translations` is "" and must not be written.
    failed_indices: Set[int] = field(default_factory=set)
    # Measurement: input texts whose first translation lost placeholders, and how many of those
    # a retry recovered (first-attempt vs after-retry success rate).
    first_attempt_failures: int = 0
    retry_recovered: int = 0
    # Positions of input texts whose API batch failed (their entry in `translations` is "").
    failed_positions: Set[int] = field(default_factory=set)


class BatchProcessor:
    """Processes translation batches with parallel execution and error handling."""

    def __init__(
        self,
        api_client: AlgebrasAIClient,
        batch_size: int,
        max_parallel_batches: int,
        provider: str,
        verbose: bool = False,
        placeholder_retries: Optional[int] = None,
    ):
        """
        Initialize BatchProcessor.

        Args:
            api_client: API client for batch translation
            batch_size: Size of each batch
            max_parallel_batches: Maximum number of parallel batches
            provider: Translation provider name (e.g., "algebras-ai")
            verbose: Whether to enable verbose logging
            placeholder_retries: How often a text whose placeholders did not survive is retried
                (None: config api.placeholder_retries, default 2; 0 disables retries)
        """
        self.api_client = api_client
        self.batch_size = batch_size
        self.max_parallel_batches = max_parallel_batches
        self.provider = provider
        self.verbose = verbose
        self.icu_service = ICUMessageService()
        if placeholder_retries is None:
            placeholder_retries = _configured_placeholder_retries(api_client)
        self.placeholder_retries = max(0, int(placeholder_retries))
        # Run totals: non-empty texts sent, and texts left out (placeholders rejected or API
        # batch failed). The translate command uses them for its summary and exit code.
        self.keys_sent = 0
        self.keys_left_out = 0

    def process(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool,
        glossary_id: str,
        on_batch_complete: Optional[
            Callable[[Dict[str, str], int], None]
        ] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
        contexts: Optional[List[Optional[str]]] = None,
        placeholder_profile: Optional[PlaceholderProfile] = None,
        drop_allowed: Optional[List[FrozenSet[str]]] = None,
    ) -> BatchResult:
        """
        Process texts in batches with parallel execution.

        Placeholders (%1$s, {name}, <b> …) are replaced by opaque tokens before sending and put back
        afterwards; a text whose tokens come back lost or changed is retried (placeholder_retries
        times: first in a batch, then alone with the API cache bypassed), then reported in
        `BatchResult.failed_indices` instead of being returned damaged.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation
            on_batch_complete: Optional callback function called after each batch completes
            translate_text_func: Optional function for translating individual texts (for non-batch providers)
            contexts: Optional per-text translator notes aligned with texts (algebras-ai only)
            placeholder_profile: Placeholder syntaxes to protect (default: generic profile)
            drop_allowed: Per-text placeholders that may be left out (count placeholders in
                plural forms that cover a single count)

        Returns:
            BatchResult with translations and statistics
        """
        profile = placeholder_profile or GENERIC_PROFILE

        # Flatten targeted ICU messages into literal segments first.
        # This preserves syntax tokens while translating only literal text. Plurals get the
        # branches the target language needs, each segment with a note on its category.
        preprocessed_texts, icu_mapping = self.icu_service.preprocess_texts(
            texts, target_lang=target_lang, source_lang=source_lang
        )
        # The API gets the full BCP-47 code, as on the single-text path (Translator.translate_text).
        source_lang = api_language_code(source_lang)
        target_lang = api_language_code(target_lang)
        preprocessed_contexts: List[Optional[str]] = [None] * len(preprocessed_texts)
        preprocessed_drop: List[FrozenSet[str]] = [frozenset()] * len(preprocessed_texts)
        for index, entry in enumerate(icu_mapping):
            # An ICU message may be split into several segments; each inherits its context.
            for offset in range(entry.count):
                if contexts and index < len(contexts):
                    preprocessed_contexts[entry.start + offset] = contexts[index]
                note = entry.note(offset)
                if note:
                    base = preprocessed_contexts[entry.start + offset]
                    preprocessed_contexts[entry.start + offset] = f"{base} {note}" if base else note
                if drop_allowed and index < len(drop_allowed):
                    preprocessed_drop[entry.start + offset] = drop_allowed[index] or frozenset()

        # Mask placeholders so the model only sees opaque tokens.
        masked = [mask(t, profile) if isinstance(t, str) else None for t in preprocessed_texts]
        api_texts = [m.text if m is not None else t for m, t in zip(masked, preprocessed_texts)]
        api_contexts = [
            combine_context(c, m, d) if m is not None else c
            for c, m, d in zip(preprocessed_contexts, masked, preprocessed_drop)
        ]

        result = self._process_segments(
            api_texts,
            source_lang,
            target_lang,
            ui_safe,
            glossary_id,
            on_batch_complete,
            translate_text_func,
            api_contexts,
            warn_dropped_contexts=bool(contexts and any(contexts)),
        )

        # Segments of failed API batches: left out (counted below).
        api_failed_segments = set(result.failed_positions)

        # Put placeholders back; retry rejected segments with a stronger note.
        # Segments of failed API batches come back as "" and are skipped by _unmask_all.
        failed_segments = self._unmask_all(result.translations, masked, profile, preprocessed_drop, set())
        first_failed_segments = set(failed_segments)
        if failed_segments:
            failed_segments = self._retry_placeholder_failures(
                sorted(failed_segments),
                result,
                api_texts,
                api_contexts,
                masked,
                preprocessed_texts,
                preprocessed_drop,
                profile,
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                translate_text_func,
            )

        failed_indices: Set[int] = set()
        first_failed_indices: Set[int] = set()
        for index, entry in enumerate(icu_mapping):
            segments = range(entry.start, entry.start + entry.count)
            if any(seg in failed_segments for seg in segments):
                failed_indices.add(index)
            if any(seg in first_failed_segments for seg in segments):
                first_failed_indices.add(index)

        if icu_mapping:
            result.translations = self.icu_service.postprocess_translations(
                icu_mapping, result.translations
            )
        for index in failed_indices:
            result.translations[index] = ""
        result.failed_indices = failed_indices
        left_out = set(failed_indices)
        for index, entry in enumerate(icu_mapping):
            if any(seg in api_failed_segments for seg in range(entry.start, entry.start + entry.count)):
                left_out.add(index)
        self.keys_sent += sum(1 for t in texts if isinstance(t, str) and t.strip())
        self.keys_left_out += len(left_out)
        result.first_attempt_failures = len(first_failed_indices)
        result.retry_recovered = len(first_failed_indices - failed_indices)
        if first_failed_indices:
            # One summary line for all retries.
            if failed_indices:
                print(
                    f"  ✗ {len(first_failed_indices)} translation(s) lost or changed placeholders; "
                    f"{result.retry_recovered} recovered on retry, {len(failed_indices)} still damaged "
                    "and not used; they stay untranslated (run again, or check with 'algebras placeholders')"
                )
            else:
                print(
                    f"  ⚠ {len(first_failed_indices)} translation(s) lost or changed placeholders; "
                    "all recovered on retry"
                )
        # --verbose: first-attempt vs after-retry success (the client follows set_verbose).
        if self.verbose or getattr(self.api_client, "verbose", False) is True:
            total = len(texts)
            print(
                f"  Placeholder check: {total - result.first_attempt_failures}/{total} passed on the "
                f"first attempt, {total - len(failed_indices)}/{total} after retries "
                f"({result.retry_recovered} recovered)"
            )
        return result

    def _retry_placeholder_failures(
        self,
        retry: List[int],
        result: BatchResult,
        api_texts: List[Any],
        api_contexts: List[Optional[str]],
        masked: List[Any],
        preprocessed_texts: List[Any],
        preprocessed_drop: List[FrozenSet[str]],
        profile: PlaceholderProfile,
        source_lang: str,
        target_lang: str,
        ui_safe: bool,
        glossary_id: str,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]],
    ) -> Set[int]:
        """
        Retry segments whose placeholders did not survive; return those still failing.

        Retry 1 resends them in a batch together, with a stronger note. Each further retry sends
        every still-failing segment alone (a batch of 1), with the note and the API's cache bypassed
        for that call only, so a cached damaged answer is not served again. Passing translations
        are written into `result.translations`; segments still failing are set to "".
        """
        pending = list(retry)
        for attempt in range(1, self.placeholder_retries + 1):
            if not pending:
                break
            alone = attempt > 1
            last = attempt == self.placeholder_retries
            retry_result = self._process_segments(
                [api_texts[i] for i in pending],
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                None,
                translate_text_func,
                [f"{_RETRY_NOTE} {api_contexts[i] or ''}".strip() for i in pending],
                warn_dropped_contexts=False,
                quiet=True,
                batch_size=1 if alone else None,
                ignore_cache=alone,
            )
            retried = list(retry_result.translations)
            still_failed = self._unmask_all(
                retried,
                [masked[i] for i in pending],
                profile,
                [preprocessed_drop[i] for i in pending],
                set(),
                key_labels=[preprocessed_texts[i] for i in pending] if last else None,
            )
            next_pending = []
            for local, segment_index in enumerate(pending):
                translated = retried[local] if local < len(retried) else ""
                if local in still_failed or not isinstance(translated, str) or translated == "":
                    # Still damaged, or the retry call itself failed: keep it pending.
                    next_pending.append(segment_index)
                else:
                    result.translations[segment_index] = translated
            pending = next_pending
        for segment_index in pending:
            result.translations[segment_index] = ""
        return set(pending)

    def _unmask_all(
        self,
        translations: List[Any],
        masked: List[Any],
        profile: PlaceholderProfile,
        drop: List[FrozenSet[str]],
        failed: Set[int],
        key_labels: Optional[List[Any]] = None,
    ) -> Set[int]:
        """Unmask translations in place; return indices whose placeholders did not survive."""
        for i, m in enumerate(masked):
            if m is None or i >= len(translations):
                continue
            translated = translations[i]
            if not isinstance(translated, str) or translated == "":
                continue  # empty source, or failed API batch
            try:
                translations[i] = unmask(translated, m, profile, drop[i])
            except PlaceholderError as e:
                failed.add(i)
                if key_labels is not None:
                    label = str(key_labels[i])[:60]
                    print(f"    ✗ '{label}': {e}")
        return failed

    def _process_segments(
        self,
        texts: List[Any],
        source_lang: str,
        target_lang: str,
        ui_safe: bool,
        glossary_id: str,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]],
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]],
        contexts: List[Optional[str]],
        warn_dropped_contexts: bool,
        quiet: bool = False,
        batch_size: Optional[int] = None,
        ignore_cache: bool = False,
    ) -> BatchResult:
        """
        Send already-masked segments through the provider (no ICU or placeholder handling).

        `batch_size` overrides self.batch_size for this call. `ignore_cache` bypasses the API's
        translation cache for this call only: it is passed per request, never stored on the
        shared client, so it cannot leak into later or concurrent calls.
        """
        preprocessed_texts = texts
        preprocessed_contexts = contexts

        # Filter empty strings and maintain mapping
        non_empty_texts = []
        non_empty_contexts: List[Optional[str]] = []
        empty_indices = []  # Track which indices were empty
        index_mapping = []  # Maps original index to non-empty index

        for i, text in enumerate(preprocessed_texts):
            if isinstance(text, str) and text.strip() == "":
                empty_indices.append(i)
                index_mapping.append(None)  # Mark as empty
            else:
                index_mapping.append(len(non_empty_texts))
                non_empty_texts.append(text)
                non_empty_contexts.append(preprocessed_contexts[i])

        # If all texts are empty, return early
        if not non_empty_texts:
            return BatchResult(
                translations=[""] * len(preprocessed_texts),
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=0,
                total_batches=0,
            )

        # Split into batches
        # Other providers translate text by text anyway; the override only applies to algebras-ai.
        size = (batch_size or self.batch_size) if self.provider == "algebras-ai" else self.batch_size
        total_texts = len(non_empty_texts)
        num_batches = (total_texts + size - 1) // size

        if not quiet:
            print(
                f"Processing {total_texts} text items in {num_batches} batches (batch size: {size})"
            )

        if self.provider != "algebras-ai" and warn_dropped_contexts:
            print(
                f"  ⚠ Plural-form notes are only sent to Algebras AI. With provider "
                f"'{self.provider}', plural forms such as few/many may come back identical "
                "— review them."
            )

        if self.provider == "algebras-ai":
            result = self._process_algebras_ai(
                non_empty_texts,
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                num_batches,
                on_batch_complete,
                empty_indices,
                index_mapping,
                len(preprocessed_texts),
                non_empty_contexts if any(non_empty_contexts) else None,
                batch_size=size,
                ignore_cache=ignore_cache,
                quiet=quiet,
            )
        else:
            result = self._process_other_provider(
                non_empty_texts,
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                num_batches,
                on_batch_complete,
                translate_text_func,
                empty_indices,
                index_mapping,
                len(preprocessed_texts),
            )

        return result

    def _process_algebras_ai(
        self,
        non_empty_texts: List[str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool,
        glossary_id: str,
        num_batches: int,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]],
        empty_indices: List[int],
        index_mapping: List[Optional[int]],
        total_texts: int,
        contexts: Optional[List[Optional[str]]] = None,
        batch_size: Optional[int] = None,
        ignore_cache: bool = False,
        quiet: bool = False,
    ) -> BatchResult:
        """
        Process batches using Algebras AI batch API with parallel execution.

        `ignore_cache` is sent with each request of this call only (per-call keyword of
        translate_batch), so a bypass never leaks into later calls or other threads.
        """
        size = batch_size or self.batch_size
        if not quiet:
            print(
                f"Using parallel batch processing with {self.max_parallel_batches} concurrent batches"
            )

        # Create batch data
        batches = []
        for i in range(0, len(non_empty_texts), size):
            batch_texts = non_empty_texts[i : i + size]
            batch_contexts = contexts[i : i + size] if contexts else None
            batch_idx = i // size + 1
            batches.append((batch_texts, batch_contexts, batch_idx))

        # Process batches in parallel using ThreadPoolExecutor
        failed_batches = []
        successful_batches = 0
        error_stats = {"5xx": [], "429": [], "other": []}
        all_translations = [None] * len(non_empty_texts)  # Pre-allocate list
        failed_non_empty: Set[int] = set()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_parallel_batches
        ) as executor:
            # Submit all batch translation tasks
            future_to_batch = {}
            for batch_texts, batch_contexts, batch_idx in batches:
                submit_kwargs = {"contexts": batch_contexts} if batch_contexts else {}
                if ignore_cache:
                    submit_kwargs["ignore_cache"] = True
                future = executor.submit(
                    self.api_client.translate_batch,
                    batch_texts,
                    source_lang,
                    target_lang,
                    ui_safe,
                    glossary_id,
                    **submit_kwargs,
                )
                future_to_batch[future] = (batch_texts, batch_idx)

            # Collect results as they complete
            completed_batches = 0
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_texts, batch_idx = future_to_batch[future]
                completed_batches += 1

                try:
                    translated_batch_raw = future.result()

                    # Store translations in the correct positions
                    batch_start_idx = (batch_idx - 1) * size
                    for j, translation in enumerate(translated_batch_raw):
                        if batch_start_idx + j < len(all_translations):
                            all_translations[batch_start_idx + j] = translation

                    # Create batch dict for callback (using indices as keys)
                    batch_dict = {}
                    for j, translation in enumerate(translated_batch_raw):
                        # Use a simple key format for callback
                        key = f"item_{batch_start_idx + j}"
                        batch_dict[key] = translation

                    # Call callback if provided
                    if on_batch_complete:
                        try:
                            on_batch_complete(batch_dict, batch_idx)
                        except Exception as e:
                            print(f"  ⚠ Error in batch complete callback: {str(e)}")

                    successful_batches += 1
                    if not quiet:
                        print(
                            f"Completed batch {batch_idx}/{num_batches} ({completed_batches}/{num_batches} total completed)"
                        )

                except Exception as e:
                    if not self._report_invalid_language(e, target_lang):
                        print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                    failed_batches.append(batch_idx)
                    failed_non_empty.update(
                        range((batch_idx - 1) * size, (batch_idx - 1) * size + len(batch_texts))
                    )

                    # Categorize error by type
                    error_msg = str(e)
                    status_match = re.search(r"(\d{3})", error_msg)
                    if status_match:
                        status_code = int(status_match.group(1))
                        if 500 <= status_code < 600:
                            error_stats["5xx"].append(batch_idx)
                        elif status_code == 429:
                            error_stats["429"].append(batch_idx)
                        else:
                            error_stats["other"].append(batch_idx)
                    else:
                        # If we can't determine, check error message content
                        if (
                            "502" in error_msg
                            or "503" in error_msg
                            or "504" in error_msg
                            or "500" in error_msg
                        ):
                            error_stats["5xx"].append(batch_idx)
                        elif "429" in error_msg:
                            error_stats["429"].append(batch_idx)
                        else:
                            error_stats["other"].append(batch_idx)

                    # Mark failed translations as None
                    batch_start_idx = (batch_idx - 1) * size
                    for j in range(len(batch_texts)):
                        if batch_start_idx + j < len(all_translations):
                            all_translations[batch_start_idx + j] = None

        # Print detailed summary
        total_failed = len(failed_batches)
        success_rate = (
            (successful_batches / num_batches * 100) if num_batches > 0 else 0
        )

        # Retries are quiet: errors are printed per batch, process() prints one summary line.
        if not quiet:
            print(f"\n  Summary:")
            print(f"    Total batches: {num_batches}")
            print(f"    Successful: {successful_batches} ({success_rate:.1f}%)")
            if total_failed > 0:
                print(f"    Failed: {total_failed} ({100 - success_rate:.1f}%)")
                if error_stats["5xx"]:
                    print(
                        f"      - 5xx errors: {len(error_stats['5xx'])} batches ({', '.join(map(str, error_stats['5xx']))})"
                    )
                if error_stats["429"]:
                    print(
                        f"      - 429 errors: {len(error_stats['429'])} batches ({', '.join(map(str, error_stats['429']))})"
                    )
                if error_stats["other"]:
                    print(
                        f"      - Other errors: {len(error_stats['other'])} batches ({', '.join(map(str, error_stats['other']))})"
                    )
            else:
                print(f"    ✓ All batches completed successfully")

        # Reconstruct full result list with empty strings in correct positions
        full_translations = []
        for i in range(total_texts):
            if i in empty_indices:
                # Preserve empty string
                full_translations.append("")
            else:
                # Get translation from non-empty list
                non_empty_idx = index_mapping[i]
                if non_empty_idx is not None and non_empty_idx < len(all_translations):
                    translation = all_translations[non_empty_idx]
                    # Use empty string if translation failed (None)
                    full_translations.append(translation if translation is not None else "")
                else:
                    full_translations.append("")

        return BatchResult(
            translations=full_translations,
            error_stats=error_stats,
            failed_batches=failed_batches,
            successful_batches=successful_batches,
            total_batches=num_batches,
            failed_positions={
                i for i, mapped in enumerate(index_mapping) if mapped is not None and mapped in failed_non_empty
            },
        )

    # Languages already reported as unsupported in this run (reset by reset_reported_languages).
    _reported_invalid_languages: Set[str] = set()

    @classmethod
    def reset_reported_languages(cls) -> None:
        cls._reported_invalid_languages = set()

    @classmethod
    def _report_invalid_language(cls, error: Exception, target_lang: str) -> bool:
        """
        The platform answers "Invalid language: X" for codes it does not support (pt-BR, sr-Cyrl).
        Report that once per language with what to do; return True if the error was one.
        """
        match = _INVALID_LANGUAGE.search(str(error))
        if not match:
            return False
        language = match.group(1) or target_lang
        if language not in cls._reported_invalid_languages:
            cls._reported_invalid_languages.add(language)
            print(
                f"  ✗ The platform does not support the language '{language}'; its keys are left out. "
                "Map it to a supported code with locale_mapping in .algebras.config, or ask support."
            )
        return True

    def _process_other_provider(
        self,
        non_empty_texts: List[str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool,
        glossary_id: str,
        num_batches: int,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]],
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]],
        empty_indices: List[int],
        index_mapping: List[Optional[int]],
        total_texts: int,
    ) -> BatchResult:
        """Process batches using individual translation calls for other providers."""
        if translate_text_func is None:
            raise ValueError(
                "translate_text_func is required for non-algebras-ai providers"
            )

        all_translations = []
        failed_batches = []
        successful_batches = 0
        error_stats = {"5xx": [], "429": [], "other": []}

        for i in range(0, len(non_empty_texts), self.batch_size):
            batch_texts = non_empty_texts[i : i + self.batch_size]
            batch_idx = i // self.batch_size + 1

            print(
                f"Processing batch {batch_idx}/{num_batches} ({len(batch_texts)} items)"
            )

            try:
                # Use ThreadPoolExecutor for parallel processing within each batch
                batch_translations = []
                batch_dict = {}
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.batch_size
                ) as executor:
                    # Create translation tasks
                    futures = {}
                    for j, text in enumerate(batch_texts):
                        future = executor.submit(
                            translate_text_func,
                            text,
                            source_lang,
                            target_lang,
                            ui_safe,
                            glossary_id,
                        )
                        futures[j] = future

                    # Collect results
                    for j, future in futures.items():
                        try:
                            translated_text = future.result()
                            batch_translations.append(translated_text)
                            key = f"item_{i + j}"
                            batch_dict[key] = translated_text
                        except Exception as e:
                            print(f"  ✗ Error translating text: {str(e)}")
                            batch_translations.append("")  # Use empty string on error
                            # Categorize error
                            error_msg = str(e)
                            status_match = re.search(r"(\d{3})", error_msg)
                            if status_match:
                                status_code = int(status_match.group(1))
                                if 500 <= status_code < 600:
                                    error_stats["5xx"].append(batch_idx)
                                elif status_code == 429:
                                    error_stats["429"].append(batch_idx)
                                else:
                                    error_stats["other"].append(batch_idx)

                all_translations.extend(batch_translations)

                # Call callback if provided
                if on_batch_complete and batch_dict:
                    try:
                        on_batch_complete(batch_dict, batch_idx)
                    except Exception as e:
                        print(f"  ⚠ Error in batch complete callback: {str(e)}")

                successful_batches += 1
                print(f"Completed batch {batch_idx}/{num_batches}")

            except Exception as e:
                print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                failed_batches.append(batch_idx)
                # Add empty strings for failed batch
                all_translations.extend([""] * len(batch_texts))
                # Categorize error
                error_msg = str(e)
                status_match = re.search(r"(\d{3})", error_msg)
                if status_match:
                    status_code = int(status_match.group(1))
                    if 500 <= status_code < 600:
                        error_stats["5xx"].append(batch_idx)
                    elif status_code == 429:
                        error_stats["429"].append(batch_idx)
                    else:
                        error_stats["other"].append(batch_idx)
                else:
                    error_stats["other"].append(batch_idx)
                # Re-raise the exception instead of falling back
                raise e

        # Reconstruct full result list with empty strings in correct positions
        full_translations = []
        for i in range(total_texts):
            if i in empty_indices:
                # Preserve empty string
                full_translations.append("")
            else:
                # Get translation from non-empty list
                non_empty_idx = index_mapping[i]
                if non_empty_idx is not None and non_empty_idx < len(all_translations):
                    full_translations.append(all_translations[non_empty_idx])
                else:
                    full_translations.append("")

        return BatchResult(
            translations=full_translations,
            error_stats=error_stats,
            failed_batches=failed_batches,
            successful_batches=successful_batches,
            total_batches=num_batches,
        )
