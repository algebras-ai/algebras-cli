"""
XLIFF file format handler
"""

from typing import Dict, Any, Optional, Set, TYPE_CHECKING

from algebras.utils.file_format_handlers.base import FileFormatHandler

if TYPE_CHECKING:
    from algebras.config import Config
from algebras.utils.xliff_handler import (
    read_xliff_file,
    write_xliff_file,
    extract_translatable_strings as extract_xliff_strings,
    update_xliff_targets,
)


class XLIFFHandler(FileFormatHandler):
    """Handler for XLIFF files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read XLIFF file (returns raw structure)"""
        return read_xliff_file(file_path)
    
    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        """Read XLIFF file and extract translatable strings"""
        raw_content = read_xliff_file(file_path)
        return extract_xliff_strings(raw_content)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write XLIFF file"""
        # XLIFF write requires additional parameters
        source_language = kwargs.get("source_language")
        target_language = kwargs.get("target_language")
        xlf_target_state = kwargs.get("xlf_target_state", "translated")
        
        if source_language is None or target_language is None:
            raise ValueError(
                "XLIFF write requires source_language and target_language in kwargs"
            )
        
        # For XLIFF, content should be the translated flat dict
        # We need the raw structure to update it
        raw_content = kwargs.get("raw_content")
        source_raw_content = kwargs.get("source_raw_content")
        
        if raw_content is None:
            # If no raw content provided, try to read existing file
            import os
            if os.path.exists(file_path):
                raw_content = read_xliff_file(file_path)
            else:
                # Create empty target structure
                xlf_version = kwargs.get("xlf_version", "1.2")
                if source_raw_content and "version" in source_raw_content:
                    xlf_version = source_raw_content["version"]
                raw_content = {
                    "version": xlf_version,
                    "files": [],
                }
        
        # Update the raw structure with translations
        updated_content = update_xliff_targets(
            raw_content,
            content,
            source_raw_content,
            xlf_target_state,
        )
        
        write_xliff_file(
            file_path,
            updated_content,
            source_language,
            target_language,
            xlf_target_state,
        )
    
    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        """Extract keys from XLIFF content (flat dictionary)"""
        return set(content.keys())
