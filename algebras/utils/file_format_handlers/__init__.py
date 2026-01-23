"""
File format handlers package
"""

from typing import Optional, TYPE_CHECKING

from algebras.utils.file_format_detector import detect_format, FileFormat

if TYPE_CHECKING:
    from algebras.config import Config

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.file_format_handlers.json_handler import JSONHandler
from algebras.utils.file_format_handlers.yaml_handler import YAMLHandler
from algebras.utils.file_format_handlers.ts_handler import TSHandler
from algebras.utils.file_format_handlers.xml_handler import XMLHandler
from algebras.utils.file_format_handlers.strings_handler import StringsHandler
from algebras.utils.file_format_handlers.stringsdict_handler import StringsDictHandler
from algebras.utils.file_format_handlers.po_handler import POHandler
from algebras.utils.file_format_handlers.html_handler import HTMLHandler
from algebras.utils.file_format_handlers.xliff_handler import XLIFFHandler
from algebras.utils.file_format_handlers.csv_handler import CSVHandler


def get_handler(file_path: str, config: Optional["Config"] = None) -> FileFormatHandler:
    """
    Get appropriate file format handler for the given file path.
    
    Args:
        file_path: Path to the file
        config: Optional Config instance (required for CSV handler)
        
    Returns:
        FileFormatHandler instance
        
    Raises:
        ValueError: If file format is not supported
    """
    format_type = detect_format(file_path)
    
    if format_type == FileFormat.JSON:
        return JSONHandler()
    elif format_type == FileFormat.YAML:
        return YAMLHandler()
    elif format_type == FileFormat.TS:
        return TSHandler()
    elif format_type == FileFormat.XML:
        return XMLHandler()
    elif format_type == FileFormat.STRINGS:
        return StringsHandler()
    elif format_type == FileFormat.STRINGSDICT:
        return StringsDictHandler()
    elif format_type == FileFormat.PO:
        return POHandler()
    elif format_type == FileFormat.HTML:
        return HTMLHandler()
    elif format_type == FileFormat.XLIFF:
        return XLIFFHandler()
    elif format_type in (FileFormat.CSV, FileFormat.TSV):
        if config is None:
            raise ValueError("Config is required for CSV/TSV handlers")
        return CSVHandler(config)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


__all__ = [
    "FileFormatHandler",
    "get_handler",
    "detect_format",
    "FileFormat",
    "JSONHandler",
    "YAMLHandler",
    "TSHandler",
    "XMLHandler",
    "StringsHandler",
    "StringsDictHandler",
    "POHandler",
    "HTMLHandler",
    "XLIFFHandler",
    "CSVHandler",
]
