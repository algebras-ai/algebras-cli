"""
PO (gettext) file format handler
"""

from typing import Dict, Any, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.po_handler import (
    read_po_file,
    write_po_file,
)


class POHandler(FileFormatHandler):
    """Handler for PO (gettext) files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read PO file"""
        return read_po_file(file_path)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write PO file"""
        po_mark_fuzzy = kwargs.get("po_mark_fuzzy", False)
        write_po_file(file_path, content, po_mark_fuzzy)
    
    def supports_in_place(self) -> bool:
        """PO format supports in-place updates via write_po_file"""
        return True
    
    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """Write PO file (write_po_file already supports in-place)"""
        po_mark_fuzzy = kwargs.get("po_mark_fuzzy", False)
        write_po_file(file_path, content, po_mark_fuzzy)
