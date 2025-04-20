"""
Translation service using AI providers
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional
from openai import OpenAI

from algebras.config import Config


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
        
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate a text from source language to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text
        """
        provider = self.api_config.get("provider", "openai")
        
        if provider == "openai":
            return self._translate_with_openai(text, source_lang, target_lang)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _translate_with_openai(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text using OpenAI API.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
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
    
    def translate_file(self, file_path: str, target_lang: str) -> Dict[str, Any]:
        """
        Translate a localization file to the target language.
        
        Args:
            file_path: Path to the localization file
            target_lang: Target language code
            
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
        translated = self._translate_nested_dict(content, source_lang, target_lang)
        
        return translated
    
    def translate_missing_keys(self, source_content: Dict[str, Any], target_content: Dict[str, Any], 
                              missing_keys: List[str], target_lang: str) -> Dict[str, Any]:
        """
        Translate only the missing keys in a target dictionary.
        
        Args:
            source_content: Source language content as a dictionary
            target_content: Target language content as a dictionary (with missing keys)
            missing_keys: List of dot-notation keys that are missing
            target_lang: Target language code
            
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
                translated_value = self.translate_text(source_value, source_lang, target_lang)
                
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
    
    def _translate_nested_dict(self, data: Dict[str, Any], source_lang: str, target_lang: str) -> Dict[str, Any]:
        """
        Recursively translate a nested dictionary.
        
        Args:
            data: Dictionary to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated dictionary
        """
        result = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._translate_nested_dict(value, source_lang, target_lang)
            elif isinstance(value, str):
                result[key] = self.translate_text(value, source_lang, target_lang)
            else:
                result[key] = value
        
        return result 