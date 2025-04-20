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
            "i18n/*.json"
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
        languages = self.config.get_languages()
        
        result = {lang: [] for lang in languages}
        assigned_files = set()
        
        # First pass: assign files with explicit language markers
        for file_path in files:
            base_name = os.path.basename(file_path)
            
            # Check for language markers in the filename
            for lang in languages:
                # Check common language marker patterns
                patterns = [
                    f".{lang}.",  # e.g., messages.en.json
                    f"-{lang}.",  # e.g., messages-en.json
                    f"_{lang}.",  # e.g., messages_en.json
                    f"/{lang}.",  # e.g., locales/en.yaml
                    f"{os.path.sep}{lang}.",  # OS agnostic path separator
                    f"/{lang}",  # For files simply named as the language code (e.g., en.json)
                    f"{os.path.sep}{lang}"  # OS agnostic path separator for files named with language code
                ]
                
                if any(pattern in file_path for pattern in patterns):
                    result[lang].append(file_path)
                    assigned_files.add(file_path)
                    break
        
        # Second pass: assign unmarked files to the default language
        if languages:
            default_lang = self.config.get_source_language()
            for file_path in files:
                if file_path not in assigned_files:
                    result[default_lang].append(file_path)
        
        return result 