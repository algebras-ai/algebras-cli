"""
Translation service using AI providers
"""

import os
import json
import yaml
import requests
from typing import Dict, Any, List, Optional
from openai import OpenAI

from algebras.config import Config
from algebras.utils.lang_validator import map_language_code


class Translator:
    """AI-powered translation service."""
    
    def __init__(self):
        self.config = Config()
        if not self.config.exists():
            raise FileNotFoundError("No Algebras configuration found. Run 'algebras init' first.")
        
        self.config.load()
        self.api_config = self.config.get_api_config()
        
        # Set up OpenAI client if available
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if openai_api_key:
            self.client = OpenAI(api_key=openai_api_key)
        else:
            self.client = None
        
    def translate_text(self, text: str, source_lang: str, target_lang: str, ui_safe: bool = False) -> str:
        """
        Translate a text from source language to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translation will not be longer than the original text
            
        Returns:
            Translated text
        """
        provider = self.api_config.get("provider", "openai")
        
        # Map language codes to ISO 2-letter format
        source_lang = map_language_code(source_lang)
        target_lang = map_language_code(target_lang)
        
        if provider == "openai":
            return self._translate_with_openai(text, source_lang, target_lang)
        elif provider == "algebras-ai":
            return self._translate_with_algebras_ai(text, source_lang, target_lang, ui_safe)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
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
    
    def _translate_with_algebras_ai(self, text: str, source_lang: str, target_lang: str, ui_safe: bool = False) -> str:
        """
        Translate text using Algebras AI API.
        
        Args:
            text: Text to translate
            source_lang: Source language code (already mapped to ISO 2-letter format, use 'auto' for automatic detection)
            target_lang: Target language code (already mapped to ISO 2-letter format)
            ui_safe: If True, ensures translation will be no more characters than original text
            
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
            "glossaryId": "",
            "prompt": "",
            "flag": "true" if ui_safe else "false"
        }
        
        try:
            print(data)
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
    
    def translate_file(self, file_path: str, target_lang: str, ui_safe: bool = False) -> Dict[str, Any]:
        """
        Translate a localization file to the target language.
        
        Args:
            file_path: Path to the localization file
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            
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
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
        
        # Assume the source language is the first language in the config
        source_lang = self.config.get_languages()[0]
        
        # Translate the content
        translated = self._translate_nested_dict(content, source_lang, target_lang, ui_safe)
        
        return translated
    
    def translate_missing_keys(self, source_content: Dict[str, Any], target_content: Dict[str, Any], 
                              missing_keys: List[str], target_lang: str, ui_safe: bool = False) -> Dict[str, Any]:
        """
        Translate only the missing keys in a target dictionary.
        
        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary (with missing keys)
            missing_keys: List of dot-notation keys that are missing
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            
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
                translated_value = self.translate_text(source_value, source_lang, target_lang, ui_safe)
                
                # Update the target content with the translated value
                self._set_nested_value(updated_content, key_parts, translated_value)
        
        return updated_content
    
    def translate_outdated_keys(self, source_content: Dict[str, Any], target_content: Dict[str, Any],
                               outdated_keys: List[str], target_lang: str, ui_safe: bool = False) -> Dict[str, Any]:
        """
        Translate only the outdated keys in a target dictionary.
        
        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary
            outdated_keys: List of dot-notation keys that are outdated
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            
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
                translated_value = self.translate_text(source_value, source_lang, target_lang, ui_safe)
                
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
    
    def _translate_nested_dict(self, data: Dict[str, Any], source_lang: str, target_lang: str, ui_safe: bool = False) -> Dict[str, Any]:
        """
        Recursively translate a nested dictionary.
        
        Args:
            data: Dictionary to translate
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensures translation will be no more characters than original text
            
        Returns:
            Translated dictionary
        """
        result = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._translate_nested_dict(value, source_lang, target_lang, ui_safe)
            elif isinstance(value, str):
                result[key] = self.translate_text(value, source_lang, target_lang, ui_safe)
            else:
                result[key] = value
        
        return result 