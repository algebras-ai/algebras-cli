"""
Java Properties file handler

Parsing follows java.util.Properties.load: comment lines start with '#' or '!', a line ending in an
odd number of backslashes continues on the next line (whose leading whitespace is skipped), the key
ends at the first unescaped '=', ':' or whitespace, and values are unescaped (\\uXXXX, \\t, \\n,
\\r, \\f, and \\x -> x for any other character).

Files are read as UTF-8 (Java 9+ ResourceBundle), falling back to ISO-8859-1 (Java 8).
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class PropertiesEntry:
    """One key/value pair and where it sits in the file."""

    key: str
    value: str
    first_line: int  # index of the first physical line
    last_line: int  # index of the last physical line (continuation lines included)
    prefix: str  # raw text of the first line up to the value: indentation, key and separator
    # The raw (escaped) value text of each physical line, and the leading whitespace of each
    # continuation line, so a rewritten value keeps its line breaks and escaping where unchanged.
    segments: List[str] = field(default_factory=list)
    leads: List[str] = field(default_factory=list)


def _read_text(file_path: str) -> str:
    with open(file_path, "rb") as f:
        data = f.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _continues(line: str) -> bool:
    """True if the physical line ends with an odd number of backslashes."""
    n = len(line) - len(line.rstrip("\\"))
    return n % 2 == 1


_KEY_END = re.compile(r"(?:\\.|[^\\=:\s])*", re.DOTALL)
_SEPARATOR = re.compile(r"[ \t\f]*[=:]?[ \t\f]*")


def parse_properties_text(text: str) -> Tuple[List[str], List[PropertiesEntry]]:
    """Split `text` into physical lines (with their line endings) and parse its entries."""
    lines = text.splitlines(keepends=True)
    entries: List[PropertiesEntry] = []
    i = 0
    while i < len(lines):
        first = lines[i].rstrip("\r\n")
        stripped = first.lstrip(" \t\f")
        if not stripped or stripped[0] in "#!":
            i += 1
            continue

        indent = first[: len(first) - len(stripped)]
        key_match = _KEY_END.match(stripped)
        raw_key = key_match.group(0)
        sep = _SEPARATOR.match(stripped, key_match.end())
        prefix = indent + stripped[: sep.end()]

        # Collect the raw value across continuation lines, remembering where each line starts.
        start = i
        raw_parts: List[str] = []
        leads: List[str] = []
        part = stripped[sep.end() :]
        while _continues(part) and i + 1 < len(lines):
            raw_parts.append(part[:-1])
            i += 1
            nxt = lines[i].rstrip("\r\n")
            body = nxt.lstrip(" \t\f")
            leads.append(nxt[: len(nxt) - len(body)])
            part = body
        if _continues(part):
            part = part[:-1]  # a trailing backslash on the last line of the file
        raw_parts.append(part)

        entries.append(
            PropertiesEntry(
                key=unescape(raw_key),
                value="".join(unescape(raw) for raw in raw_parts),
                first_line=start,
                last_line=i,
                prefix=prefix,
                segments=raw_parts,
                leads=leads,
            )
        )
        i += 1
    return lines, entries


def read_properties_file(file_path: str) -> Dict[str, str]:
    """
    Read a Java Properties file and return its content as a dictionary.

    Args:
        file_path: Path to the Properties file

    Returns:
        Dictionary containing the Properties file content

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Properties file not found: {file_path}")
    _, entries = parse_properties_text(_read_text(file_path))
    return {e.key: e.value for e in entries}


def uses_unicode_escapes(file_path: str) -> bool:
    """
    True if non-ASCII text should be written as \\uXXXX escapes: the file uses such escapes, or has
    no raw non-ASCII character outside comments. New files are written this way too: every Java
    version reads it (Java 8 reads .properties as ISO-8859-1).
    """
    if not os.path.exists(file_path):
        return True
    raw_non_ascii = False
    for line in _read_text(file_path).splitlines():
        if line.lstrip().startswith(("#", "!")):
            continue
        if re.search(r"(?<!\\)(?:\\\\)*\\u[0-9a-fA-F]{4}", line):
            return True
        raw_non_ascii = raw_non_ascii or any(ord(c) > 0x7F for c in line)
    return not raw_non_ascii


