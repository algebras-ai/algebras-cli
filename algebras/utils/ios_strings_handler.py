"""
iOS .strings localization file handler
"""

import re
from typing import Any, Dict, Iterator, Tuple

# Import Config to check normalization settings
from algebras.config import Config


# One "key" = "value"; entry, or a comment. Comments are matched so that entries inside them
# (commented-out translations) are skipped, and so a "//" or "/*" inside a quoted value is not
# mistaken for a comment.
_ENTRY_OR_COMMENT = re.compile(
    r'/\*.*?\*/'
    r'|//[^\n]*'
    r'|"(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*;',
    re.DOTALL,
)


def _iter_entries(content: str) -> Iterator[Tuple[str, "re.Match[str]"]]:
    """(unescaped key, match) for every entry outside comments, in file order."""
    for m in _ENTRY_OR_COMMENT.finditer(content):
        if m.group("key") is not None:
            yield _unescape_ios_string(m.group("key")), m


def read_ios_strings_file(file_path: str) -> Dict[str, Any]:
    """
    Read an iOS .strings localization file and extract key-value pairs.

    Entries inside /* */ and // comments are ignored.

    Args:
        file_path: Path to the iOS .strings file

    Returns:
        Dictionary containing the translation content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    result = {}
    for key, m in _iter_entries(content):
        result[key] = _unescape_ios_string(m.group("value"))
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


_ESCAPES = {'"': '"', '\\': '\\', 'n': '\n', 't': '\t', 'r': '\r', "'": "'"}
_ESCAPE_RE = re.compile(r'\\(?:U([0-9A-Fa-f]{4})|(.))', re.DOTALL)


def _unescape_ios_string(text: str) -> str:
    """
    Unescape an iOS strings value, handling escape sequences.

    One pass, left to right, so an escaped backslash followed by "n" ("\\\\n") stays a backslash
    and an "n" instead of turning into a newline. "\\U2026" becomes the character it names.
    Unknown escapes are kept as written. "%" is never touched.

    Args:
        text: The escaped text

    Returns:
        Unescaped text
    """
    def _replace(m: "re.Match[str]") -> str:
        if m.group(1) is not None:
            return chr(int(m.group(1), 16))
        return _ESCAPES.get(m.group(2), m.group(0))

    return _ESCAPE_RE.sub(_replace, text)


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


def update_ios_strings_file_in_place(file_path: str, updates: Dict[str, str]) -> None:
    """
    Replace the values of existing keys, leaving every other byte of the file as it is
    (comments, key order, spacing, line endings, other entries' escaping).

    Keys not present in the file are ignored. A key that appears more than once is updated
    everywhere, so whichever occurrence the reader picks has the new value.

    Args:
        file_path: Path to the iOS .strings file
        updates: {key: new unescaped value}
    """
    if not updates:
        return
    with open(file_path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    parts = []
    pos = 0
    for key, m in _iter_entries(content):
        if key not in updates:
            continue
        start, end = m.span("value")
        parts.append(content[pos:start])
        parts.append(_escape_ios_string(str(updates[key])))
        pos = end
    if not parts:
        return
    parts.append(content[pos:])

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(''.join(parts))
