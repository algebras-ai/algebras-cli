"""
iOS .strings localization file handler
"""

import os
import re
from typing import Dict, Any, Optional, Set, Match

# Import Config to check normalization settings
from algebras.config import Config


def read_ios_strings_file(file_path: str) -> Dict[str, Any]:
    """
    Read an iOS .strings localization file and extract key-value pairs.
    
    Args:
        file_path: Path to the iOS .strings file
        
    Returns:
        Dictionary containing the translation content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    result = {}
    
    # Pattern to match iOS strings format: "key" = "value";
    # This pattern handles:
    # - Escaped quotes in keys and values
    # - Multi-line values
    # - Comments (which we'll ignore)
    pattern = r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;'
    
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    
    for key_match, value_match in matches:
        # Unescape the key and value
        key = _unescape_ios_string(key_match)
        value = _unescape_ios_string(value_match)
        result[key] = value
    
    return result


def write_ios_strings_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write a dictionary to an iOS .strings localization file.
    
    Args:
        file_path: Path to the iOS .strings file
        content: Dictionary to write
    """
    lines = []
    
    # Sort keys to ensure consistent output
    sorted_keys = sorted(content.keys())
    
    for key in sorted_keys:
        value = content[key]
        
        # Escape key and value
        escaped_key = _escape_ios_string(str(key))
        escaped_value = _escape_ios_string(str(value))
        
        # Format as iOS strings entry
        line = f'"{escaped_key}" = "{escaped_value}";'
        lines.append(line)
    
    # Join lines and write to file
    ios_content = '\n'.join(lines) + '\n'
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(ios_content)


def write_ios_strings_file_in_place(
    file_path: str,
    content: Dict[str, Any],
    keys_to_update: Optional[Set[str]] = None,
) -> None:
    """
    Update an existing iOS .strings file in-place, preserving comments and formatting.

    Args:
        file_path: Path to the iOS .strings file
        content: Dictionary containing the translations
        keys_to_update: Optional set of keys to update. If None, all keys in content will be considered.
    """
    if not os.path.exists(file_path):
        write_ios_strings_file(file_path, content)
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        original_text = f.read()

    keys_needed = set(content.keys()) if keys_to_update is None else set(
        key for key in keys_to_update if key in content
    )
    if not keys_needed:
        return

    line_ending = "\r\n" if "\r\n" in original_text else "\n"

    pattern = re.compile(
        r'("(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*")(?P<value>(?:[^"\\]|\\.)*)(";\s*)',
        re.MULTILINE,
    )

    updated_keys: Set[str] = set()

    def _replacement(match: Match[str]) -> str:
        raw_key = match.group("key")
        key = _unescape_ios_string(raw_key)
        if key not in keys_needed:
            return match.group(0)

        new_value = content.get(key)
        if new_value is None:
            return match.group(0)

        escaped_value = _escape_ios_string(str(new_value))
        updated_keys.add(key)
        return f'{match.group(1)}{escaped_value}{match.group(4)}'

    updated_text = pattern.sub(_replacement, original_text)

    missing_keys = keys_needed - updated_keys
    if missing_keys:
        additions = []
        for key in sorted(missing_keys):
            escaped_key = _escape_ios_string(str(key))
            escaped_value = _escape_ios_string(str(content[key]))
            additions.append(f'"{escaped_key}" = "{escaped_value}";')

        updated_text = updated_text.rstrip("\r\n")
        if updated_text:
            updated_text += line_ending + line_ending
        updated_text += line_ending.join(additions)
        updated_text += line_ending
    else:
        if not updated_text.endswith(line_ending):
            updated_text += line_ending

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_text)


def _unescape_ios_string(text: str) -> str:
    """
    Unescape an iOS strings value, handling escape sequences.
    
    Args:
        text: The escaped text
        
    Returns:
        Unescaped text
    """
    # Handle iOS-specific escape sequences
    replacements = [
        ('\\"', '"'),
        ('\\\\', '\\'),
        ('\\n', '\n'),
        ('\\t', '\t'),
        ('\\r', '\r'),
        ("\\'", "'"),
    ]
    
    result = text
    for escaped, unescaped in replacements:
        result = result.replace(escaped, unescaped)
    
    return result


def _escape_ios_string(text: str) -> str:
    """
    Escape text for iOS .strings format.
    
    Args:
        text: The text to escape
        
    Returns:
        Escaped text suitable for iOS .strings format
    """
    # Check if normalization is enabled
    try:
        config = Config()
        if config.exists():
            config.load()
            normalize_strings = config.get_setting("api.normalize_strings", True)
        else:
            normalize_strings = True  # Default to True if no config
    except:
        normalize_strings = True  # Default to True if config fails to load
    
    # Handle iOS-specific escape sequences
    # Order matters - backslash must be escaped first
    replacements = [
        ('\\', '\\\\'),
        ('"', '\\"'),
        ('\n', '\\n'),
        ('\t', '\\t'),
        ('\r', '\\r'),
    ]
    
    # Only escape apostrophes if normalization is disabled
    if not normalize_strings:
        replacements.append(("'", "\\'"))
    
    result = text
    for unescaped, escaped in replacements:
        result = result.replace(unescaped, escaped)
    
    return result 