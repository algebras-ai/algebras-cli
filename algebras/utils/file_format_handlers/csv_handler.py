"""
CSV/TSV file format handler
"""

from typing import Dict, Any, Optional, Set, TYPE_CHECKING

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.csv_handler import (
    read_csv_file,
    write_csv_file,
    write_csv_file_in_place,
    extract_translatable_strings as extract_csv_strings,
    add_language_to_csv,
)

if TYPE_CHECKING:
    from algebras.config import Config


class CSVHandler(FileFormatHandler):
    """Handler for CSV/TSV files"""
    
    def __init__(self, config: "Config"):
        """
        Initialize CSV handler.
        
        Args:
            config: Config instance for locale mapping
        """
        self.config = config
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read CSV file (returns full CSV structure)"""
        return read_csv_file(file_path)
    
    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        """Read CSV file and extract translatable strings for specific language"""
        csv_content = read_csv_file(file_path)
        
        if language is None:
            # If no language specified, return empty dict
            return {}
        
        # Map language code to actual column name using config
        mapped_language = self.config.get_destination_locale_code(language)
        return extract_csv_strings(csv_content, mapped_language)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write CSV file"""
        # CSV write requires target language for column mapping
        target_language = kwargs.get("target_language")
        if target_language is None:
            raise ValueError(
                "CSV write requires target_language in kwargs"
            )
        
        mapped_target_lang = self.config.get_destination_locale_code(target_language)
        
        # Read existing CSV or create new structure
        import os
        if os.path.exists(file_path):
            existing_csv = read_csv_file(file_path)
        else:
            # If target doesn't exist, use source file structure if provided
            source_file = kwargs.get("source_file")
            if source_file and os.path.exists(source_file):
                existing_csv = read_csv_file(source_file)
            else:
                existing_csv = {
                    "languages": [],
                    "translations": {},
                    "key_column": "Key",
                }
        
        # Add/update language column
        updated_csv = add_language_to_csv(existing_csv, mapped_target_lang, content)
        write_csv_file(file_path, updated_csv)
    
    def supports_in_place(self) -> bool:
        """CSV format supports in-place updates"""
        return True
    
    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """Write CSV file in-place"""
        target_language = kwargs.get("target_language")
        if target_language is None:
            raise ValueError(
                "CSV write_in_place requires target_language in kwargs"
            )
        
        mapped_target_lang = self.config.get_destination_locale_code(target_language)
        write_csv_file_in_place(
            file_path,
            content,
            mapped_target_lang,
            keys_to_update,
        )
    
    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        """Extract keys from CSV content (flat dictionary)"""
        return set(content.keys())
