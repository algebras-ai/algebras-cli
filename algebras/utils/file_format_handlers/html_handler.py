"""
HTML file format handler
"""

from typing import Dict, Any, Optional, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.html_handler import (
    read_html_file,
    write_html_file,
)


class HTMLHandler(FileFormatHandler):
    """Handler for HTML files"""

    def read(self, file_path: str) -> Dict[str, Any]:
        """Read HTML file"""
        return read_html_file(file_path)

    def write(self, file_path: str, content: Dict[str, Any], **kwargs) -> None:
        """Write HTML file"""
        # HTML write requires source_file to preserve structure
        source_file = kwargs.get("source_file")
        if source_file is None:
            raise ValueError(
                "HTML write requires source_file in kwargs to preserve HTML structure"
            )
        write_html_file(file_path, source_file, content)

    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        """Extract keys from HTML content (flat dictionary)"""
        return set(content.keys())
