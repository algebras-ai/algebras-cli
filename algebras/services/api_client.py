"""
API client for Algebras AI translation service
"""

import os
import requests
from typing import List, Optional

from colorama import Fore

from algebras.config import Config
from algebras.services.retry_handler import RetryHandler


class AlgebrasAIClient:
    """Client for interacting with Algebras AI translation API."""

    def __init__(
        self,
        config: Config,
        retry_handler: RetryHandler,
        verbose: bool = False,
        custom_prompt: str = "",
    ):
        """
        Initialize Algebras AI API client.

        Args:
            config: Config instance for getting base URL and settings
            retry_handler: RetryHandler instance for handling retries
            verbose: Whether to enable verbose logging
            custom_prompt: Custom prompt to use for translations
        """
        self.config = config
        self._retry_handler = retry_handler
        self.verbose = verbose
        self.custom_prompt = custom_prompt

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
        Translate multiple texts using Algebras AI batch API.

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

        # Use 'auto' if source_lang is not specified or is 'auto'
        source_lang_value = (
            source_lang if source_lang and source_lang != "auto" else "auto"
        )

        # Filter out empty strings (after strip) - maintain mapping to preserve order
        non_empty_texts = []
        empty_indices = []  # Track which indices were empty
        index_mapping = []  # Maps original index to non-empty index

        for i, text in enumerate(texts):
            if isinstance(text, str) and text.strip() == "":
                empty_indices.append(i)
                index_mapping.append(None)  # Mark as empty
            else:
                index_mapping.append(len(non_empty_texts))
                non_empty_texts.append(text)

        # If all texts are empty, return empty strings
        if not non_empty_texts:
            return [""] * len(texts)

        data = {
            "texts": non_empty_texts,
            "sourceLanguage": source_lang_value,
            "targetLanguage": target_lang,
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

            if response.status_code == 200:
                result = response.json()

                if self.verbose:
                    print(
                        f"  {Fore.CYAN}[API Response] Status: {response.status_code}{Fore.RESET}"
                    )

                # Handle the correct API response format
                if "data" in result and "translations" in result["data"]:
                    # Extract translations from the nested structure
                    translation_items = result["data"]["translations"]
                    # Sort by index to maintain order and extract content
                    translation_items.sort(key=lambda x: x.get("index", 0))
                    translations = [
                        item.get("content", "") for item in translation_items
                    ]
                else:
                    # Fallback to old format if structure is different
                    translations = result.get("data", [])

                if self.verbose and len(translations) > 0:
                    print(
                        f"  {Fore.CYAN}[API Response] Sample output: '{translations[0][:50]}...'{Fore.RESET}"
                    )
                    # Check if translation matches source (potential issue)
                    if len(translations) > 0 and len(non_empty_texts) > 0:
                        matches_source = sum(
                            1
                            for i, trans in enumerate(translations)
                            if trans == non_empty_texts[i]
                        )
                        if matches_source > len(translations) * 0.5:
                            print(
                                f"  {Fore.YELLOW}[WARNING] {matches_source}/{len(translations)} translations match source text - API may not be translating{Fore.RESET}"
                            )

                # Ensure we have the same number of translations as non-empty input texts
                if len(translations) != len(non_empty_texts):
                    raise Exception(
                        f"Expected {len(non_empty_texts)} translations, but got {len(translations)}"
                    )

                # Check for empty or missing translations (warn but don't fail)
                empty_translation_count = 0
                for i, translation in enumerate(translations):
                    if not translation or translation.strip() == "":
                        empty_translation_count += 1
                        if self.verbose:
                            print(
                                f"  {Fore.YELLOW}[WARNING] Empty translation for: '{non_empty_texts[i][:50]}...'{Fore.RESET}"
                            )

                # Warn if many translations are empty
                if empty_translation_count > 0:
                    if self.verbose:
                        print(
                            f"  {Fore.YELLOW}[WARNING] {empty_translation_count}/{len(translations)} translations are empty{Fore.RESET}"
                        )

                # Reconstruct full result list with empty strings in correct positions
                full_translations = []
                for i in range(len(texts)):
                    if i in empty_indices:
                        # Preserve empty string
                        full_translations.append("")
                    else:
                        # Get translation from non-empty list
                        non_empty_idx = index_mapping[i]
                        full_translations.append(translations[non_empty_idx])

                return full_translations
            else:
                error_msg = f"Error from Algebras AI batch API: {response.status_code} - {response.text}"
                raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"Failed to translate batch with Algebras AI: {str(e)}")
