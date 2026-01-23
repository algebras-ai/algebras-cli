"""
File format detection utility
"""

from enum import Enum
from typing import Optional


class FileFormat(Enum):
    """Supported file formats"""

    JSON = "json"
    YAML = "yaml"
    TS = "ts"
    XML = "xml"
    STRINGS = "strings"
    STRINGSDICT = "stringsdict"
    PO = "po"
    HTML = "html"
    XLIFF = "xliff"
    CSV = "csv"
    TSV = "tsv"
    UNKNOWN = "unknown"


def detect_format(file_path: str) -> FileFormat:
    """
    Detect file format based on file extension.

    Args:
        file_path: Path to the file

    Returns:
        FileFormat enum value
    """
    if not file_path:
        return FileFormat.UNKNOWN

    file_path_lower = file_path.lower()

    # Check extensions in order of specificity (longer first)
    if file_path_lower.endswith(".stringsdict"):
        return FileFormat.STRINGSDICT
    elif file_path_lower.endswith((".xlf", ".xliff")):
        return FileFormat.XLIFF
    elif file_path_lower.endswith(".strings"):
        return FileFormat.STRINGS
    elif file_path_lower.endswith(".tsv"):
        return FileFormat.TSV
    elif file_path_lower.endswith(".csv"):
        return FileFormat.CSV
    elif file_path_lower.endswith((".yaml", ".yml")):
        return FileFormat.YAML
    elif file_path_lower.endswith(".json"):
        return FileFormat.JSON
    elif file_path_lower.endswith(".ts"):
        return FileFormat.TS
    elif file_path_lower.endswith(".xml"):
        return FileFormat.XML
    elif file_path_lower.endswith(".po"):
        return FileFormat.PO
    elif file_path_lower.endswith((".html", ".htm")):
        return FileFormat.HTML
    else:
        return FileFormat.UNKNOWN


def is_flat_format(format: FileFormat) -> bool:
    """
    Check if format uses flat dictionary structure (not nested).

    Args:
        format: FileFormat enum value

    Returns:
        True if format uses flat dictionary, False otherwise
    """
    flat_formats = {
        FileFormat.HTML,
        FileFormat.XLIFF,
        FileFormat.CSV,
        FileFormat.TSV,
    }
    return format in flat_formats
