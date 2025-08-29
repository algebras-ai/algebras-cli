"""
Configuration module for Algebras CLI
"""

import os
import yaml
import glob
import click
from colorama import Fore
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
    
    def detect_languages_from_files(self, verbose: bool = False) -> List[str]:
        """
        Detect languages from existing locale files.
        
        Args:
            verbose: Whether to print verbose debug information
            
        Returns:
            List of detected language codes
        """
        languages = set()
        languages.add("en")  # Always include English as default
        
        if verbose:
            click.echo(f"{Fore.BLUE}Detecting languages from files...{Fore.RESET}")
        
        # Check common locale file patterns
        patterns = [
            "src/locales/*.json",
            "locales/*.json",
            "src/i18n/*.json",
            "i18n/*.json",
            "translations/*.json",
            "src/translations/*.json",
            "locale/**/*.json",
            "src/locale/**/*.json",
            "messages/*.json",  # Add support for Next.js messages directory
            "src/messages/*.json",
            "app/messages/*.json",
            "**/messages/*.json"  # More recursive search for messages directory
        ]
        
        detected_files = []
        
        for pattern in patterns:
            files = glob.glob(pattern, recursive=True)
            for file_path in files:
                detected_files.append(file_path)
                # Extract language from filename patterns
                basename = os.path.basename(file_path)
                dirname = os.path.dirname(file_path)
                
                # Check for common language code patterns
                if basename in ["en.json", "fr.json", "es.json", "de.json", "ru.json", "ch.json", "ua.json"]:
                    # e.g. en.json -> en
                    lang_code = basename.split(".")[0]
                    languages.add(lang_code)
                    if verbose:
                        click.echo(f"  Detected language {lang_code} from file {file_path}")
                elif "." in basename:
                    name_parts = basename.split(".")
                    if len(name_parts) >= 3:  # e.g. messages.en.json
                        lang_code = name_parts[-2]
                        # Simple validation for common language codes
                        if len(lang_code) == 2:  # Most language codes are 2 chars
                            languages.add(lang_code)
                            if verbose:
                                click.echo(f"  Detected language {lang_code} from file {file_path}")
                
                # Check for language in directory path
                if "/locales/" in dirname or "\\locales\\" in dirname:
                    parts = dirname.split(os.path.sep)
                    for i, part in enumerate(parts):
                        if part == "locales" and i < len(parts) - 1:
                            lang_part = parts[i+1]
                            if len(lang_part) == 2:  # Most language codes are 2 chars
                                languages.add(lang_part)
                                if verbose:
                                    click.echo(f"  Detected language {lang_part} from directory structure in {file_path}")
                
                # Check for messages directory pattern (e.g., messages/en.json)
                if "/messages/" in dirname or "\\messages\\" in dirname or os.path.basename(dirname) == "messages":
                    # For files directly in a messages directory, the basename is likely the language code
                    if "." in basename:
                        lang_code = basename.split(".")[0]
                        # Basic validation: length is 2 or in known language codes
                        if len(lang_code) == 2 or lang_code in ["en", "es", "fr", "de", "zh", "ja", "ko", "ru", "pt", "it", "ar", "hi", "bn", "mn"]:
                            languages.add(lang_code)
                            if verbose:
                                click.echo(f"  Detected language {lang_code} from messages directory in {file_path}")
        
        if verbose:
            if detected_files:
                click.echo(f"{Fore.GREEN}Found {len(detected_files)} locale files:{Fore.RESET}")
                for file in detected_files[:10]:  # Show first 10 files
                    click.echo(f"  - {file}")
                if len(detected_files) > 10:
                    click.echo(f"  ... and {len(detected_files) - 10} more")
            else:
                click.echo(f"{Fore.YELLOW}No locale files found. Using default language (en).{Fore.RESET}")
            
            click.echo(f"{Fore.GREEN}Detected languages: {', '.join(sorted(list(languages)))}{Fore.RESET}")
        
        return sorted(list(languages))
    
    def create_default(self) -> None:
        """Create a default configuration file."""
        if self.exists():
            return
        
        # Detect languages from existing files
        detected_languages = self.detect_languages_from_files()
        
        # Make sure we have at least English
        if not detected_languages:
            detected_languages = ["en"]
        
        self.data = {
            "languages": detected_languages,
            "path_rules": [
                "**/*.json",  # JSON files
                "**/*.yaml",  # YAML files
                "**/*.xml",   # Android XML localization files
                "**/*.strings",  # iOS strings localization files
                "!**/node_modules/**",  # Exclude node_modules directory
                "!**/build/**",  # Exclude build directory
            ],
            "api": {
                "provider": "algebras-ai",  # Default provider
                "model": "gpt-4",     # Default model (for OpenAI)
                # Provider options include: "openai", "algebras-ai"
                "normalize_strings": True,  # Default to normalize escaped characters
            },
            "batch_size": 5,  # Default batch size
            "max_parallel_batches": 5  # Default max parallel batches
        }
        
        self.save()
    
    def get_languages(self) -> List[str]:
        """Get the list of languages."""
        if not self.data:
            if not self.exists():
                return []
            self.load()
        
        return self.data.get("languages", [])
    
    def get_source_language(self) -> str:
        """Get the source language. Defaults to the first language in the list if not specified."""
        if not self.data:
            if not self.exists():
                return "en"
            self.load()
        
        # Explicitly check for source_language in the config and prioritize it
        if "source_language" in self.data:
            return self.data["source_language"]
            
        # If no explicit source_language, return the first language or default to "en"
        languages = self.get_languages()
        return languages[0] if languages else "en"
    
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
    
    def has_setting(self, key: str) -> bool:
        """Check if a setting exists in the configuration."""
        if not self.data:
            if not self.exists():
                return False
            self.load()
        
        return key in self.data
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting from the configuration. Supports dot notation for nested keys."""
        if not self.data:
            if not self.exists():
                return default
            self.load()
        
        # Handle nested keys using dot notation
        if "." in key:
            keys = key.split(".")
            current = self.data
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return default
            return current
        
        return self.data.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting in the configuration. Supports dot notation for nested keys."""
        if not self.data:
            self.load()
        
        # Handle nested keys using dot notation
        if "." in key:
            keys = key.split(".")
            current = self.data
            
            # Navigate to the parent of the final key, creating nested dicts as needed
            for k in keys[:-1]:
                if k not in current or not isinstance(current[k], dict):
                    current[k] = {}
                current = current[k]
            
            # Set the final key
            current[keys[-1]] = value
        else:
            self.data[key] = value
        
        self.save() 