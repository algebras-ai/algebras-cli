"""
API client for Algebras AI translation service
"""

import os
import time
import requests
from typing import Dict, List, Optional, Tuple

from colorama import Fore

from algebras.config import Config
from algebras.services.retry_handler import RetryHandler

# How long to keep polling a batch translation job before giving up. Mirrors
# the 300s timeout the platform's own synchronous batch endpoint used to
# enforce on the blocking Celery call it has now replaced with this
# submit+poll flow.
BATCH_JOB_POLL_TIMEOUT = 300.0
BATCH_JOB_POLL_INITIAL_INTERVAL = 2.0
BATCH_JOB_POLL_MAX_INTERVAL = 10.0


class AlgebrasAIClient:
    """Client for interacting with Algebras AI translation API."""

    def __init__(
        self,
        config: Config,
        retry_handler: RetryHandler,
        verbose: bool = False,
        custom_prompt: str = "",
        sync_batch: bool = False,
    ):
        """
        Initialize Algebras AI API client.

        Args:
            config: Config instance for getting base URL and settings
            retry_handler: RetryHandler instance for handling retries
            verbose: Whether to enable verbose logging
            custom_prompt: Custom prompt to use for translations
            sync_batch: If True, use the legacy blocking translate-batch
                endpoint. If False (default), submit via translate-batch-async
                and poll for the result.
        """
        self.config = config
        self._retry_handler = retry_handler
        self.verbose = verbose
        self.custom_prompt = custom_prompt
        self.sync_batch = sync_batch

    def set_custom_prompt(self, prompt: str) -> None:
        """
        Set a custom prompt to be used for translations.

        Args:
            prompt: Custom prompt text to use for translation
        """
        self.custom_prompt = prompt

    def set_verbose(self, verbose: bool) -> None:
        """
        Set verbose mode for detailed logging.

        Args:
            verbose: Whether to enable verbose logging
        """
        self.verbose = verbose

    def set_sync_batch(self, sync_batch: bool) -> None:
        """
        Choose which batch translation endpoint to use.

        Args:
            sync_batch: If True, use the legacy blocking translate-batch
                endpoint instead of the default submit+poll async endpoint.
        """
        self.sync_batch = sync_batch

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: str = "",
    ) -> str:
        """
        Translate text using Algebras AI API.

        Args:
            text: Text to translate
            source_lang: Source language code (already mapped to ISO 2-letter format, use 'auto' for automatic detection)
            target_lang: Target language code (already mapped to ISO 2-letter format)
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation

        Returns:
            Translated text

        Raises:
            ValueError: If API key is not found
            Exception: If API request fails
        """
        api_key = os.environ.get("ALGEBRAS_API_KEY")
        if not api_key:
            raise ValueError(
                "Algebras API key not found. Set the ALGEBRAS_API_KEY environment variable."
            )

        base_url = self.config.get_base_url()
        url = f"{base_url}/api/v1/translation/translate"
        headers = {"accept": "application/json", "X-Api-Key": api_key}

        # Use 'auto' if source_lang is not specified or is 'auto'
        source_lang_value = (
            source_lang if source_lang and source_lang != "auto" else "auto"
        )

        data = {
            "sourceLanguage": source_lang_value,
            "targetLanguage": target_lang,
            "textContent": text,
            "fileContent": "",
            "glossaryId": glossary_id,
            "prompt": self.custom_prompt,
            "flag": "true" if ui_safe else "false",
        }

        try:
            # Use retry helper for 429 errors
            def make_api_call():
                return requests.post(
                    url,
                    headers=headers,
                    files={
                        "sourceLanguage": (None, data["sourceLanguage"]),
                        "targetLanguage": (None, data["targetLanguage"]),
                        "textContent": (None, data["textContent"]),
                        "fileContent": (None, data["fileContent"]),
                        "glossaryId": (None, data["glossaryId"]),
                        "prompt": (None, data["prompt"]),
                        "flag": (None, data["flag"]),
                    },
                )

            response = self._retry_handler.execute_with_retry(make_api_call)

            if response.status_code == 200:
                result = response.json()
                return result.get("data", "")
            else:
                error_msg = f"Error from Algebras AI API: {response.status_code} - {response.text}"
                raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"Failed to translate with Algebras AI: {str(e)}")

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: str = "",
    ) -> List[str]:
        """
        Translate multiple texts using the Algebras AI batch API.

        Uses the async submit+poll endpoint by default; pass
        sync_batch=True to the client (or --sync-batch on the CLI) to fall
        back to the legacy blocking endpoint.

        Args:
            texts: List of texts to translate
            source_lang: Source language code (already mapped to ISO 2-letter format, use 'auto' for automatic detection)
            target_lang: Target language code (already mapped to ISO 2-letter format)
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation

        Returns:
            List of translated texts (raw, without normalization)

        Raises:
            ValueError: If API key is not found
            Exception: If API request fails or response format is invalid
        """
        if self.sync_batch:
            return self._translate_batch_sync(
                texts, source_lang, target_lang, ui_safe, glossary_id
            )
        return self._translate_batch_async(
            texts, source_lang, target_lang, ui_safe, glossary_id
        )

    @staticmethod
    def _split_empty_texts(
        texts: List[str],
    ) -> Tuple[List[str], List[int], List[Optional[int]]]:
        """
        Filter out empty (after strip) strings before sending to the API.

        Returns (non_empty_texts, empty_indices, index_mapping), where
        index_mapping[i] is the position of texts[i] in non_empty_texts, or
        None if texts[i] was empty.
        """
        non_empty_texts: List[str] = []
        empty_indices: List[int] = []
        index_mapping: List[Optional[int]] = []

        for i, text in enumerate(texts):
            if isinstance(text, str) and text.strip() == "":
                empty_indices.append(i)
                index_mapping.append(None)
            else:
                index_mapping.append(len(non_empty_texts))
                non_empty_texts.append(text)

        return non_empty_texts, empty_indices, index_mapping

    @staticmethod
    def _reassemble_full_translations(
        texts: List[str],
        translations: List[str],
        empty_indices: List[int],
        index_mapping: List[Optional[int]],
    ) -> List[str]:
        """Reinsert empty strings at their original positions."""
        full_translations = []
        for i in range(len(texts)):
            if i in empty_indices:
                full_translations.append("")
            else:
                full_translations.append(translations[index_mapping[i]])
        return full_translations

    def _extract_translations(
        self, result: Dict, non_empty_texts: List[str]
    ) -> List[str]:
        """
        Extract and validate the `translations` array from a batch
        translation result (the same shape returned by both the sync
        endpoint's immediate response and the async endpoint's `result`
        field once a job is READY).
        """
        if "translations" in result:
            translation_items = list(result["translations"])
            translation_items.sort(key=lambda x: x.get("index", 0))
            translations = [item.get("content", "") for item in translation_items]
        else:
            # Fallback to old format if structure is different
            translations = result if isinstance(result, list) else []

        if self.verbose and len(translations) > 0:
            print(
                f"  {Fore.CYAN}[API Response] Sample output: '{translations[0][:50]}...'{Fore.RESET}"
            )
            if len(non_empty_texts) > 0:
                matches_source = sum(
                    1
                    for i, trans in enumerate(translations)
                    if i < len(non_empty_texts) and trans == non_empty_texts[i]
                )
                if matches_source > len(translations) * 0.5:
                    print(
                        f"  {Fore.YELLOW}[WARNING] {matches_source}/{len(translations)} translations match source text - API may not be translating{Fore.RESET}"
                    )

        if len(translations) != len(non_empty_texts):
            raise Exception(
                f"Expected {len(non_empty_texts)} translations, but got {len(translations)}"
            )

        empty_translation_count = 0
        for i, translation in enumerate(translations):
            if not translation or translation.strip() == "":
                empty_translation_count += 1
                if self.verbose:
                    print(
                        f"  {Fore.YELLOW}[WARNING] Empty translation for: '{non_empty_texts[i][:50]}...'{Fore.RESET}"
                    )

        if empty_translation_count > 0 and self.verbose:
            print(
                f"  {Fore.YELLOW}[WARNING] {empty_translation_count}/{len(translations)} translations are empty{Fore.RESET}"
            )

        return translations

    def _translate_batch_sync(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: str = "",
    ) -> List[str]:
        """Legacy blocking batch translation call (translate-batch)."""
        api_key = os.environ.get("ALGEBRAS_API_KEY")
        if not api_key:
            raise ValueError(
                "Algebras API key not found. Set the ALGEBRAS_API_KEY environment variable."
            )

        base_url = self.config.get_base_url()
        url = f"{base_url}/api/v1/translation/translate-batch"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        }

        source_lang_value = (
            source_lang if source_lang and source_lang != "auto" else "auto"
        )

        non_empty_texts, empty_indices, index_mapping = self._split_empty_texts(texts)
        if not non_empty_texts:
            return [""] * len(texts)

        data = {
            "texts": non_empty_texts,
            "sourceLanguage": source_lang_value,
            "targetLanguage": target_lang,
            "glossaryId": glossary_id,
            "prompt": self.custom_prompt,
            "flag": ui_safe,
        }

        if self.verbose:
            print(
                f"  {Fore.CYAN}[API Request] Translating {len(non_empty_texts)} texts from {source_lang_value} to {target_lang}{Fore.RESET}"
            )
            if len(non_empty_texts) > 0:
                print(
                    f"  {Fore.CYAN}[API Request] Sample input: '{non_empty_texts[0][:50]}...'{Fore.RESET}"
                )

        try:
            # Use retry helper for 429 errors
            def make_api_call():
                return requests.post(url, headers=headers, json=data)

            response = self._retry_handler.execute_with_retry(make_api_call)

            if response.status_code != 200:
                raise Exception(
                    f"Error from Algebras AI batch API: {response.status_code} - {response.text}"
                )

            result = response.json()

            if self.verbose:
                print(
                    f"  {Fore.CYAN}[API Response] Status: {response.status_code}{Fore.RESET}"
                )

            translations = self._extract_translations(
                result.get("data", {}), non_empty_texts
            )
            return self._reassemble_full_translations(
                texts, translations, empty_indices, index_mapping
            )
        except Exception as e:
            raise Exception(f"Failed to translate batch with Algebras AI: {str(e)}")

    def _translate_batch_async(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: str = "",
    ) -> List[str]:
        """
        Submit a batch translation job (translate-batch-async) and poll for
        its result, instead of blocking the request on the legacy endpoint.
        """
        api_key = os.environ.get("ALGEBRAS_API_KEY")
        if not api_key:
            raise ValueError(
                "Algebras API key not found. Set the ALGEBRAS_API_KEY environment variable."
            )

        base_url = self.config.get_base_url()
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        }

        source_lang_value = (
            source_lang if source_lang and source_lang != "auto" else "auto"
        )

        non_empty_texts, empty_indices, index_mapping = self._split_empty_texts(texts)
        if not non_empty_texts:
            return [""] * len(texts)

        data = {
            "texts": non_empty_texts,
            "sourceLanguage": source_lang_value,
            "targetLanguage": target_lang,
            "glossaryId": glossary_id,
            "prompt": self.custom_prompt,
            "flag": ui_safe,
        }

        if self.verbose:
            print(
                f"  {Fore.CYAN}[API Request] Submitting async batch of {len(non_empty_texts)} texts from {source_lang_value} to {target_lang}{Fore.RESET}"
            )

        try:
            submit_url = f"{base_url}/api/v1/translation/translate-batch-async"

            def make_submit_call():
                return requests.post(submit_url, headers=headers, json=data)

            response = self._retry_handler.execute_with_retry(make_submit_call)

            if response.status_code != 200:
                raise Exception(
                    f"Error from Algebras AI batch API: {response.status_code} - {response.text}"
                )

            job = response.json().get("data", {})
            job_id = job.get("job_id")
            if not job_id:
                raise Exception("Async batch submission did not return a job_id")

            if self.verbose:
                print(
                    f"  {Fore.CYAN}[API Response] Job {job_id} submitted, status: {job.get('status')}{Fore.RESET}"
                )

            # The submit response only ever carries {job_id, status} - even
            # when status is already READY (e.g. an all-cache-hit batch) the
            # result itself is only available from the GET endpoint, so we
            # always poll at least once.
            result = self._poll_batch_job(job_id, headers, base_url)

            translations = self._extract_translations(result, non_empty_texts)
            return self._reassemble_full_translations(
                texts, translations, empty_indices, index_mapping
            )
        except Exception as e:
            raise Exception(f"Failed to translate batch with Algebras AI: {str(e)}")

    def _poll_batch_job(self, job_id: str, headers: Dict, base_url: str) -> Dict:
        """
        Poll GET /translation/translate-batch-async/{job_id} until it
        reaches READY or ERROR, or BATCH_JOB_POLL_TIMEOUT is exceeded.

        Polls directly with `requests` rather than through the shared
        RetryHandler/RateLimiter: those are tuned for the translation
        endpoints' rate limits, while this GET has a much higher server-side
        limit and needs its own lightweight backoff instead.
        """
        status_url = f"{base_url}/api/v1/translation/translate-batch-async/{job_id}"
        start_time = time.time()
        interval = BATCH_JOB_POLL_INITIAL_INTERVAL
        consecutive_network_errors = 0

        while True:
            if time.time() - start_time > BATCH_JOB_POLL_TIMEOUT:
                raise Exception(
                    f"Timed out after {BATCH_JOB_POLL_TIMEOUT:.0f}s waiting for "
                    f"batch translation job {job_id}"
                )

            try:
                response = requests.get(status_url, headers=headers)
                consecutive_network_errors = 0
            except requests.exceptions.RequestException as e:
                consecutive_network_errors += 1
                if consecutive_network_errors > 5:
                    raise Exception(
                        f"Failed to poll batch translation job {job_id}: {str(e)}"
                    )
                time.sleep(interval)
                continue

            if response.status_code != 200:
                raise Exception(
                    f"Error polling batch translation job {job_id}: "
                    f"{response.status_code} - {response.text}"
                )

            job = response.json().get("data", {})
            status = job.get("status")

            if status == "READY":
                return job.get("result", {})
            if status == "ERROR":
                raise Exception(
                    f"Batch translation job {job_id} failed: "
                    f"{job.get('error', 'Unknown error')}"
                )

            time.sleep(interval)
            interval = min(interval * 1.5, BATCH_JOB_POLL_MAX_INTERVAL)
