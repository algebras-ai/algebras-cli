"""
File scanner for localization files
"""

import os
import glob
from typing import List, Dict, Set, Optional

from algebras.config import Config


class FileScanner:
    """Scanner for finding localization files in the project."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize FileScanner with optional Config instance.
        
        Args:
            config: Optional Config instance. If None, creates a new Config with default path.
        """
        if config is None:
            config = Config()
        
        self.config = config
        if not self.config.exists():
            raise FileNotFoundError("No Algebras configuration found. Run 'algebras init' first.")
        
        self.config.load()
        self.source_files = self.config.get_source_files()
        # Keep path_rules for backward compatibility
        self.path_rules = self.config.get_path_rules()
    
    def find_localization_files(self) -> List[str]:
        """
        Find all localization files in the project based on source files configuration.
        
        Returns:
            List of file paths
        """
        all_files = set()
        
        # If we have source_files configuration, use it
        if self.source_files and len(self.source_files) > 0:
            for source_file in self.source_files.keys():
                if os.path.isfile(source_file):
                    all_files.add(os.path.normpath(source_file))
        else:
            # Fallback to old path_rules system for backward compatibility
            include_patterns = []
            exclude_patterns = []
            
            # Add more specific patterns for locale files
            specific_locale_patterns = [
                "src/locales/*.json",
                "locales/*.json",
                "src/i18n/*.json",
                "i18n/*.json",
                "public/locales/*/*.json",  # Add support for public/locales/{lang}/common.json
                "public/locales/*/common.json",  # Specifically target common.json files
                # iOS localization files
                "*.lproj/*.strings",
                "*/*.lproj/*.strings",
                "*/*/*.lproj/*.strings",
                "*.lproj/*.stringsdict",
                "*/*.lproj/*.stringsdict",
                "*/*/*.lproj/*.stringsdict",
                # More general patterns for iOS files
                "**/*.strings",
                "**/*.stringsdict",
                # Android values directory patterns
                "**/values/*.xml",          # Base language files: .../values/*.xml
                "**/values-*/*.xml",        # Localized files: .../values-{lang}/*.xml
                "values/*.xml",              # Direct values directory
                "values-*/*.xml",            # Direct values-{lang} directories
                # gettext .po files
                "**/*.po",
                "locale/*/*.po",
                "locales/*/*.po",
                "src/locale/*/*.po",
                "src/locales/*/*.po",
                # Flutter ARB files
                "lib/l10n/*.arb",
                "**/l10n/*.arb",
                "**/*.arb",
                # XLIFF files
                "translations/*.xlf",
                "translations/*.xliff",
                "**/*.xlf",
                "**/*.xliff",
                # Java Properties files
                "src/main/resources/*.properties",
                "**/resources/*.properties",
                "**/*.properties",
                # CSV translation files
                "locales/*.csv",
                "**/locales/*.csv",
                "**/*.csv",
                # TSV translation files
                "locales/*.tsv",
                "**/locales/*.tsv",
                "**/*.tsv",
                # XLSX translation files
                "locales/*.xlsx",
                "**/locales/*.xlsx",
                "**/*.xlsx",
            ]
            
            # Separate include and exclude patterns
            for rule in self.path_rules:
                if rule.startswith("!"):
                    exclude_patterns.append(rule[1:])
                else:
                    include_patterns.append(rule)
            
            # Find all files matching specific locale patterns first
            for pattern in specific_locale_patterns:
                for file_path in glob.glob(pattern, recursive=True):
                    if os.path.isfile(file_path):
                        all_files.add(os.path.normpath(file_path))
            
            # Also check user-configured patterns from config (don't just fallback)
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
        from algebras.utils.path_utils import resolve_destination_path
        
        # Make sure we have valid languages list (no False values)
        languages = [lang for lang in self.config.get_languages() if lang]
        
        # Get the source language from config
        source_language = self.config.get_source_language()
        
        # Initialize result with all configured languages
        result = {lang: [] for lang in languages}
        
        # If we have source_files configuration, use it
        if self.source_files:
            # First, add all source files to the source language list
            for source_file, source_config in self.source_files.items():
                # Normalize the source file path for consistent path separators
                normalized_source_file = os.path.normpath(source_file)
                if os.path.isfile(normalized_source_file):
                    # Source language files go directly to source language
                    if normalized_source_file not in result[source_language]:
                        result[source_language].append(normalized_source_file)
            
            # Then, for each source file, check destination files for other languages
            for source_file, source_config in self.source_files.items():
                # Normalize the source file path for consistent path separators
                normalized_source_file = os.path.normpath(source_file)
                if os.path.isfile(normalized_source_file):
                    # Check if this source file would generate a destination for each target language
                    destination_pattern = source_config.get("destination_path", "")
                    if destination_pattern:
                        for lang in languages:
                            if lang != source_language:
                                resolved_path = resolve_destination_path(destination_pattern, lang, self.config)
                                # Normalize the resolved path for consistent path separators
                                normalized_resolved_path = os.path.normpath(resolved_path)
                                if os.path.isfile(normalized_resolved_path):
                                    if normalized_resolved_path not in result[lang]:
                                        result[lang].append(normalized_resolved_path)
        else:
            # Fallback to old system for backward compatibility
            files = self.find_localization_files()
            assigned_files = set()
            
            # First pass: assign files with explicit language markers in folder structure
            for file_path in files:
                base_name = os.path.basename(file_path)
                directory = os.path.dirname(file_path)
                
                # Special handling for Android values directory structure
                # Pattern: .../values/*.xml (base language) and .../values-{lang}/*.xml (translations)
                if file_path.endswith('.xml'):
                    parts = file_path.split(os.path.sep)
                    
                    # Look for values or values-{lang} directory in the path
                    for i, part in enumerate(parts):
                        if part == "values":
                            # This is a base language file in /values/ directory
                            result[source_language].append(file_path)
                            assigned_files.add(file_path)
                            break
                        elif part.startswith("values-") and len(part) > 7:  # "values-" is 7 chars
                            # Extract destination locale code from values-{lang}
                            destination_value = part[7:]  # Remove "values-" prefix
                            
                            # Try to find the original language code using reverse lookup
                            # This handles mapped locale codes (e.g., "b+uz+Cyrl" -> "uz_Cyrl")
                            lang_code = self.config.get_language_code_from_destination(destination_value)
                            
                            # If reverse lookup found a match, use it
                            # Otherwise, check if the extracted value is itself a language code
                            if lang_code is None:
                                lang_code = destination_value if destination_value in languages else None
                            
                            if lang_code and lang_code in languages:
                                result[lang_code].append(file_path)
                                assigned_files.add(file_path)
                                break
                    
                    # If assigned to Android pattern, skip other language checks
                    if file_path in assigned_files:
                        continue
                
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
                        
                        # Try to find the original language code using reverse lookup
                        # This handles mapped locale codes (e.g., "b+uz+Cyrl" -> "uz_Cyrl")
                        lang_code = self.config.get_language_code_from_destination(lang_folder)
                        
                        # If reverse lookup found a match, use it
                        # Otherwise, check if the folder name is itself a language code
                        if lang_code is None:
                            lang_code = lang_folder if lang_folder in languages else None
                        
                        if lang_code and lang_code in languages:
                            result[lang_code].append(file_path)
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
        
        return result 