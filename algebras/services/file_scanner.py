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
        
        # Separate include and exclude patterns
        for rule in self.path_rules:
            if rule.startswith("!"):
                exclude_patterns.append(rule[1:])
            else:
                include_patterns.append(rule)
        
        # Find all files matching include patterns
        all_files = set()
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
        
        # Simplified approach: check if language code is in the file path
        for file_path in files:
            base_name = os.path.basename(file_path)
            for lang in languages:
                if f".{lang}." in base_name or f"-{lang}." in base_name or f"_{lang}." in base_name:
                    result[lang].append(file_path)
                    break
            else:
                # If no language code found, assume it's the default language (first in list)
                if languages:
                    result[languages[0]].append(file_path)
        
        return result 