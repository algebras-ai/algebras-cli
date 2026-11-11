"""
iOS Strings file format handler
"""

from typing import Dict, Any, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ios_strings_handler import (
    read_ios_strings_file,
    write_ios_strings_file,
    write_ios_strings_preserving_layout,
)


class StringsHandler(FileFormatHandler):
    """Handler for iOS Strings files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read iOS Strings file"""
        return read_ios_strings_file(file_path)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Write iOS Strings file.

        With preserve_layout and a source_file, the file keeps its layout (or, if new, takes the
        source's); otherwise it is regenerated sorted by key.
        """
        source_file = kwargs.get("source_file")
        if kwargs.get("preserve_layout") and source_file:
            write_ios_strings_preserving_layout(file_path, content, source_file)
        else:
            write_ios_strings_file(file_path, content)

    def supports_in_place(self) -> bool:
        """.strings supports in-place updates"""
        return True

    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """Change only the given values and add new keys at their source position."""
        source_file = kwargs.get("source_file")
        if source_file:
            write_ios_strings_preserving_layout(file_path, content, source_file, keys_to_update)
        else:
            write_ios_strings_file(file_path, content)
