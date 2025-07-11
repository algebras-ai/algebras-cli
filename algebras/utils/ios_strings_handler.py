"""
iOS .strings localization file handler
"""

import re
from typing import Dict, Any


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
    # Handle iOS-specific escape sequences
    # Order matters - backslash must be escaped first
    replacements = [
        ('\\', '\\\\'),
        ('"', '\\"'),
        ('\n', '\\n'),
        ('\t', '\\t'),
        ('\r', '\\r'),
        ("'", "\\'"),
    ]
    
    result = text
    for unescaped, escaped in replacements:
        result = result.replace(unescaped, escaped)
    
    return result 