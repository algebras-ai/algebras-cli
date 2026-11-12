"""
iOS .strings localization file handler
"""

import os
import re
from typing import Any, Dict, Iterator, Optional, Set, Tuple

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
    
    with open(file_path, 'w', encoding='utf-8', newline="") as f:
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


# ---------------------------------------------------------------------------
# Layout-preserving writes (translate / update)
# ---------------------------------------------------------------------------

# As _ENTRY_OR_COMMENT, but a // comment stops before the \r of a CRLF line ending.
_LAYOUT_TOKEN = re.compile(
    r'/\*.*?\*/'
    r'|//[^\r\n]*'
    r'|"(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*;',
    re.DOTALL,
)


def _layout_items(text: str):
    from algebras.utils.layout_merge import COMMENT, ENTRY, Item

    items = []
    matches = []
    for m in _LAYOUT_TOKEN.finditer(text):
        if m.group("key") is not None:
            items.append(Item(ENTRY, m.start(), m.end(), _unescape_ios_string(m.group("key"))))
        else:
            items.append(Item(COMMENT, m.start(), m.end()))
        matches.append(m)
    return items, matches


def _render_entry(m: "re.Match[str]", value: str) -> str:
    """The entry as written in its file, with the value replaced (spacing and key kept)."""
    start, end = m.span("value")
    raw = m.group("value")
    if _unescape_ios_string(raw) != str(value):
        raw = _escape_ios_string(str(value))
    return m.string[m.start():start] + raw + m.string[end:m.end()]


def write_ios_strings_preserving_layout(
    file_path: str,
    content: Dict[str, Any],
    source_file: str,
    keys_to_update: Optional[Set[str]] = None,
) -> None:
    """
    Write translations keeping the file's layout.

    Target exists: only values that changed are replaced; keys new to the target are added at
    their source position (with the comments attached to them in the source). Keys the source no
    longer has stay. Comments, order, blank lines, escaping of untouched entries, line endings
    and the trailing newline are kept.

    Target does not exist: the source file is the template (order, comments, blank lines), with
    each value replaced by its translation. Keys missing from `content` (left untranslated) are
    left out, never written in the source language.

    Args:
        file_path: Target .strings file
        content: {key: translated value}
        source_file: Source-language .strings file (template and positions of new keys)
        keys_to_update: Keys to write; None for every key in content
    """
    from algebras.utils import layout_merge

    with open(source_file, 'r', encoding='utf-8', newline='') as f:
        source_text = f.read()
    source_items, source_matches = _layout_items(source_text)

    keys = set(content) if keys_to_update is None else {k for k in keys_to_update if k in content}
    keys = {k for k in keys if not isinstance(content[k], (dict, list))}

    if not os.path.exists(file_path):
        output = layout_merge.build_from_template(
            source_text,
            source_items,
            keep=lambda i: source_items[i].key in keys,
            render_item=lambda i: _render_entry(source_matches[i], content[source_items[i].key]),
        )
        # Keys the source does not have (not expected): at the end.
        source_keys = {it.key for it in source_items if it.kind == layout_merge.ENTRY}
        extra = [k for k in content if k in keys and k not in source_keys]
        if extra:
            nl = layout_merge.newline_of(output)
            if output and not output.endswith("\n"):
                output += nl
            output += "".join(
                f'"{_escape_ios_string(k)}" = "{_escape_ios_string(str(content[k]))}";{nl}' for k in extra
            )
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            f.write(output)
        return

    with open(file_path, 'r', encoding='utf-8', newline='') as f:
        target_text = f.read()
    target_items, target_matches = _layout_items(target_text)

    edits = []
    present = set()
    for item, m in zip(target_items, target_matches):
        if item.kind != layout_merge.ENTRY:
            continue
        present.add(item.key)
        if item.key not in keys:
            continue
        new_value = str(content[item.key])
        if _unescape_ios_string(m.group("value")) == new_value:
            continue
        start, end = m.span("value")
        edits.append((start, end, _escape_ios_string(new_value)))

    new_keys = keys - present
    new_indices = []
    placed = set()
    for i, item in enumerate(source_items):
        if item.kind == layout_merge.ENTRY and item.key in new_keys and item.key not in placed:
            new_indices.append(i)
            placed.add(item.key)
    orphans = [
        f'"{_escape_ios_string(k)}" = "{_escape_ios_string(str(content[k]))}";'
        for k in sorted(new_keys - placed)
    ]
    if not edits and not new_indices and not orphans:
        return

    output = layout_merge.merge(
        target_text,
        target_items,
        source_text,
        source_items,
        new_indices,
        render_item=lambda i: _render_entry(source_matches[i], content[source_items[i].key]),
        edits=edits,
        orphan_texts=orphans,
    )
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(output)
