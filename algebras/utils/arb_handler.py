"""
Flutter ARB (Application Resource Bundle) file handler
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple


def read_arb_file(file_path: str) -> Dict[str, Any]:
    """
    Read a Flutter ARB file and return its content as a dictionary.
    
    Args:
        file_path: Path to the ARB file
        
    Returns:
        Dictionary containing the ARB file content
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is not valid JSON or ARB format
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"ARB file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ARB file {file_path}: {str(e)}")
    
    if not isinstance(content, dict):
        raise ValueError(f"ARB file {file_path} must contain a JSON object")
    
    return content


def write_arb_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write content to a Flutter ARB file.
    
    Args:
        file_path: Path where to write the ARB file
        content: Dictionary containing the ARB content
        
    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("ARB content must be a dictionary")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2, sort_keys=True)


def extract_translatable_strings(arb_content: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract translatable strings from ARB content, filtering out metadata.
    
    Args:
        arb_content: ARB file content as dictionary
        
    Returns:
        Dictionary of key-value pairs for translatable strings only
    """
    translatable = {}
    
    for key, value in arb_content.items():
        # Skip metadata keys (prefixed with @)
        if key.startswith('@'):
            continue
        
        # Only include string values
        if isinstance(value, str):
            translatable[key] = value
    
    return translatable


def create_arb_from_translations(translations: Dict[str, str], 
                                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create ARB content from translations and optional metadata.
    
    Args:
        translations: Dictionary of key-value translation pairs
        metadata: Optional metadata dictionary (keys prefixed with @)
        
    Returns:
        ARB content dictionary
    """
    arb_content = {}
    
    # Add metadata first if provided
    if metadata:
        for key, value in metadata.items():
            if not key.startswith('@'):
                key = f"@{key}"
            arb_content[key] = value
    
    # Add translations
    arb_content.update(translations)
    
    return arb_content


def get_arb_metadata(arb_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from ARB content.
    
    Args:
        arb_content: ARB file content as dictionary
        
    Returns:
        Dictionary containing only metadata keys (prefixed with @)
    """
    metadata = {}
    
    for key, value in arb_content.items():
        if key.startswith('@'):
            metadata[key] = value
    
    return metadata


def is_valid_arb_file(file_path: str) -> bool:
    """
    Check if a file is a valid ARB file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file is a valid ARB file, False otherwise
    """
    try:
        content = read_arb_file(file_path)
        return isinstance(content, dict)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return False


def get_arb_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from ARB file path or content.
    
    Args:
        file_path: Path to the ARB file
        
    Returns:
        Language code if found, None otherwise
    """
    # Try to extract from @locale metadata first (content has higher priority)
    try:
        content = read_arb_file(file_path)
        # Check for @locale metadata object first (higher priority)
        locale_metadata = content.get('@locale')
        if isinstance(locale_metadata, dict) and 'locale' in locale_metadata:
            return locale_metadata['locale']
        # Check for @@locale field (common in ARB files)
        locale_value = content.get('@@locale')
        if isinstance(locale_value, str):
            return locale_value
    except (ValueError, json.JSONDecodeError, FileNotFoundError):
        pass
    
    # Try to extract from filename (e.g., app_en.arb -> en, app_en_US.arb -> en_US)
    # Only extract if the pattern looks like a valid locale code
    filename = os.path.basename(file_path)
    if '_' in filename:
        parts = filename.split('_')
        if len(parts) >= 3:
            # Check if the last two parts form a valid locale (e.g., en_US)
            last_two = '_'.join(parts[-2:]).split('.')[0]
            # Validate it's a locale format: exactly 5 chars with underscore, both parts are letters
            if len(last_two) == 5 and '_' in last_two:
                lang, region = last_two.split('_')
                if lang.isalpha() and len(lang) == 2 and region.isalpha() and len(region) == 2:
                    return last_two
        elif len(parts) >= 2:
            # Get the part before .arb
            name_part = parts[-1].split('.')[0]
            # Validate it's a 2-letter language code
            if len(name_part) == 2 and name_part.isalpha():
                return name_part

    return None


# ---------------------------------------------------------------------------
# Order-preserving writes
# ---------------------------------------------------------------------------

# Language (lowercase), then optional script/region parts (Hant, TW, 419): app_zh_Hant_TW.arb.
_LOCALE_IN_NAME = re.compile(r"_([a-z]{2,3}(?:_(?:[A-Z][A-Za-z]{1,3}|\d{3}))*)\.arb$")


def locale_from_filename(file_path: str) -> Optional[str]:
    """'lib/l10n/app_pt_BR.arb' -> 'pt_BR' (the naming flutter gen-l10n expects), else None."""
    match = _LOCALE_IN_NAME.search(os.path.basename(file_path))
    return match.group(1) if match else None


def write_arb_content(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write ARB content in the given key order (metadata stays next to its message, as in the source).
    A copied "@@locale" is set to the locale in the file name, which gen-l10n requires to match.
    """
    if not isinstance(content, dict):
        raise ValueError("ARB content must be a dictionary")
    content = dict(content)
    locale = locale_from_filename(file_path)
    if locale and isinstance(content.get("@@locale"), str):
        content["@@locale"] = locale
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n﻿":
        i += 1
    return i


def _top_level_entries(text: str) -> Tuple[List[Tuple[str, int, int, int]], int, int]:
    """
    ([(key, key_start, value_start, value_end)], open_brace, close_brace) of the top-level object,
    with exact character positions, so single values can be replaced in place.
    """
    decoder = json.JSONDecoder()
    i = _skip_ws(text, 0)
    if i >= len(text) or text[i] != "{":
        raise ValueError("ARB file must contain a JSON object")
    open_brace = i
    entries = []
    i = _skip_ws(text, i + 1)
    if i < len(text) and text[i] == "}":
        return entries, open_brace, i
    while True:
        if i >= len(text) or text[i] != '"':
            raise ValueError(f"Expected a key at position {i}")
        key, after_key = json.decoder.scanstring(text, i + 1)
        key_start = i
        i = _skip_ws(text, after_key)
        if i >= len(text) or text[i] != ":":
            raise ValueError(f"Expected ':' at position {i}")
        value_start = _skip_ws(text, i + 1)
        _, value_end = decoder.raw_decode(text, value_start)
        entries.append((key, key_start, value_start, value_end))
        i = _skip_ws(text, value_end)
        if i < len(text) and text[i] == ",":
            i = _skip_ws(text, i + 1)
            continue
        if i < len(text) and text[i] == "}":
            return entries, open_brace, i
        raise ValueError(f"Expected ',' or '}}' at position {i}")


def update_arb_values(file_path: str, values: Dict[str, str], add_missing: bool = True) -> List[str]:
    """
    Set string values in an existing ARB file, changing only those values: key order, indentation,
    the escaping of other entries and `@` metadata stay byte for byte. Keys not in the file are
    appended at the end (add_missing) or returned as not found.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    entries, open_brace, close_brace = _top_level_entries(text)
    positions = {key: (start, end) for key, _, start, end in entries}
    newline = "\r\n" if "\r\n" in text else "\n"
    indent = "  "
    if entries:
        line_start = text.rfind("\n", 0, entries[0][1]) + 1
        prefix = text[line_start : entries[0][1]]
        if prefix and not prefix.strip():
            indent = prefix

    edits: List[Tuple[int, int, str]] = []
    appended: List[str] = []
    not_found: List[str] = []
    for key, value in values.items():
        encoded = json.dumps(value, ensure_ascii=False)
        if key in positions:
            start, end = positions[key]
            if json.loads(text[start:end]) != value:
                edits.append((start, end, encoded))
        elif add_missing:
            appended.append(f"{indent}{json.dumps(key, ensure_ascii=False)}: {encoded}")
        else:
            not_found.append(key)

    separator = "," + newline
    if appended:
        if entries:
            insert_at = entries[-1][3]
            edits.append((insert_at, insert_at, separator + separator.join(appended)))
        else:
            edits.append((open_brace + 1, close_brace, newline + separator.join(appended) + newline))

    if edits:
        for start, end, replacement in sorted(edits, key=lambda e: e[0], reverse=True):
            text = text[:start] + replacement + text[end:]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
    return not_found
