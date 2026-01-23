"""
iOS Strings file format handler
"""

from typing import Dict, Any

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ios_strings_handler import (
    read_ios_strings_file,
    write_ios_strings_file,
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
        """Write iOS Strings file"""
        write_ios_strings_file(file_path, content)