def write_properties_file(file_path: str, content: Dict[str, str],
                         header: Optional[str] = None, ascii_only: bool = True) -> None:
    """
    Write content to a Java Properties file.

    Args:
        file_path: Path where to write the Properties file
        content: Dictionary containing the Properties content
        header: Optional header comment to add to the file
        ascii_only: Write non-ASCII characters as \\uXXXX escapes (readable by every Java version)

    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("Properties content must be a dictionary")

    # Ensure the directory exists
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8', newline="\n") as f:
        # Write header if provided
        if header:
            f.write(f"# {header}\n")
            f.write(f"# Generated by algebras-cli\n\n")

        # Write properties
        for key, value in content.items():
            if isinstance(value, str):
                escaped_key = _escape_properties_key(key, ascii_only)
                escaped_value = _escape_properties_value(value, ascii_only)
                f.write(f"{escaped_key}={escaped_value}\n")


def update_properties_values(
    file_path: str,
    values: Dict[str, str],
    add_missing: bool = True,
    ascii_only: Optional[bool] = None,
) -> List[str]:
    """
    Replace the values of the given keys in place. Comments, blank lines, key order, separators and
    every other entry stay byte for byte; a changed value keeps its continuation lines where the
    text around each line break is unchanged. Keys not in the file are appended (add_missing) or
    returned.

    ascii_only: write non-ASCII as \\uXXXX; by default follow the file's own convention.
    """
    text = _read_text(file_path)
    if ascii_only is None:
        ascii_only = uses_unicode_escapes(file_path)
    lines, entries = parse_properties_text(text)
    newline = "\r\n" if "\r\n" in text else "\n"
    last_by_key: Dict[str, PropertiesEntry] = {}
    for e in entries:
        last_by_key[e.key] = e  # Properties.load keeps the last duplicate

    replacements: Dict[int, Tuple[int, str]] = {}
    missing: List[str] = []
    for key, value in values.items():
        entry = last_by_key.get(key)
        if entry is None:
            missing.append(key)
            continue
        if entry.value == value:
            continue
        ending = lines[entry.last_line][len(lines[entry.last_line].rstrip("\r\n")) :]
        replacements[entry.first_line] = (
            entry.last_line,
            _render_value(entry, value, ascii_only, newline) + (ending or ""),
        )

    out: List[str] = []
    i = 0
    while i < len(lines):
        if i in replacements:
            last, rendered = replacements[i]
            out.append(rendered)
            i = last + 1
        else:
            out.append(lines[i])
            i += 1

    if add_missing and missing:
        if out and not out[-1].endswith(("\n", "\r")):
            out[-1] += newline
        for key in missing:
            out.append(f"{_escape_properties_key(key, ascii_only)}={_escape_properties_value(values[key], ascii_only)}{newline}")
        missing = []

    new_text = "".join(out)
    if new_text != text:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
    return missing


def _render_value(entry: PropertiesEntry, value: str, ascii_only: bool, newline: str) -> str:
    """
    The entry's lines with `value`. Only the changed part is escaped anew: the text around it keeps
    its original escaping, and line breaks outside it are kept (the changed part goes on one line).
    """
    old = entry.value
    head = 0
    while head < min(len(old), len(value)) and old[head] == value[head]:
        head += 1
    tail = 0
    while tail < min(len(old), len(value)) - head and old[-1 - tail] == value[-1 - tail]:
        tail += 1
    change_start, change_end = head, len(old) - tail
    middle = value[head : len(value) - tail]

    # Logical start of each physical line's text, and the raw offset of each of its characters.
    starts: List[int] = []
    offsets: List[List[int]] = []
    pos = 0
    for raw in entry.segments:
        offs = [start for start, _, _ in _tokens(raw)] + [len(raw)]
        starts.append(pos)
        offsets.append(offs)
        pos += len(offs) - 1
    ends = [s + len(o) - 1 for s, o in zip(starts, offsets)]

    last = len(entry.segments) - 1
    first = next((i for i in range(len(ends)) if change_start < ends[i]), last)
    end_line = first if change_end <= change_start else next(
        (i for i in range(first, len(ends)) if change_end <= ends[i]), last
    )
    before = entry.segments[first][: offsets[first][change_start - starts[first]]]
    escaped = _escape_properties_value(middle, ascii_only)
    if before and escaped.startswith("\\ "):
        escaped = escaped[1:]  # only a space at the start of a line needs escaping
    merged = before + escaped + entry.segments[end_line][offsets[end_line][change_end - starts[end_line]] :]
    pieces = entry.segments[:first] + [merged] + entry.segments[end_line + 1 :]
    leads = entry.leads[:first] + entry.leads[end_line:]

    rendered = entry.prefix + pieces[0]
    for lead, piece in zip(leads, pieces[1:]):
        rendered += "\\" + newline + lead + piece
    return rendered


def extract_translatable_strings(properties_content: Dict[str, str]) -> Dict[str, str]:
    """
    Extract translatable strings from Properties content.

    Args:
        properties_content: Properties file content as dictionary

    Returns:
        Dictionary of key-value pairs for translatable strings
    """
    # All properties are considered translatable strings
    return properties_content.copy()


def create_properties_from_translations(translations: Dict[str, str],
                                      header: Optional[str] = None) -> Dict[str, str]:
    """
    Create Properties content from translations.

    Args:
        translations: Dictionary of key-value translation pairs
        header: Optional header comment

    Returns:
        Properties content dictionary
    """
    return translations.copy()


def _escape_char(c: str, ascii_only: bool) -> str:
    if c == "\\":
        return "\\\\"
    if c == "\n":
        return "\\n"
    if c == "\r":
        return "\\r"
    if c == "\t":
        return "\\t"
    if c == "\f":
        return "\\f"
    code = ord(c)
    if code < 0x20 or (ascii_only and code > 0x7E):
        if code > 0xFFFF:  # UTF-16 surrogate pair, as Java stores it
            code -= 0x10000
            return "\\u%04X\\u%04X" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF))
        return "\\u%04X" % code
    return c


def _escape_properties_key(key: str, ascii_only: bool = False) -> str:
    """
    Escape a Properties key for writing.

    Args:
        key: Key to escape

    Returns:
        Escaped key
    """
    out = []
    for i, c in enumerate(key):
        if c in " =:" or (i == 0 and c in "#!"):
            out.append("\\" + c)
        else:
            out.append(_escape_char(c, ascii_only))
    return "".join(out)


def _escape_properties_value(value: str, ascii_only: bool = False) -> str:
    """
    Escape a Properties value for writing: backslashes, control characters, a leading space (which
    the reader would skip) and, with ascii_only, non-ASCII characters as \\uXXXX.

    Args:
        value: Value to escape

    Returns:
        Escaped value
    """
    out = [_escape_char(c, ascii_only) for c in value]
    if out and out[0] == " ":
        out[0] = "\\ "
    return "".join(out)


_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)", re.DOTALL)
_SIMPLE_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def _tokens(raw: str) -> List[Tuple[int, int, str]]:
    """(raw start, raw end, character) for every character of an escaped key or value."""
    out: List[Tuple[int, int, str]] = []
    pos = 0
    while pos < len(raw):
        m = _ESCAPE.match(raw, pos) if raw[pos] == "\\" else None
        if m is None:
            out.append((pos, pos + 1, raw[pos]))
            pos += 1
            continue
        s = m.group(1)
        if s[0] == "u" and len(s) == 5:
            ch = chr(int(s[1:], 16))
            if 0xDC00 <= ord(ch) <= 0xDFFF and out and 0xD800 <= ord(out[-1][2]) <= 0xDBFF:
                start, _, high = out.pop()  # a UTF-16 surrogate pair is one character
                out.append((start, m.end(), chr(0x10000 + ((ord(high) - 0xD800) << 10) + (ord(ch) - 0xDC00))))
            else:
                out.append((pos, m.end(), ch))
        else:
            out.append((pos, m.end(), _SIMPLE_ESCAPES.get(s, s)))
        pos = m.end()
    return out


def unescape(value: str) -> str:
    """
    Unescape a Properties key or value as java.util.Properties does: \\uXXXX, \\t, \\n, \\r, \\f,
    and a backslash before any other character is dropped (\\: -> :, \\= -> =, \\\\ -> \\).
    """
    return "".join(ch for _, _, ch in _tokens(value))


def _unescape_properties_value(value: str) -> str:
    """Backward-compatible name for unescape()."""
    return unescape(value)


def is_valid_properties_file(file_path: str) -> bool:
    """
    Check if a file is a valid Properties file.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file is a valid Properties file, False otherwise
    """
    try:
        content = read_properties_file(file_path)
        return isinstance(content, dict)
    except (FileNotFoundError, ValueError, UnicodeDecodeError):
        return False


def get_properties_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from Properties file path.

    Args:
        file_path: Path to the Properties file

    Returns:
        Language code if found, None otherwise
    """
    # Try to extract from filename (e.g., messages_en.properties -> en, messages_en_US.properties -> en_US)
    filename = os.path.basename(file_path)
    if '_' in filename:
        parts = filename.split('_')
        if len(parts) >= 2:
            # Get the part before .properties (last part)
            name_part = parts[-1].split('.')[0]
            # Check if it looks like a valid language code (2-3 letters)
            if len(name_part) in [2, 3] and name_part.isalpha():
                # Check if the previous part forms a valid locale (e.g., en_US)
                # Locale format: lowercase 2-letter language code + underscore + 2 uppercase letters (country code)
                if len(parts) >= 3:
                    second_last = parts[-2]
                    # Validate locale: language code should be lowercase 2 letters, country code should be uppercase 2 letters
                    if (len(second_last) == 2 and second_last.islower() and second_last.isalpha() and
                        len(name_part) == 2 and name_part.isupper() and name_part.isalpha()):
                        return f"{second_last}_{name_part}"
                # Return just the language code (can be any case, but typically lowercase)
                return name_part

    return None
