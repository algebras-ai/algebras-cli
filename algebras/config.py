"""
Configuration module for Algebras CLI
"""

import os
import yaml
import glob
from typing import List, Dict, Any, Optional


class Config:
    """Configuration class for Algebras CLI."""
    
    CONFIG_FILE = ".algebras.config"
    
    def __init__(self):
        self.config_path = os.path.join(os.getcwd(), self.CONFIG_FILE)
        self.data = {}
    
    def exists(self) -> bool:
        """Check if the configuration file exists."""
        return os.path.exists(self.config_path)
    
    def load(self) -> Dict[str, Any]:
        """Load the configuration file."""
        if not self.exists():
            raise FileNotFoundError(f"Configuration file not found. Run 'algebras init' to create one.")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f) or {}
        
        return self.data
    
    def save(self) -> None:
        """Save the configuration file."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)
    
    def detect_languages_from_files(self) -> List[str]:
        """
        Detect languages from existing locale files.
        
        Returns:
            List of detected language codes
        """
        languages = set()
        languages.add("en")  # Always include English as default
        
        # Check common locale file patterns
        patterns = [
            "src/locales/*.json",
            "locales/*.json",
            "src/i18n/*.json",
            "i18n/*.json",
            "translations/*.json",
            "src/translations/*.json",
            "locale/**/*.json",
            "src/locale/**/*.json"
        ]
        
        for pattern in patterns:
            for file_path in glob.glob(pattern, recursive=True):
                # Extract language from filename patterns
                basename = os.path.basename(file_path)
                dirname = os.path.dirname(file_path)
                
                # Check for common language code patterns
                if basename in ["en.json", "fr.json", "es.json", "de.json", "ru.json", "ch.json", "ua.json"]:
                    # e.g. en.json -> en
                    lang_code = basename.split(".")[0]
                    languages.add(lang_code)
                elif "." in basename:
                    name_parts = basename.split(".")
                    if len(name_parts) >= 3:  # e.g. messages.en.json
                        lang_code = name_parts[-2]
                        # Simple validation for common language codes
                        if len(lang_code) == 2:  # Most language codes are 2 chars
                            languages.add(lang_code)
                
                # Check for language in directory path
                if "/locales/" in dirname or "\\locales\\" in dirname:
                    parts = dirname.split(os.path.sep)
                    for i, part in enumerate(parts):
                        if part == "locales" and i < len(parts) - 1:
                            lang_part = parts[i+1]
                            if len(lang_part) == 2:  # Most language codes are 2 chars
                                languages.add(lang_part)
        
        return sorted(list(languages))
    
    def create_default(self) -> None:
        """Create a default configuration file."""
        if self.exists():
            return
        
        # Detect languages from existing files
        detected_languages = self.detect_languages_from_files()
        
        self.data = {
            "languages": detected_languages,
            "path_rules": [
                "**/*.json",  # JSON files
                "**/*.yaml",  # YAML files
                "!**/node_modules/**",  # Exclude node_modules directory
                "!**/build/**",  # Exclude build directory
            ],
            "api": {
                "provider": "openai",
                "model": "gpt-4",
            }
        }
        
        self.save()
    
    def get_languages(self) -> List[str]:
        """Get the list of languages."""
        if not self.data:
            if not self.exists():
                return []
            self.load()
        
        return self.data.get("languages", [])
    
    def add_language(self, language: str) -> None:
        """Add a new language to the configuration."""
        if not self.data:
            self.load()
        
        languages = self.get_languages()
        if language in languages:
            return
        
        languages.append(language)
        self.data["languages"] = languages
        self.save()
    
    def get_path_rules(self) -> List[str]:
        """Get the list of path rules."""
        if not self.data:
            if not self.exists():
                return []
            self.load()
        
        return self.data.get("path_rules", [])
    
    def get_api_config(self) -> Dict[str, str]:
        """Get the API configuration."""
        if not self.data:
            if not self.exists():
                return {}
            self.load()
        
        return self.data.get("api", {}) 