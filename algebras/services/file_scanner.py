"""
File scanner for localization files
"""

import os
import glob
from typing import List, Dict, Set

from algebras.config import Config


class FileScanner:
    """Scanner for finding localization files in the project."""
    
    def __init__(self):
        self.config = Config()
        if not self.config.exists():
            raise FileNotFoundError("No Algebras configuration found. Run 'algebras init' first.")
        
        self.config.load()
        self.path_rules = self.config.get_path_rules()
    
    def find_localization_files(self) -> List[str]:
        """
        Find all localization files in the project based on path rules.
        
        Returns:
            List of file paths
        """
        include_patterns = []
        exclude_patterns = []
        
        # Add more specific patterns for locale files
        specific_locale_patterns = [
            "src/locales/*.json",
            "locales/*.json",
            "src/i18n/*.json",
            "i18n/*.json",
            "public/locales/*/*.json",  # Add support for public/locales/{lang}/common.json
            "public/locales/*/common.json"  # Specifically target common.json files
        ]
        
        # Separate include and exclude patterns
        for rule in self.path_rules:
            if rule.startswith("!"):
                exclude_patterns.append(rule[1:])
            else:
                include_patterns.append(rule)
        
        # Find all files matching specific locale patterns first
        all_files = set()
        for pattern in specific_locale_patterns:
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path):
                    all_files.add(os.path.normpath(file_path))
        
        # If no files found, fallback to general patterns
        if not all_files:
            for pattern in include_patterns:
                for file_path in glob.glob(pattern, recursive=True):
                    if os.path.isfile(file_path):
                        all_files.add(os.path.normpath(file_path))
        
        # Remove files matching exclude patterns
        for pattern in exclude_patterns:
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path) and os.path.normpath(file_path) in all_files:
                    all_files.remove(os.path.normpath(file_path))
        
        return sorted(list(all_files))
    
    def group_files_by_language(self) -> Dict[str, List[str]]:
        """
        Group localization files by language.
        
        Returns:
            Dictionary mapping language codes to lists of file paths
        """
        files = self.find_localization_files()
        
        # Make sure we have valid languages list (no False values)
        languages = [lang for lang in self.config.get_languages() if lang]
        
        # Get the source language from config
        source_language = self.config.get_source_language()
        
        # Special handling for public/locales/{lang}/common.json structure
        # This format is common in next-i18next and similar frameworks
        has_public_locales = any("public/locales/" in f for f in files)
        
        # Initialize result with all configured languages
        result = {lang: [] for lang in languages}
        assigned_files = set()
        
        # First pass: assign files with explicit language markers in folder structure
        for file_path in files:
            base_name = os.path.basename(file_path)
            directory = os.path.dirname(file_path)
            
            # Special handling for public/locales/{lang}/common.json structure
            if "public/locales/" in file_path or f"public{os.path.sep}locales{os.path.sep}" in file_path:
                parts = file_path.split(os.path.sep)
                locale_idx = -1
                
                # Find the index of "locales" in the path
                for i, part in enumerate(parts):
                    if part == "locales":
                        locale_idx = i
                        break
                
                # Check if we have a language folder after "locales"
                if locale_idx >= 0 and locale_idx + 1 < len(parts):
                    lang_folder = parts[locale_idx + 1]
                    
                    # Check if this language is in our config
                    if lang_folder in languages:
                        result[lang_folder].append(file_path)
                        assigned_files.add(file_path)
                        continue  # Skip other language checks
            
            # Check for language markers in the filename (original implementation)
            for lang in languages:
                # Check common language marker patterns
                patterns = [
                    f".{lang}.",  # e.g., messages.en.json
                    f"-{lang}.",  # e.g., messages-en.json
                    f"_{lang}.",  # e.g., messages_en.json
                    f"/{lang}/",  # e.g., locales/en/translations.json
                    f"{os.path.sep}{lang}{os.path.sep}",  # OS agnostic path separator
                    f"/{lang}.",  # e.g., locales/en.yaml
                    f"{os.path.sep}{lang}.",  # OS agnostic path separator
                    f"/{lang}$",  # For files simply named as the language code (e.g., en.json)
                    f"{os.path.sep}{lang}$"  # OS agnostic path separator for files named with language code
                ]
                
                match_found = False
                for pattern in patterns:
                    if pattern in file_path:
                        match_found = True
                        break
                
                if match_found:
                    result[lang].append(file_path)
                    assigned_files.add(file_path)
                    break
        
        # # Second pass: assign unmarked files to the source language
        # for file_path in files:
        #     if file_path not in assigned_files:
        #         result[source_language].append(file_path)
        
        return result 