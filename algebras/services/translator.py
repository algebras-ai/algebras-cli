"""
Translation service using AI providers
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional
import openai

from algebras.config import Config


class Translator:
    """AI-powered translation service."""
    
    def __init__(self):
        self.config = Config()
        if not self.config.exists():
            raise FileNotFoundError("No Algebras configuration found. Run 'algebras init' first.")
        
        self.config.load()
        self.api_config = self.config.get_api_config()
        
        # Set up OpenAI if available
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if openai_api_key:
            openai.api_key = openai_api_key
        
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
        
        if not openai.api_key:
            raise ValueError("OpenAI API key not found. Set the OPENAI_API_KEY environment variable.")
        
        prompt = f"""
        Translate the following text from {source_lang} to {target_lang}.
        Preserve all formatting, variables, and placeholders.
        Only return the translated text, nothing else.
        
        Text to translate:
        {text}
        """
        
        response = openai.ChatCompletion.create(
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