"""
Translation service using AI providers
"""

import os
import json
import yaml
import requests
import hashlib
import pickle
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from functools import lru_cache
from openai import OpenAI
import re
import time

import click
from colorama import Fore

from algebras.config import Config
from algebras.utils.lang_validator import map_language_code
from algebras.utils.ts_handler import read_ts_translation_file
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.ios_strings_handler import read_ios_strings_file
from algebras.utils.ios_stringsdict_handler import read_ios_stringsdict_file, extract_translatable_strings
from algebras.utils.po_handler import read_po_file


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
                with open(self._cache_file, 'rb') as f:
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
            
            with open(self._cache_file, 'wb') as f:
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
            "cache_file": self._cache_file
        }


class Translator:
    """AI-powered translation service."""
    
    def __init__(self):
        self.config = Config()
        if not self.config.exists():
            raise FileNotFoundError("No Algebras configuration found. Run 'algebras init' first.")
        
        self.config.load()
        self.api_config = self.config.get_api_config()
        
        # Get batch size from environment or config, default to 20
        self.batch_size = int(os.environ.get("ALGEBRAS_BATCH_SIZE", 20))
        if self.config.has_setting("batch_size"):
            self.batch_size = int(self.config.get_setting("batch_size"))
        
        # Get max parallel batches from config, default to 5
        self.max_parallel_batches = int(os.environ.get("ALGEBRAS_MAX_PARALLEL_BATCHES", 5))
        if self.config.has_setting("max_parallel_batches"):
            self.max_parallel_batches = int(self.config.get_setting("max_parallel_batches"))
        
        # Set up OpenAI client if available
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if openai_api_key:
            self.client = OpenAI(api_key=openai_api_key)
        else:
            self.client = None
            
        # Initialize the translation cache
        self.cache = TranslationCache()
        
        # Initialize custom prompt
        self.custom_prompt = ""
        
    def set_custom_prompt(self, prompt: str) -> None:
        """
        Set a custom prompt to be used for translations.
        
        Args:
            prompt: Custom prompt text to use for translation
        """
        self.custom_prompt = prompt
        
    def normalize_translation_string(self, source_text: str, translated_text: str) -> str:
        """
        Normalize a translated string by removing escaped characters if they weren't
        present in the source text.
        
        Args:
            source_text: The original source text
            translated_text: The translated text from the API
            
        Returns:
            Normalized translated text
        """
        # Check if normalization is enabled
        if not self.config.get_setting("api.normalize_strings", True):
            return translated_text
        
        # Common escaped characters to normalize
        escape_mappings = {
            "\\'": "'",   # Escaped apostrophe
            '\\"': '"',   # Escaped quote
            "\\\\": "\\", # Escaped backslash
            "\\n": "\n",  # Escaped newline (keep as actual newline)
            "\\t": "\t",  # Escaped tab (keep as actual tab)
            "\\r": "\r",  # Escaped carriage return (keep as actual carriage return)
        }
        
        # Only normalize if the source text doesn't contain these escaped characters
        normalized_text = translated_text
        for escaped_char, unescaped_char in escape_mappings.items():
            # Only normalize if the source text doesn't contain the escaped version
            if escaped_char not in source_text and escaped_char in normalized_text:
                normalized_text = normalized_text.replace(escaped_char, unescaped_char)
        
        return normalized_text
        
    def translate_text(self, text: str, source_lang: str, target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> str:
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
        cache_key = self.cache.get_cache_key(text, source_lang, target_lang, ui_safe, self.custom_prompt)
        cached_translation = self.cache.get(cache_key)
        if cached_translation:
            print(f"Cache hit: Using cached translation for '{text[:30]}...' ({source_lang} → {target_lang})")
            return cached_translation
        
        print(f"Cache miss: Translating '{text[:30]}...' ({source_lang} → {target_lang})")
        provider = self.api_config.get("provider", "openai")
        
        if provider == "openai":
            translation = self._translate_with_openai(text, source_lang, target_lang)
        elif provider == "algebras-ai":
            translation = self._translate_with_algebras_ai(text, source_lang, target_lang, ui_safe, glossary_id)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Apply normalization to the translation
        translation = self.normalize_translation_string(text, translation)
        
        # Update cache with new translation
        self.cache.set(cache_key, translation)
        print(f"Added translation to cache: '{text[:30]}...' ({source_lang} → {target_lang})")
        
        return translation
    
    def _translate_with_openai(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text using OpenAI API.
        
        Args:
            text: Text to translate
            source_lang: Source language code (already mapped to ISO 2-letter format)
            target_lang: Target language code (already mapped to ISO 2-letter format)
            
        Returns:
            Translated text
        """
        model = self.api_config.get("model", "gpt-4")
        
        if not self.client:
            raise ValueError("OpenAI API key not found. Set the OPENAI_API_KEY environment variable.")
        
        # Build the prompt with custom prompt if provided
        base_prompt = f"""
        Translate the following text from {source_lang} to {target_lang}.
        Preserve all formatting, variables, and placeholders.
        Only return the translated text, nothing else.
        """
        
        if self.custom_prompt:
            prompt = f"""
        {self.custom_prompt}
        
        Translate the following text from {source_lang} to {target_lang}.
        Preserve all formatting, variables, and placeholders.
        Only return the translated text, nothing else.
        
        Text to translate:
        {text}
        """
        else:
            prompt = f"""
        Translate the following text from {source_lang} to {target_lang}.
        Preserve all formatting, variables, and placeholders.
        Only return the translated text, nothing else.
        
        Text to translate:
        {text}
        """
        
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional translator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        return response.choices[0].message.content.strip()
    
    def _translate_with_algebras_ai(self, text: str, source_lang: str, target_lang: str, ui_safe: bool = False, glossary_id: str = "") -> str:
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
        """
        api_key = os.environ.get("ALGEBRAS_API_KEY")
        if not api_key:
            raise ValueError("Algebras API key not found. Set the ALGEBRAS_API_KEY environment variable.")
        
        url = "https://platform.algebras.ai/api/v1/translation/translate"
        headers = {
            "accept": "application/json",
            "X-Api-Key": api_key
        }
        
        # Use 'auto' if source_lang is not specified or is 'auto'
        source_lang_value = source_lang if source_lang and source_lang != "auto" else "auto"
        
        data = {
            "sourceLanguage": source_lang_value,
            "targetLanguage": target_lang,
            "textContent": text,
            "fileContent": "",
            "glossaryId": glossary_id,
            "prompt": self.custom_prompt,
            "flag": "true" if ui_safe else "false"
        }
        
        try:
            response = requests.post(url, headers=headers, files={
                "sourceLanguage": (None, data["sourceLanguage"]),
                "targetLanguage": (None, data["targetLanguage"]),
                "textContent": (None, data["textContent"]),
                "fileContent": (None, data["fileContent"]),
                "glossaryId": (None, data["glossaryId"]),
                "prompt": (None, data["prompt"]),
                "flag": (None, data["flag"])
            })
            
            if response.status_code == 200:
                result = response.json()
                return result.get("data", "")
            else:
                error_msg = f"Error from Algebras AI API: {response.status_code} - {response.text}"
                raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"Failed to translate with Algebras AI: {str(e)}")
    
    def translate_file(self, file_path: str, target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
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
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
        
        # Assume the source language is the first language in the config
        source_lang = self.config.get_languages()[0]
        
        # Translate the content
        translated = self._translate_nested_dict(content, source_lang, target_lang, ui_safe, glossary_id)
        
        return translated
    
    def translate_missing_keys(self, source_content: Dict[str, Any], target_content: Dict[str, Any], 
                              missing_keys: List[str], target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Translate only the missing keys in a target dictionary.
        
        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary (with missing keys)
            missing_keys: List of dot-notation keys that are missing
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            
        Returns:
            Updated target content with translated missing keys
        """
        # Make a deep copy of the target content to avoid modifying it directly
        updated_content = target_content.copy()
        
        # Get source language
        source_lang = self.config.get_source_language()
        
        # Translate each missing key and update the target content
        for key_path in missing_keys:
            # Split the key path into individual parts
            key_parts = key_path.split('.')
            
            # Get the value from the source content
            source_value = self._get_nested_value(source_content, key_parts)
            
            if isinstance(source_value, str):
                # Translate the value
                translated_value = self.translate_text(source_value, source_lang, target_lang, ui_safe, glossary_id)
                
                # Update the target content with the translated value
                self._set_nested_value(updated_content, key_parts, translated_value)
        
        return updated_content
    
    def translate_outdated_keys(self, source_content: Dict[str, Any], target_content: Dict[str, Any],
                               outdated_keys: List[str], target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Translate only the outdated keys in a target dictionary.
        
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
        # Make a deep copy of the target content to avoid modifying it directly
        updated_content = target_content.copy()
        
        # Get source language
        source_lang = self.config.get_source_language()
        
        # Translate each outdated key and update the target content
        for key_path in outdated_keys:
            # Split the key path into individual parts
            key_parts = key_path.split('.')
            
            # Get the value from the source content
            source_value = self._get_nested_value(source_content, key_parts)
            
            if isinstance(source_value, str):
                # Translate the value
                translated_value = self.translate_text(source_value, source_lang, target_lang, ui_safe, glossary_id)
                
                # Update the target content with the translated value
                self._set_nested_value(updated_content, key_parts, translated_value)
        
        return updated_content
    
    def _get_nested_value(self, data: Dict[str, Any], key_parts: List[str]) -> Any:
        """
        Get a value from a nested dictionary using a list of key parts.
        
        Args:
            data: Dictionary to get value from
            key_parts: List of key parts representing a dot-notation path
            
        Returns:
            Value at the specified path
        """
        current = data
        for part in key_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def _set_nested_value(self, data: Dict[str, Any], key_parts: List[str], value: Any) -> None:
        """
        Set a value in a nested dictionary using a list of key parts.
        Will create intermediate dictionaries if they don't exist.
        
        Args:
            data: Dictionary to update
            key_parts: List of key parts representing a dot-notation path
            value: Value to set
        """
        current = data
        for i, part in enumerate(key_parts):
            if i == len(key_parts) - 1:
                # Last part, set the value
                current[part] = value
            else:
                # Intermediate part, create dict if needed
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
    
    def _translate_with_algebras_ai_batch(self, texts: List[str], source_lang: str, target_lang: str, ui_safe: bool = False, glossary_id: str = "") -> List[str]:
        """
        Translate multiple texts using Algebras AI batch API.
        
        Args:
            texts: List of texts to translate
            source_lang: Source language code (already mapped to ISO 2-letter format, use 'auto' for automatic detection)
            target_lang: Target language code (already mapped to ISO 2-letter format)
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation
            
        Returns:
            List of translated texts
        """
        api_key = os.environ.get("ALGEBRAS_API_KEY")
        if not api_key:
            raise ValueError("Algebras API key not found. Set the ALGEBRAS_API_KEY environment variable.")
        
        url = "https://platform.algebras.ai/api/v1/translation/translate-batch"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": api_key
        }
        
        # Use 'auto' if source_lang is not specified or is 'auto'
        source_lang_value = source_lang if source_lang and source_lang != "auto" else "auto"
        
        data = {
            "texts": texts,
            "sourceLanguage": source_lang_value,
            "targetLanguage": target_lang,
            "prompt": self.custom_prompt,
            "flag": ui_safe
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                
                # Handle the correct API response format
                if "data" in result and "translations" in result["data"]:
                    # Extract translations from the nested structure
                    translation_items = result["data"]["translations"]
                    # Sort by index to maintain order and extract content
                    translation_items.sort(key=lambda x: x.get("index", 0))
                    translations = [item.get("content", "") for item in translation_items]
                else:
                    # Fallback to old format if structure is different
                    translations = result.get("data", [])
                
                # Ensure we have the same number of translations as input texts
                if len(translations) != len(texts):
                    raise Exception(f"Expected {len(texts)} translations, but got {len(translations)}")
                
                # Apply normalization to each translation
                normalized_translations = []
                for i, translation in enumerate(translations):
                    normalized_translation = self.normalize_translation_string(texts[i], translation)
                    normalized_translations.append(normalized_translation)
                
                return normalized_translations
            else:
                error_msg = f"Error from Algebras AI batch API: {response.status_code} - {response.text}"
                raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"Failed to translate batch with Algebras AI: {str(e)}")
    
    def _translate_nested_dict(self, data: Dict[str, Any], source_lang: str, target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Recursively translate a nested dictionary.
        
        Args:
            data: Dictionary to translate
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            
        Returns:
            Translated dictionary
        """
        # Resolve glossary_id from config if not provided
        if glossary_id is None:
            glossary_id = self.config.get_setting("api.glossary_id", "")
        
        # Collect all string values that need translation
        string_items = []
        paths = []
        
        def collect_strings(current_data, current_path=None):
            if current_path is None:
                current_path = []
                
            for key, value in current_data.items():
                path = current_path + [key]
                if isinstance(value, dict):
                    collect_strings(value, path)
                elif isinstance(value, str):
                    string_items.append(value)
                    paths.append(path)
        
        # Collect all strings that need translation
        collect_strings(data)
        
        # Split into batches
        total_strings = len(string_items)
        num_batches = (total_strings + self.batch_size - 1) // self.batch_size
        
        print(f"Processing {total_strings} text items in {num_batches} batches (batch size: {self.batch_size})")
        
        # Translate in batches
        translated_values = {}
        provider = self.api_config.get("provider", "openai")
        
        if provider == "algebras-ai":
            # Use parallel batch processing for Algebras AI
            print(f"Using parallel batch processing with {self.max_parallel_batches} concurrent batches")
            
            # Create batch data
            batches = []
            for i in range(0, total_strings, self.batch_size):
                batch = string_items[i:i + self.batch_size]
                batch_paths = paths[i:i + self.batch_size]
                batch_idx = i // self.batch_size + 1
                batches.append((batch, batch_paths, batch_idx))
            
            # Process batches in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_batches) as executor:
                # Submit all batch translation tasks
                future_to_batch = {}
                for batch, batch_paths, batch_idx in batches:
                    future = executor.submit(
                        self._translate_with_algebras_ai_batch,
                        batch, source_lang, target_lang, ui_safe, glossary_id
                    )
                    future_to_batch[future] = (batch, batch_paths, batch_idx)
                
                # Collect results as they complete
                completed_batches = 0
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch, batch_paths, batch_idx = future_to_batch[future]
                    completed_batches += 1
                    
                    try:
                        translated_batch = future.result()
                        
                        # Store results with their paths
                        for j, translated_text in enumerate(translated_batch):
                            path_key = tuple(batch_paths[j])  # Convert list to tuple for dict key
                            translated_values[path_key] = translated_text
                        
                        print(f"Completed batch {batch_idx}/{num_batches} ({completed_batches}/{num_batches} total completed)")
                        for j in range(len(batch)):
                            print(f"  ✓ Translated: {'.'.join(str(p) for p in batch_paths[j])}")
                    
                    except Exception as e:
                        print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                        # Re-raise the exception instead of falling back to individual translations
                        raise e
        else:
            # Use sequential batch processing for other providers (like OpenAI)
            for i in range(0, total_strings, self.batch_size):
                batch = string_items[i:i + self.batch_size]
                batch_paths = paths[i:i + self.batch_size]
                batch_idx = i // self.batch_size + 1
                
                print(f"Processing batch {batch_idx}/{num_batches} ({len(batch)} items)")
                
                try:
                    # Use individual translations for other providers (like OpenAI)
                    # Use ThreadPoolExecutor for parallel processing within the batch
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                        # Create translation tasks
                        futures = {}
                        for j, text in enumerate(batch):
                            future = executor.submit(
                                self.translate_text,
                                text,
                                source_lang,
                                target_lang,
                                ui_safe,
                                glossary_id
                            )
                            futures[j] = future
                        
                        # Collect results
                        for j, future in futures.items():
                            try:
                                translated_text = future.result()
                                path_key = tuple(batch_paths[j])  # Convert list to tuple for dict key
                                translated_values[path_key] = translated_text
                                print(f"  ✓ Translated: {'.'.join(str(p) for p in batch_paths[j])}")
                            except Exception as e:
                                print(f"  ✗ Error translating {batch[j]}: {str(e)}")
                    
                    print(f"Completed batch {batch_idx}/{num_batches}")
                except Exception as e:
                    print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                    # Re-raise the exception instead of falling back to individual translations
                    raise e
        
        # Build the result dictionary with translations
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
                        # Fallback to direct translation if not in batch results
                        dest_data[key] = self.translate_text(value, source_lang, target_lang, ui_safe, glossary_id)
                else:
                    dest_data[key] = value
        
        # Build the translated dictionary
        build_result(data, result)
        
        return result
    
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
            cache_key = self.cache.get_cache_key(text, source_lang, source_lang, False, "")
            if not self.cache.get(cache_key):
                self.cache.set(cache_key, text)  # Set identity translation (same language)
                loaded_count += 1
        
        print(f"Preloaded {loaded_count} items into translation cache")
        return loaded_count
    
    def translate_missing_keys_batch(self, source_content: Dict[str, Any], target_content: Dict[str, Any],
                                    missing_keys: List[str], target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Translate missing keys in batches to avoid overloading the API.
        
        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary (with missing keys)
            missing_keys: List of dot-notation keys that are missing
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation (if None, will check config for api.glossary_id)
            
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
        
        # Collect texts and their corresponding key paths
        texts_to_translate = []
        key_paths_list = []
        key_parts_list = []
        
        for key_path in missing_keys:
            key_parts = key_path.split('.')
            source_value = self._get_nested_value(source_content, key_parts)
            
            if isinstance(source_value, str):
                texts_to_translate.append(source_value)
                key_paths_list.append(key_path)
                key_parts_list.append(key_parts)
        
        if not texts_to_translate:
            return updated_content
        
        # Split into batches
        total_keys = len(texts_to_translate)
        num_batches = (total_keys + self.batch_size - 1) // self.batch_size
        
        print(f"Processing {total_keys} missing keys in {num_batches} batches (batch size: {self.batch_size})")
        
        provider = self.api_config.get("provider", "openai")
        
        if provider == "algebras-ai":
            # Use parallel batch processing for Algebras AI
            print(f"Using parallel batch processing with {self.max_parallel_batches} concurrent batches")
            
            # Create batch data
            batches = []
            for i in range(0, total_keys, self.batch_size):
                batch_texts = texts_to_translate[i:i + self.batch_size]
                batch_key_paths = key_paths_list[i:i + self.batch_size]
                batch_key_parts = key_parts_list[i:i + self.batch_size]
                batch_idx = i // self.batch_size + 1
                batches.append((batch_texts, batch_key_paths, batch_key_parts, batch_idx))
            
            # Process batches in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_batches) as executor:
                # Submit all batch translation tasks
                future_to_batch = {}
                for batch_texts, batch_key_paths, batch_key_parts, batch_idx in batches:
                    future = executor.submit(
                        self._translate_with_algebras_ai_batch,
                        batch_texts, source_lang, target_lang, ui_safe, glossary_id
                    )
                    future_to_batch[future] = (batch_texts, batch_key_paths, batch_key_parts, batch_idx)
                
                # Collect results as they complete
                completed_batches = 0
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch_texts, batch_key_paths, batch_key_parts, batch_idx = future_to_batch[future]
                    completed_batches += 1
                    
                    try:
                        translated_batch = future.result()
                        
                        # Update content with translated values
                        for j, translated_value in enumerate(translated_batch):
                            self._set_nested_value(updated_content, batch_key_parts[j], translated_value)
                        
                        print(f"Completed batch {batch_idx}/{num_batches} ({completed_batches}/{num_batches} total completed)")
                        for j in range(len(batch_texts)):
                            print(f"  ✓ Translated: {batch_key_paths[j]}")
                    
                    except Exception as e:
                        print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                        # Re-raise the exception instead of falling back to individual translations
                        raise e
        else:
            # Use sequential batch processing for other providers (like OpenAI)
            for i in range(0, total_keys, self.batch_size):
                batch_texts = texts_to_translate[i:i + self.batch_size]
                batch_key_paths = key_paths_list[i:i + self.batch_size]
                batch_key_parts = key_parts_list[i:i + self.batch_size]
                batch_idx = i // self.batch_size + 1
                
                print(f"Processing batch {batch_idx}/{num_batches} ({len(batch_texts)} keys)")
                
                try:
                    # Use individual translations for other providers (like OpenAI)
                    # Use ThreadPoolExecutor for parallel processing within each batch
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                        # Create tasks for each key in the batch
                        futures = {}
                        for j, text in enumerate(batch_texts):
                            future = executor.submit(
                                self.translate_text,
                                text,
                                source_lang,
                                target_lang,
                                ui_safe,
                                glossary_id
                            )
                            futures[j] = future
                        
                        # Collect results and update content
                        for j, future in futures.items():
                            try:
                                translated_value = future.result()
                                self._set_nested_value(updated_content, batch_key_parts[j], translated_value)
                                print(f"  ✓ Translated: {batch_key_paths[j]}")
                            except Exception as e:
                                print(f"  ✗ Error translating {batch_key_paths[j]}: {str(e)}")
                    
                    print(f"Completed batch {batch_idx}/{num_batches}")
                except Exception as e:
                    print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                    # Re-raise the exception instead of falling back to individual translations
                    raise e
        
        return updated_content
    
    def translate_outdated_keys_batch(self, source_content: Dict[str, Any], target_content: Dict[str, Any],
                                     outdated_keys: List[str], target_lang: str, ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
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
        
        # Collect texts and their corresponding key paths
        texts_to_translate = []
        key_paths_list = []
        key_parts_list = []
        
        for key_path in outdated_keys:
            key_parts = key_path.split('.')
            source_value = self._get_nested_value(source_content, key_parts)
            
            if isinstance(source_value, str):
                texts_to_translate.append(source_value)
                key_paths_list.append(key_path)
                key_parts_list.append(key_parts)
        
        if not texts_to_translate:
            return updated_content
        
        # Split into batches
        total_keys = len(texts_to_translate)
        num_batches = (total_keys + self.batch_size - 1) // self.batch_size
        
        print(f"Processing {total_keys} outdated keys in {num_batches} batches (batch size: {self.batch_size})")
        
        provider = self.api_config.get("provider", "openai")
        
        if provider == "algebras-ai":
            # Use parallel batch processing for Algebras AI
            print(f"Using parallel batch processing with {self.max_parallel_batches} concurrent batches")
            
            # Create batch data
            batches = []
            for i in range(0, total_keys, self.batch_size):
                batch_texts = texts_to_translate[i:i + self.batch_size]
                batch_key_paths = key_paths_list[i:i + self.batch_size]
                batch_key_parts = key_parts_list[i:i + self.batch_size]
                batch_idx = i // self.batch_size + 1
                batches.append((batch_texts, batch_key_paths, batch_key_parts, batch_idx))
            
            # Process batches in parallel using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_parallel_batches) as executor:
                # Submit all batch translation tasks
                future_to_batch = {}
                for batch_texts, batch_key_paths, batch_key_parts, batch_idx in batches:
                    future = executor.submit(
                        self._translate_with_algebras_ai_batch,
                        batch_texts, source_lang, target_lang, ui_safe, glossary_id
                    )
                    future_to_batch[future] = (batch_texts, batch_key_paths, batch_key_parts, batch_idx)
                
                # Collect results as they complete
                completed_batches = 0
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch_texts, batch_key_paths, batch_key_parts, batch_idx = future_to_batch[future]
                    completed_batches += 1
                    
                    try:
                        translated_batch = future.result()
                        
                        # Update content with translated values
                        for j, translated_value in enumerate(translated_batch):
                            self._set_nested_value(updated_content, batch_key_parts[j], translated_value)
                        
                        print(f"Completed batch {batch_idx}/{num_batches} ({completed_batches}/{num_batches} total completed)")
                        for j in range(len(batch_texts)):
                            print(f"  ✓ Translated: {batch_key_paths[j]}")
                    
                    except Exception as e:
                        print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                        # Re-raise the exception instead of falling back to individual translations
                        raise e
        else:
            # Use sequential batch processing for other providers (like OpenAI)
            for i in range(0, total_keys, self.batch_size):
                batch_texts = texts_to_translate[i:i + self.batch_size]
                batch_key_paths = key_paths_list[i:i + self.batch_size]
                batch_key_parts = key_parts_list[i:i + self.batch_size]
                batch_idx = i // self.batch_size + 1
                
                print(f"Processing batch {batch_idx}/{num_batches} ({len(batch_texts)} keys)")
                
                try:
                    # Use individual translations for other providers (like OpenAI)
                    # Use ThreadPoolExecutor for parallel processing within each batch
                    with concurrent.futures.ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                        # Create tasks for each key in the batch
                        futures = {}
                        for j, text in enumerate(batch_texts):
                            future = executor.submit(
                                self.translate_text,
                                text,
                                source_lang,
                                target_lang,
                                ui_safe,
                                glossary_id
                            )
                            futures[j] = future
                        
                        # Collect results and update content
                        for j, future in futures.items():
                            try:
                                translated_value = future.result()
                                self._set_nested_value(updated_content, batch_key_parts[j], translated_value)
                                print(f"  ✓ Translated: {batch_key_paths[j]}")
                            except Exception as e:
                                print(f"  ✗ Error translating {batch_key_paths[j]}: {str(e)}")
                    
                    print(f"Completed batch {batch_idx}/{num_batches}")
                except Exception as e:
                    print(f"  ✗ Error processing batch {batch_idx}: {str(e)}")
                    # Re-raise the exception instead of falling back to individual translations
                    raise e
        
        return updated_content 