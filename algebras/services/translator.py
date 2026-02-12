"""
Translation service using AI providers
"""

import os
import json
import yaml
import requests
import hashlib
import pickle
import concurrent.futures
from typing import Dict, Any, List, Optional, Callable

from algebras.config import Config as ConfigClass
import re
import time

from colorama import Fore

from algebras.utils.lang_validator import map_language_code
from algebras.utils.ts_handler import read_ts_translation_file
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.ios_strings_handler import read_ios_strings_file
from algebras.utils.ios_stringsdict_handler import (
    read_ios_stringsdict_file,
    extract_translatable_strings,
)
from algebras.utils.po_handler import read_po_file
from algebras.utils.html_handler import read_html_file
from algebras.utils.arb_handler import (
    read_arb_file,
    extract_translatable_strings as extract_arb_strings,
)
from algebras.utils.xliff_handler import (
    read_xliff_file,
    extract_translatable_strings as extract_xliff_strings,
)
from algebras.utils.properties_handler import read_properties_file
from algebras.utils.csv_handler import (
    read_csv_file,
    is_glossary_csv,
)
from algebras.utils.xlsx_handler import (
    read_xlsx_file,
    is_glossary_xlsx,
)
from algebras.utils.nested_structure_handler import (
    get_nested_value,
    set_nested_value,
)
from algebras.services.rate_limiter import RateLimiter
from algebras.services.retry_handler import RetryHandler
from algebras.services.api_client import AlgebrasAIClient
from algebras.services.batch_processor import BatchProcessor, BatchResult
from algebras.services.string_normalizer import StringNormalizer
from algebras.services.strategies.strategy_factory import TranslationStrategyFactory


