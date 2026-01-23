"""
TypeScript file format handler
"""

from typing import Dict, Any, Optional, Callable

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ts_handler import (
    read_ts_translation_file,
    write_ts_translation_file,
)
from algebras.utils.file_writer import IncrementalFileWriter


class TSHandler(FileFormatHandler):
    """Handler for TypeScript translation files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read TypeScript translation file"""
        return read_ts_translation_file(file_path)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write TypeScript translation file"""
        write_ts_translation_file(file_path, content)
    
    def create_incremental_writer(
        self,
        file_path: str,
        export_name: Optional[str] = None
    ) -> IncrementalFileWriter:
        """
        Create incremental file writer for TypeScript files.
        This allows writing translations in batches as they are completed.
        
        Args:
            file_path: Path to the file
            export_name: Export name for TypeScript file (defaults to basename without extension)
            
        Returns:
            IncrementalFileWriter instance
        """
        if export_name is None:
            import os
            basename = os.path.basename(file_path)
            export_name = basename.split(".")[0]
        
        return IncrementalFileWriter(file_path, "ts", export_name)
