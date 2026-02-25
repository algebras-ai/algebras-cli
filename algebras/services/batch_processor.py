"""
Batch processor for translation operations.
Handles batch splitting, parallel processing, and error handling.
"""

import concurrent.futures
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Any

from algebras.services.api_client import AlgebrasAIClient
from algebras.services.icu_message_service import ICUMessageService


@dataclass
class BatchResult:
    """Result of batch processing operation."""

    translations: List[str]  # List of translations in the same order as input texts
    error_stats: Dict[str, List[int]]  # {"5xx": [...], "429": [...], "other": [...]}
    failed_batches: List[int]  # Indices of failed batches
    successful_batches: int
    total_batches: int


class BatchProcessor:
    """Processes translation batches with parallel execution and error handling."""

    def __init__(
        self,
        api_client: AlgebrasAIClient,
        batch_size: int,
        max_parallel_batches: int,
        provider: str,
        verbose: bool = False,
    ):
        """
        Initialize BatchProcessor.

        Args:
            api_client: API client for batch translation
            batch_size: Size of each batch
            max_parallel_batches: Maximum number of parallel batches
            provider: Translation provider name (e.g., "algebras-ai")
            verbose: Whether to enable verbose logging
        """
        self.api_client = api_client
        self.batch_size = batch_size
        self.max_parallel_batches = max_parallel_batches
        self.provider = provider
        self.verbose = verbose
        self.icu_service = ICUMessageService()

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
    ) -> BatchResult:
        """
        Process texts in batches with parallel execution.

        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation
            on_batch_complete: Optional callback function called after each batch completes
            translate_text_func: Optional function for translating individual texts (for non-batch providers)

        Returns:
            BatchResult with translations and statistics
        """
        # Flatten targeted ICU messages into literal segments first.
        # This preserves syntax tokens while translating only literal text.
        preprocessed_texts, icu_mapping = self.icu_service.preprocess_texts(texts)

        # Filter empty strings and maintain mapping
        non_empty_texts = []
        empty_indices = []  # Track which indices were empty
        index_mapping = []  # Maps original index to non-empty index

        for i, text in enumerate(preprocessed_texts):
            if isinstance(text, str) and text.strip() == "":
                empty_indices.append(i)
                index_mapping.append(None)  # Mark as empty
            else:
                index_mapping.append(len(non_empty_texts))
                non_empty_texts.append(text)

        # If all texts are empty, return early
        if not non_empty_texts:
            empty_result = BatchResult(
                translations=[""] * len(preprocessed_texts),
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=0,
                total_batches=0,
            )
            if icu_mapping:
                empty_result.translations = self.icu_service.postprocess_translations(
                    icu_mapping, empty_result.translations
                )
            return empty_result

        # Split into batches
        total_texts = len(non_empty_texts)
        num_batches = (total_texts + self.batch_size - 1) // self.batch_size

        print(
            f"Processing {total_texts} text items in {num_batches} batches (batch size: {self.batch_size})"
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

        if icu_mapping:
            result.translations = self.icu_service.postprocess_translations(
                icu_mapping, result.translations
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
    ) -> BatchResult:
        """Process batches using Algebras AI batch API with parallel execution."""
        print(
            f"Using parallel batch processing with {self.max_parallel_batches} concurrent batches"
        )

        # Create batch data
        batches = []
        for i in range(0, len(non_empty_texts), self.batch_size):
            batch_texts = non_empty_texts[i : i + self.batch_size]
            batch_idx = i // self.batch_size + 1
            batches.append((batch_texts, batch_idx))

        # Process batches in parallel using ThreadPoolExecutor
        failed_batches = []
        successful_batches = 0
        error_stats = {"5xx": [], "429": [], "other": []}
        all_translations = [None] * len(non_empty_texts)  # Pre-allocate list

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_parallel_batches
        ) as executor:
            # Submit all batch translation tasks
            future_to_batch = {}
            for batch_texts, batch_idx in batches:
                future = executor.submit(
                    self.api_client.translate_batch,
                    batch_texts,
                    source_lang,
                    target_lang,
                    ui_safe,
                    glossary_id,
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
                    batch_start_idx = (batch_idx - 1) * self.batch_size
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
                    print(
                        f"Completed batch {batch_idx}/{num_batches} ({completed_batches}/{num_batches} total completed)"
                    )

                except Exception as e:
                    print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                    failed_batches.append(batch_idx)

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
                    batch_start_idx = (batch_idx - 1) * self.batch_size
                    for j in range(len(batch_texts)):
                        if batch_start_idx + j < len(all_translations):
                            all_translations[batch_start_idx + j] = None

        # Print detailed summary
        total_failed = len(failed_batches)
        success_rate = (
            (successful_batches / num_batches * 100) if num_batches > 0 else 0
        )

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
        )

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
