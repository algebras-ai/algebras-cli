"""
Android XML file format handler
"""

from typing import Dict, Any, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.android_xml_handler import (
    read_android_xml_file,
    write_android_xml_file,
    write_android_xml_file_in_place,
)


class XMLHandler(FileFormatHandler):
    """Handler for Android XML files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read Android XML file"""
        return read_android_xml_file(file_path)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write Android XML file"""
        write_android_xml_file(file_path, content)
    
    def supports_in_place(self) -> bool:
        """XML format supports in-place updates"""
        return True
    
    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """Write Android XML file in-place"""
        write_android_xml_file_in_place(file_path, content, keys_to_update)