class TranslationCache:
    """Cache for storing translations to avoid duplicate API calls."""

    _instance = None
    _cache = {}
    _max_size = 4096 * 100  # Approximately 10MB
    _cache_file = os.path.join(os.path.expanduser("~"), ".algebras.cache")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranslationCache, cls).__new__(cls)
            cls._instance._load_cache()
        return cls._instance

    def _load_cache(self):
        """Load cache from disk if it exists."""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "rb") as f:
                    self._cache = pickle.load(f)
                print(f"Loaded {len(self._cache)} translations from cache file")
            except (pickle.PickleError, EOFError, Exception) as e:
                print(f"Failed to load translation cache: {str(e)}")
                self._cache = {}
        else:
            print(f"No cache file found at {self._cache_file}, creating new cache")
            self._cache = {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            cache_dir = os.path.dirname(self._cache_file)
            os.makedirs(cache_dir, exist_ok=True)

            with open(self._cache_file, "wb") as f:
                pickle.dump(self._cache, f)
        except Exception as e:
            print(f"Failed to save translation cache: {str(e)}")

    def get(self, key):
        """Get a value from the cache."""
        return self._cache.get(key)

    def set(self, key, value):
        """Set a value in the cache and persist to disk."""
        # If cache is at max size, remove oldest item
        if len(self._cache) >= self._max_size:
            # Remove a random item as a simple strategy
            if self._cache:
                self._cache.pop(next(iter(self._cache)))

        self._cache[key] = value
        self._save_cache()

    def get_cache_key(self, text, source_lang, target_lang, ui_safe, prompt=""):
        """Generate a unique cache key for the translation parameters."""
        if prompt:
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            return f"{text}|{source_lang}|{target_lang}|{ui_safe}|{prompt_hash}"
        else:
            return f"{text}|{source_lang}|{target_lang}|{ui_safe}"

    def clear(self):
        """Clear the cache."""
        self._cache = {}
        self._save_cache()

    def info(self):
        """Return information about the cache."""
        return {
            "entries": len(self._cache),
            "max_size": self._max_size,
            "cache_file": self._cache_file,
        }


class Translator:
    """AI-powered translation service."""

    def __init__(self, config: Optional[ConfigClass] = None):
        """
        Initialize Translator with optional Config instance.

        Args:
            config: Optional Config instance. If None, creates a new Config with default path.
        """
        if config is None:
            from algebras.config import Config

            config = Config()

        self.config = config
        if not self.config.exists():
            raise FileNotFoundError(
                "No Algebras configuration found. Run 'algebras init' first."
            )

        self.config.load()
        self.api_config = self.config.get_api_config()

        # Get batch size from environment or config, default to 20
        self.batch_size = int(os.environ.get("ALGEBRAS_BATCH_SIZE", 20))
        if self.config.has_setting("batch_size"):
            self.batch_size = int(self.config.get_setting("batch_size"))

        # Get max parallel batches from config, default to 5
        self.max_parallel_batches = int(
            os.environ.get("ALGEBRAS_MAX_PARALLEL_BATCHES", 5)
        )
        if self.config.has_setting("max_parallel_batches"):
            self.max_parallel_batches = int(
                self.config.get_setting("max_parallel_batches")
            )

        # Initialize the translation cache
        self.cache = TranslationCache()

        # Initialize string normalizer
        self.string_normalizer = StringNormalizer(self.config)

        # Initialize custom prompt
        self.custom_prompt = ""

        # Initialize verbose flag
        self.verbose = False

        # Initialize rate limiter and retry handler
        # Rate limiter: 30 requests per minute (server limit is 30)
        self._rate_limiter = RateLimiter(max_requests_per_minute=30)
        self._retry_handler = RetryHandler(
            rate_limiter=self._rate_limiter, max_retries=5, initial_wait=1.0
        )

        # Initialize API client
        self.api_client = AlgebrasAIClient(
            config=self.config,
            retry_handler=self._retry_handler,
            verbose=self.verbose,
            custom_prompt=self.custom_prompt,
        )

        # BatchProcessor will be created lazily when needed
        self._batch_processor = None

    def _get_batch_processor(self) -> BatchProcessor:
        """Get or create BatchProcessor instance."""
        if self._batch_processor is None:
            provider = self.api_config.get("provider", "algebras-ai")
            self._batch_processor = BatchProcessor(
                api_client=self.api_client,
                batch_size=self.batch_size,
                max_parallel_batches=self.max_parallel_batches,
                provider=provider,
                verbose=self.verbose,
            )
        return self._batch_processor

    def set_custom_prompt(self, prompt: str) -> None:
        """
        Set a custom prompt to be used for translations.

        Args:
            prompt: Custom prompt text to use for translation
        """
        self.custom_prompt = prompt
        self.api_client.set_custom_prompt(prompt)

    def set_verbose(self, verbose: bool) -> None:
        """
        Set verbose mode for detailed logging.

        Args:
            verbose: Whether to enable verbose logging
        """
        self.verbose = verbose
        self.api_client.set_verbose(verbose)

    def translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
    ) -> str:
        """
        Translate a text from source language to target language.

        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translation will not be longer than the original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)

        Returns:
            Translated text
        """
        # Resolve glossary_id from config if not provided
        if glossary_id is None:
            glossary_id = self.config.get_setting("api.glossary_id", "")

        # Map language codes to ISO 2-letter format
        source_lang = map_language_code(source_lang)
        target_lang = map_language_code(target_lang)

        # Check cache first
        cache_key = self.cache.get_cache_key(
            text, source_lang, target_lang, ui_safe, self.custom_prompt
        )
        cached_translation = self.cache.get(cache_key)
        if cached_translation:
            print(
                f"Cache hit: Using cached translation for '{text[:30]}...' ({source_lang} → {target_lang})"
            )
            return cached_translation

        print(
            f"Cache miss: Translating '{text[:30]}...' ({source_lang} → {target_lang})"
        )
        provider = self.api_config.get("provider", "algebras-ai")

        if provider == "algebras-ai":
            translation = self.api_client.translate(
                text, source_lang, target_lang, ui_safe, glossary_id
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Apply normalization to the translation
        translation = self.string_normalizer.normalize(text, translation)

        # Update cache with new translation
        self.cache.set(cache_key, translation)
        print(
            f"Added translation to cache: '{text[:30]}...' ({source_lang} → {target_lang})"
        )

        return translation

    def translate_file(
        self,
        file_path: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translate a localization file to the target language.

        Args:
            file_path: Path to the localization file
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)

        Returns:
            Translated content as a dictionary
        """
        # Determine file format
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
        elif file_path.endswith((".yaml", ".yml")):
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
        elif file_path.endswith(".ts"):
            content = read_ts_translation_file(file_path)
        elif file_path.endswith(".xml"):
            content = read_android_xml_file(file_path)
        elif file_path.endswith(".strings"):
            content = read_ios_strings_file(file_path)
        elif file_path.endswith(".stringsdict"):
            # For .stringsdict files, extract translatable strings to get a flat dictionary
            raw_content = read_ios_stringsdict_file(file_path)
            content = extract_translatable_strings(raw_content)
        elif file_path.endswith(".po"):
            content = read_po_file(file_path)
        elif file_path.endswith(".html"):
            content = read_html_file(file_path)
        elif file_path.endswith(".arb"):
            content = read_arb_file(file_path)
        elif file_path.endswith((".xlf", ".xliff")):
            content = read_xliff_file(file_path)
        elif file_path.endswith(".properties"):
            content = read_properties_file(file_path)
        elif file_path.endswith((".csv", ".tsv")):
            # Check if it's a glossary CSV/TSV or translation CSV/TSV
            if is_glossary_csv(file_path):
                raise ValueError(
                    f"CSV/TSV file {file_path} appears to be a glossary file, not a translation file"
                )
            content = read_csv_file(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            # Check if it's a glossary XLSX or translation XLSX
            if is_glossary_xlsx(file_path):
                raise ValueError(
                    f"XLSX file {file_path} appears to be a glossary file, not a translation file"
                )
            content = read_xlsx_file(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Assume the source language is the first language in the config
        source_lang = self.config.get_languages()[0]

        # Get appropriate strategy for this file format
        strategy = TranslationStrategyFactory.get_strategy(file_path, self)

        # Determine translate_text_func for non-algebras-ai providers
        provider = self.api_config.get("provider", "algebras-ai")
        translate_text_func = None if provider == "algebras-ai" else self.translate_text

        # Handle special cases that need preprocessing
        if file_path.endswith(".arb"):
            # ARB files need special handling to extract translatable strings
            translatable_strings = extract_arb_strings(content)
            # Use flat dict strategy for ARB
            flat_strategy = TranslationStrategyFactory.get_flat_dict_strategy(self)
            translated_strings = flat_strategy.translate(
                translatable_strings,
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                None,
                translate_text_func,
            )
            # Merge back with original content, preserving metadata
            translated = content.copy()
            translated.update(translated_strings)
        elif file_path.endswith((".xlf", ".xliff")):
            # XLIFF files need special handling to extract translatable strings
            translatable_strings = extract_xliff_strings(content)
            # Use flat dict strategy for XLIFF
            flat_strategy = TranslationStrategyFactory.get_flat_dict_strategy(self)
            translated_strings = flat_strategy.translate(
                translatable_strings,
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                None,
                translate_text_func,
            )
            # For XLIFF, we need to update the target elements
            translated = self._update_xliff_targets(content, translated_strings)
        else:
            # Use the strategy for translation
            translated = strategy.translate(
                content,
                source_lang,
                target_lang,
                ui_safe,
                glossary_id,
                None,
                translate_text_func,
            )

        return translated

    def translate_missing_keys(
        self,
        source_content: Dict[str, Any],
        target_content: Dict[str, Any],
        missing_keys: List[str],
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        source_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translate only the missing keys in a target dictionary.

        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary (with missing keys)
            missing_keys: List of dot-notation keys that are missing
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            source_file_path: Path to the source file (used to determine file format)

        Returns:
            Updated target content with translated missing keys
        """
        # Make a deep copy of the target content to avoid modifying it directly
        updated_content = target_content.copy()

        # Get source language
        source_lang = self.config.get_source_language()

        # Translate each missing key and update the target content
        for key_path in missing_keys:
            # First, check if this is a direct key in source_content (flat format)
            if isinstance(source_content, dict) and key_path in source_content:
                source_value = source_content[key_path]
                if isinstance(source_value, str):
                    # Translate the value
                    translated_value = self.translate_text(
                        source_value, source_lang, target_lang, ui_safe, glossary_id
                    )
                    # Update target content directly (flat format)
                    updated_content[key_path] = translated_value
            else:
                # Try to treat it as a dot-notation path (nested format)
                key_parts = key_path.split(".")
                source_value = get_nested_value(source_content, key_parts)

                if isinstance(source_value, str):
                    # Translate the value
                    translated_value = self.translate_text(
                        source_value, source_lang, target_lang, ui_safe, glossary_id
                    )
                    # Update the target content with the translated value (nested format)
                    set_nested_value(updated_content, key_parts, translated_value)
                else:
                    # Determine file format to decide how to handle missing keys
                    is_flat_format = False
                    if source_file_path:
                        is_flat_format = source_file_path.endswith((".po", ".csv", ".tsv"))
                    else:
                        # Fallback: check structure of source_content
                        is_flat_format = (
                            isinstance(source_content, dict) and
                            all(isinstance(v, str) for v in source_content.values()) and
                            not any("." in k for k in source_content.keys())
                        )
                    
                    if is_flat_format:
                        # For flat formats like .po, the key itself might BE the text to translate
                        translated_value = self.translate_text(
                            key_path, source_lang, target_lang, ui_safe, glossary_id
                        )
                        updated_content[key_path] = translated_value
                    else:
                        # For nested formats, if key not found in source, set empty string
                        set_nested_value(updated_content, key_parts, "")

        return updated_content

    def translate_outdated_keys(
        self,
        source_content: Dict[str, Any],
        target_content: Dict[str, Any],
        outdated_keys: List[str],
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        source_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translate only the outdated keys in a target dictionary.

        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary
            outdated_keys: List of dot-notation keys that are outdated
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            source_file_path: Path to the source file (used to determine file format)

        Returns:
            Updated target content with translated outdated keys
        """
        # Make a deep copy of the target content to avoid modifying it directly
        updated_content = target_content.copy()

        # Get source language
        source_lang = self.config.get_source_language()

        # Translate each outdated key and update the target content
        for key_path in outdated_keys:
            # First, check if this is a direct key in source_content (flat format)
            if isinstance(source_content, dict) and key_path in source_content:
                source_value = source_content[key_path]
                if isinstance(source_value, str):
                    # Translate the value
                    translated_value = self.translate_text(
                        source_value, source_lang, target_lang, ui_safe, glossary_id
                    )
                    # Update target content directly (flat format)
                    updated_content[key_path] = translated_value
            else:
                # Try to treat it as a dot-notation path (nested format)
                key_parts = key_path.split(".")
                source_value = get_nested_value(source_content, key_parts)

                if isinstance(source_value, str):
                    # Translate the value
                    translated_value = self.translate_text(
                        source_value, source_lang, target_lang, ui_safe, glossary_id
                    )
                    # Update the target content with the translated value (nested format)
                    set_nested_value(updated_content, key_parts, translated_value)
                else:
                    # Determine file format to decide how to handle missing keys
                    is_flat_format = False
                    if source_file_path:
                        is_flat_format = source_file_path.endswith((".po", ".csv", ".tsv"))
                    else:
                        # Fallback: check structure of source_content
                        is_flat_format = (
                            isinstance(source_content, dict) and
                            all(isinstance(v, str) for v in source_content.values()) and
                            not any("." in k for k in source_content.keys())
                        )
                    
                    if is_flat_format:
                        # For flat formats like .po, the key itself might BE the text to translate
                        translated_value = self.translate_text(
                            key_path, source_lang, target_lang, ui_safe, glossary_id
                        )
                        updated_content[key_path] = translated_value
                    else:
                        # For nested formats, if key not found in source, set empty string
                        set_nested_value(updated_content, key_parts, "")

        return updated_content

    def preload_translations(self, file_path: str) -> int:
        """
        Preload all text values from a localization file into the cache.
        This can be useful to ensure all subsequent translations use the cache.

        Args:
            file_path: Path to the localization file

        Returns:
            Number of items loaded into cache
        """
        # Determine file format
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
        elif file_path.endswith((".yaml", ".yml")):
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
        elif file_path.endswith(".ts"):
            content = read_ts_translation_file(file_path)
        elif file_path.endswith(".xml"):
            content = read_android_xml_file(file_path)
        elif file_path.endswith(".strings"):
            content = read_ios_strings_file(file_path)
        elif file_path.endswith(".stringsdict"):
            # For .stringsdict files, extract translatable strings to get a flat dictionary
            raw_content = read_ios_stringsdict_file(file_path)
            content = extract_translatable_strings(raw_content)
        elif file_path.endswith(".po"):
            content = read_po_file(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Extract all string values from the nested dict
        all_strings = []

        def extract_strings(data):
            if isinstance(data, dict):
                for value in data.values():
                    extract_strings(value)
            elif isinstance(data, str):
                all_strings.append(data)

        extract_strings(content)
        print(f"Found {len(all_strings)} text items in {file_path}")

        # Get source language
        source_lang = self.config.get_source_language()

        # Load translations into cache
        loaded_count = 0
        for text in all_strings:
            cache_key = self.cache.get_cache_key(
                text, source_lang, source_lang, False, ""
            )
            if not self.cache.get(cache_key):
                self.cache.set(
                    cache_key, text
                )  # Set identity translation (same language)
                loaded_count += 1

        print(f"Preloaded {loaded_count} items into translation cache")
        return loaded_count

    def translate_missing_keys_batch(
        self,
        source_content: Dict[str, Any],
        target_content: Dict[str, Any],
        missing_keys: List[str],
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        source_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Translate missing keys in batches to avoid overloading the API.

        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary (with missing keys)
            missing_keys: List of dot-notation keys that are missing
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            source_file_path: Path to the source file (used to determine file format)

        Returns:
            Updated target content with translated missing keys
        """
        # Resolve glossary_id from config if not provided
        if glossary_id is None:
            glossary_id = self.config.get_setting("api.glossary_id", "")

        # Make a deep copy of the target content to avoid modifying it directly
        updated_content = target_content.copy()

        # Get source language
        source_lang = self.config.get_source_language()

        # Collect texts and their corresponding key paths, filter empty strings
        texts_to_translate = []
        key_paths_list = []
        key_parts_list = []
        empty_key_paths = []  # Track keys with empty strings

        for key_path in missing_keys:
            # First, check if this is a direct key in source_content (flat format)
            if isinstance(source_content, dict) and key_path in source_content:
                source_value = source_content[key_path]
                if isinstance(source_value, str):
                    # Filter empty strings - preserve them but don't send to API
                    if source_value.strip() == "":
                        empty_key_paths.append((key_path, [key_path]))
                    else:
                        texts_to_translate.append(source_value)
                        key_paths_list.append(key_path)
                        key_parts_list.append([key_path])  # Treat as single-level key
                elif isinstance(source_value, dict):
                    # Handle plural/dict values (e.g., Android XML plurals)
                    # Each plural form (one, other, etc.) needs to be translated separately
                    for plural_key, plural_value in source_value.items():
                        if isinstance(plural_value, str) and plural_value.strip():
                            # Create a composite key for this plural form (e.g., "Plural.tasks.__plurals__.one")
                            composite_key = f"{key_path}.{plural_key}"
                            texts_to_translate.append(plural_value)
                            key_paths_list.append(composite_key)
                            key_parts_list.append([key_path, plural_key])  # Store as nested structure
                            print(f"DEBUG: ✓ Added plural form '{composite_key}' to translation queue")
            else:
                # Try to treat it as a dot-notation path (nested format)
                key_parts = key_path.split(".")
                print(f"DEBUG: Trying as nested path -> key_parts: {key_parts}")

                source_value = get_nested_value(source_content, key_parts)
                print(
                    f"DEBUG: Source value for nested '{key_path}': {repr(source_value)} (type: {type(source_value)})"
                )

                if isinstance(source_value, str):
                    # Filter empty strings - preserve them but don't send to API
                    if source_value.strip() == "":
                        empty_key_paths.append((key_path, key_parts))
                    else:
                        # This is a nested format, use the source value as text to translate
                        texts_to_translate.append(source_value)
                        key_paths_list.append(key_path)
                        key_parts_list.append(key_parts)
                        print(
                            f"DEBUG: ✓ Added '{key_path}' to translation queue (nested format)"
                        )
                else:
                    print(
                        f"DEBUG: Source value for '{key_path}': {repr(source_value)} (type: {type(source_value)})"
                    )
                    # Determine file format to decide how to handle missing keys
                    is_flat_format = False
                    if source_file_path:
                        is_flat_format = source_file_path.endswith((".po", ".csv", ".tsv"))
                    else:
                        # Fallback: check structure of source_content
                        # If it's a flat dictionary (all values are strings, no nested dicts),
                        # then it might be a flat format
                        is_flat_format = (
                            isinstance(source_content, dict) and
                            all(isinstance(v, str) for v in source_content.values()) and
                            not any("." in k for k in source_content.keys())
                        )
                    
                    if is_flat_format:
                        # For flat formats like .po, the key itself might BE the text to translate
                        # This is common when msgid is used as the key
                        # Filter empty strings
                        if key_path.strip() == "":
                            empty_key_paths.append((key_path, [key_path]))
                        else:
                            texts_to_translate.append(key_path)
                            key_paths_list.append(key_path)
                            key_parts_list.append([key_path])
                            print(
                                f"DEBUG: ✓ Added '{key_path}' to translation queue (flat format - key as text)"
                            )
                    else:
                        # For nested formats (TypeScript, JSON, YAML), if key not found in source,
                        # set empty string (key will be created in target file with empty value)
                        empty_key_paths.append((key_path, key_parts))
                        print(
                            f"DEBUG: ⚠ Key '{key_path}' not found in source, setting empty string (nested format)"
                        )

        # Set empty strings in the result
        for key_path, key_parts in empty_key_paths:
            if len(key_parts) == 1:
                updated_content[key_parts[0]] = ""
            else:
                set_nested_value(updated_content, key_parts, "")

        print(f"DEBUG: Final translation queue size: {len(texts_to_translate)}")

        if not texts_to_translate:
            print("DEBUG: No texts to translate, returning original target content")
            return updated_content

        # Use BatchProcessor for batch translation
        batch_processor = self._get_batch_processor()

        # Process batches
        provider = self.api_config.get("provider", "algebras-ai")
        translate_text_func = None if provider == "algebras-ai" else self.translate_text

        result = batch_processor.process(
            texts=texts_to_translate,
            source_lang=source_lang,
            target_lang=target_lang,
            ui_safe=ui_safe,
            glossary_id=glossary_id,
            on_batch_complete=None,  # We'll handle callback after mapping to keys
            translate_text_func=translate_text_func,
        )

        # Map translations back to key paths and update content
        # Also handle callbacks
        num_batches = (len(texts_to_translate) + self.batch_size - 1) // self.batch_size
        failed_indices = set()
        for batch_idx in result.failed_batches:
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(
                batch_start_idx + self.batch_size, len(texts_to_translate)
            )
            for idx in range(batch_start_idx, batch_end_idx):
                failed_indices.add(idx)

        for batch_idx in range(1, num_batches + 1):
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(
                batch_start_idx + self.batch_size, len(texts_to_translate)
            )

            batch_dict = {}
            for i in range(batch_start_idx, batch_end_idx):
                if i < len(result.translations) and i < len(key_parts_list):
                    source_text = texts_to_translate[i]
                    raw_translation = result.translations[i]
                    key_parts = key_parts_list[i]
                    key_path = key_paths_list[i]

                    # Skip failed translations
                    if i in failed_indices:
                        continue

                    # Apply normalization
                    normalized = self.string_normalizer.normalize(
                        source_text, raw_translation
                    )

                    # Update content with translated values
                    if len(key_parts) == 1:
                        # Flat format - set directly
                        updated_content[key_parts[0]] = normalized
                    elif len(key_parts) == 2 and key_parts[0].endswith('.__plurals__'):
                        # Handle plurals - reconstruct dictionary structure
                        plural_base_key = key_parts[0]  # e.g., "Quiz.timer_format.__plurals__"
                        plural_form = key_parts[1]      # e.g., "one" or "other"
                        
                        # Initialize plural dict if it doesn't exist
                        if plural_base_key not in updated_content:
                            updated_content[plural_base_key] = {}
                        elif not isinstance(updated_content[plural_base_key], dict):
                            # Convert to dict if it wasn't one already
                            updated_content[plural_base_key] = {}
                        
                        # Set the plural form
                        updated_content[plural_base_key][plural_form] = normalized
                        print(f"  ✓ Translated plural: {key_path}")
                    else:
                        # Nested format - use nested value setter
                        set_nested_value(updated_content, key_parts, normalized)
                    batch_dict[key_path] = normalized

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
            print(f"    Failed batches will keep existing values (or remain missing)")

        return updated_content

    def translate_outdated_keys_batch(
        self,
        source_content: Dict[str, Any],
        target_content: Dict[str, Any],
        outdated_keys: List[str],
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Translate outdated keys in batches to avoid overloading the API.

        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary
            outdated_keys: List of dot-notation keys that are outdated
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)

        Returns:
            Updated target content with translated outdated keys
        """
        # Resolve glossary_id from config if not provided
        if glossary_id is None:
            glossary_id = self.config.get_setting("api.glossary_id", "")

        # Make a deep copy of the target content to avoid modifying it directly
        updated_content = target_content.copy()

        # Get source language
        source_lang = self.config.get_source_language()

        # Collect texts and their corresponding key paths, filter empty strings
        texts_to_translate = []
        key_paths_list = []
        key_parts_list = []
        empty_key_paths = []  # Track keys with empty strings

        for key_path in outdated_keys:
            key_parts = key_path.split(".")
            source_value = get_nested_value(source_content, key_parts)

            if isinstance(source_value, str):
                # Filter empty strings - preserve them but don't send to API
                if source_value.strip() == "":
                    empty_key_paths.append((key_path, key_parts))
                else:
                    texts_to_translate.append(source_value)
                    key_paths_list.append(key_path)
                    key_parts_list.append(key_parts)

        # Set empty strings in the result
        for key_path, key_parts in empty_key_paths:
            if len(key_parts) == 1:
                updated_content[key_parts[0]] = ""
            else:
                set_nested_value(updated_content, key_parts, "")

        if not texts_to_translate:
            return updated_content

        # Use BatchProcessor for batch translation
        batch_processor = self._get_batch_processor()

        # Process batches
        provider = self.api_config.get("provider", "algebras-ai")
        translate_text_func = None if provider == "algebras-ai" else self.translate_text

        result = batch_processor.process(
            texts=texts_to_translate,
            source_lang=source_lang,
            target_lang=target_lang,
            ui_safe=ui_safe,
            glossary_id=glossary_id,
            on_batch_complete=None,  # We'll handle callback after mapping to keys
            translate_text_func=translate_text_func,
        )

        # Map translations back to key paths and update content
        # Also handle callbacks
        num_batches = (len(texts_to_translate) + self.batch_size - 1) // self.batch_size
        failed_indices = set()
        for batch_idx in result.failed_batches:
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(
                batch_start_idx + self.batch_size, len(texts_to_translate)
            )
            for idx in range(batch_start_idx, batch_end_idx):
                failed_indices.add(idx)

        for batch_idx in range(1, num_batches + 1):
            batch_start_idx = (batch_idx - 1) * self.batch_size
            batch_end_idx = min(
                batch_start_idx + self.batch_size, len(texts_to_translate)
            )

            batch_dict = {}
            for i in range(batch_start_idx, batch_end_idx):
                if i < len(result.translations) and i < len(key_parts_list):
                    source_text = texts_to_translate[i]
                    raw_translation = result.translations[i]
                    key_parts = key_parts_list[i]
                    key_path = key_paths_list[i]

                    # Skip failed translations
                    if i in failed_indices:
                        continue

                    # Apply normalization
                    normalized = self.string_normalizer.normalize(
                        source_text, raw_translation
                    )

                    # Update content with translated values
                    if len(key_parts) == 1:
                        # Flat format - set directly
                        updated_content[key_parts[0]] = normalized
                    elif len(key_parts) == 2 and key_parts[0].endswith('.__plurals__'):
                        # Handle plurals - reconstruct dictionary structure
                        plural_base_key = key_parts[0]  # e.g., "Quiz.timer_format.__plurals__"
                        plural_form = key_parts[1]      # e.g., "one" or "other"
                        
                        # Initialize plural dict if it doesn't exist
                        if plural_base_key not in updated_content:
                            updated_content[plural_base_key] = {}
                        elif not isinstance(updated_content[plural_base_key], dict):
                            # Convert to dict if it wasn't one already
                            updated_content[plural_base_key] = {}
                        
                        # Set the plural form
                        updated_content[plural_base_key][plural_form] = normalized
                        print(f"  ✓ Translated plural: {key_path}")
                    else:
                        # Nested format - use nested value setter
                        set_nested_value(updated_content, key_parts, normalized)
                    batch_dict[key_path] = normalized

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
            print(f"    Failed batches will keep existing values")

        return updated_content

    def _update_xliff_targets(
        self, xliff_content: Dict[str, Any], translated_strings: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Update XLIFF target elements with translated strings.

        Args:
            xliff_content: Original XLIFF content
            translated_strings: Dictionary of translated strings

        Returns:
            Updated XLIFF content with target elements
        """
        updated_content = xliff_content.copy()

        if "files" in updated_content:
            for file_data in updated_content["files"]:
                if "trans-units" in file_data:
                    for unit in file_data["trans-units"]:
                        if "id" in unit and unit["id"] in translated_strings:
                            unit["target"] = translated_strings[unit["id"]]

        return updated_content
