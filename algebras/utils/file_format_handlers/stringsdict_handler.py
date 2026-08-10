"""
iOS StringsDict file format handler
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

from algebras.utils.file_format_handlers.base import FileFormatHandler

if TYPE_CHECKING:
    from algebras.config import Config
from algebras.utils.ios_stringsdict_handler import (
    read_ios_stringsdict_file,
    write_ios_stringsdict_file,
    extract_translatable_strings,
    update_translatable_strings,
)


class StringsDictHandler(FileFormatHandler):
    """Handler for iOS StringsDict files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read iOS StringsDict file (returns raw structure)"""
        return read_ios_stringsdict_file(file_path)
    
    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        """Read iOS StringsDict file and extract translatable strings"""
        raw_content = read_ios_stringsdict_file(file_path)
        return extract_translatable_strings(raw_content)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write iOS StringsDict file"""
        # For StringsDict, content should be the translated flat dict
        # We need the raw structure to update it
        raw_content = kwargs.get("raw_content")
        source_raw_content = kwargs.get("source_raw_content")
        if raw_content is None:
            # If no raw content provided, try to read existing file
            import os
            if os.path.exists(file_path):
                raw_content = read_ios_stringsdict_file(file_path)
            elif source_raw_content is not None:
                # New target file: start empty, missing keys are filled in
                # from source_raw_content below
                raw_content = {}
            else:
                # If file doesn't exist and there's no source structure to
                # build from, we can't write without raw structure
                raise ValueError(
                    "StringsDict write requires raw_content in kwargs. "
                    "Either provide raw_content or ensure target file exists."
                )

        # Update the raw structure with translations, filling in any keys
        # missing from raw_content using source_raw_content as a template
        updated_content = update_translatable_strings(raw_content, content, source_raw_content)
        write_ios_stringsdict_file(file_path, updated_content)
