"""
TypeScript translation file handler.

A translation module is an exported object literal:

    export const en = {
      greeting: 'Hello, {{name}}!',
      welcome: `Welcome back, ${user.name}`,
      nested: { items: "{count, plural, one {# item} other {# items}}" },
    };

The object literal is read with a small JavaScript literal parser (parse_ts_module), not by
rewriting it into Python syntax: the old regex rewrite turned "true"/"null" inside values into
"True"/"None", cut "https://…" at "//" as if it were a comment, and could not read backtick
template literals at all.

Every string value keeps its literal's span and quote style ('…', "…" or `…`), so writers can
replace values in place with the escaping of that literal: an apostrophe in a single-quoted value
becomes \\', and a translated backtick or "${" inside a template literal is escaped instead of
starting a new substitution. A template literal's ${…} substitutions are kept verbatim in the value
(they are JavaScript expressions evaluated by the app, i.e. placeholders).
"""

import os
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from algebras.utils.nested_structure_handler import set_nested_value

KeyPath = Tuple[str, ...]

QUOTES = ("'", '"', "`")


class TSParseError(ValueError):
    def __init__(self, message: str, offset: Optional[int] = None, text: Optional[str] = None):
        if offset is not None and text is not None:
            line = text.count("\n", 0, offset) + 1
            column = offset - (text.rfind("\n", 0, offset) + 1) + 1
            message = f"{message} (line {line}, column {column})"
        super().__init__(message)
        self.offset = offset


@dataclass(frozen=True)
class TSLiteral:
    """A string value's literal in the file."""

    start: int  # offset of the opening quote
    end: int  # offset after the closing quote
    quote: str  # ', " or `
    # Template literals: the ${…} substitutions, verbatim and in order.
    substitutions: Tuple[str, ...] = ()
    # Lenient parsing only: the literal had unescaped quotes of its own kind inside.
    recovered: bool = False


@dataclass
class TSDocument:
    text: str
    data: Dict[str, Any]
    literals: Dict[KeyPath, TSLiteral] = field(default_factory=dict)
    export_name: Optional[str] = None

    @property
    def recovered(self) -> Dict[KeyPath, TSLiteral]:
        return {p: lit for p, lit in self.literals.items() if lit.recovered}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_EXPORT_RE = re.compile(
    r"export\s+(?:default\s+|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]*?)?=\s*)", re.MULTILINE
)
_IDENT_RE = re.compile(r"[A-Za-z_$À-￿][\w$À-￿]*")
_NUMBER_RE = re.compile(r"-?(?:0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|(?:\d[\d_]*(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")
_KEYWORDS = {"true": True, "false": False, "null": None, "undefined": None}
_SIMPLE_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v"}
# What may follow the closing quote of a value (lenient parsing tells an unescaped quote inside a
# value from the real closing quote by this).
_AFTER_VALUE = ",}]"


class _Parser:
    def __init__(self, text: str, lenient: bool = False):
        self.text = text
        self.n = len(text)
        self.lenient = lenient
        self.literals: Dict[KeyPath, TSLiteral] = {}

    def error(self, message: str, offset: int) -> TSParseError:
        return TSParseError(message, offset, self.text)

    # -- whitespace and comments -------------------------------------------

    def ws(self, i: int) -> int:
        t = self.text
        while i < self.n:
            c = t[i]
            if c in " \t\r\n﻿   ":
                i += 1
            elif t.startswith("//", i):
                j = t.find("\n", i)
                i = self.n if j == -1 else j + 1
            elif t.startswith("/*", i):
                j = t.find("*/", i + 2)
                if j == -1:
                    raise self.error("Unterminated comment", i)
                i = j + 2
            else:
                break
        return i

    # -- values ------------------------------------------------------------

    def value(self, i: int, path: KeyPath) -> Tuple[Any, int]:
        i = self.ws(i)
        if i >= self.n:
            raise self.error("Unexpected end of file", i)
        c = self.text[i]
        if c == "{":
            return self.obj(i, path)
        if c == "[":
            return self.arr(i, path)
        if c in ("'", '"'):
            value, end, recovered = self.string(i, value_position=True)
            self.literals[path] = TSLiteral(i, end, c, (), recovered)
            return value, end
        if c == "`":
            value, end, subs, recovered = self.template(i, value_position=True)
            self.literals[path] = TSLiteral(i, end, c, tuple(subs), recovered)
            return value, end
        m = _NUMBER_RE.match(self.text, i)
        if m and m.end() > i and not (m.group(0) == "-"):
            raw = m.group(0).replace("_", "")
            try:
                if raw.lstrip("-")[:2].lower() in ("0x", "0o", "0b"):
                    return int(raw, 0), m.end()
                number = float(raw)
                return (int(number) if number.is_integer() and re.fullmatch(r"-?\d+", raw) else number), m.end()
            except ValueError:
                raise self.error(f"Invalid number {m.group(0)!r}", i)
        m = _IDENT_RE.match(self.text, i)
        if m and m.group(0) in _KEYWORDS:
            return _KEYWORDS[m.group(0)], m.end()
        raise self.error(f"Unsupported value starting with {self.text[i:i + 20]!r}", i)

    def key(self, i: int) -> Tuple[str, int]:
        c = self.text[i]
        if c in ("'", '"'):
            value, end, _ = self.string(i, value_position=False)
            return value, end
        if c == "`":
            value, end, subs, _ = self.template(i, value_position=False)
            if subs:
                raise self.error("Computed template keys are not supported", i)
            return value, end
        m = _IDENT_RE.match(self.text, i)
        if m:
            return m.group(0), m.end()
        m = _NUMBER_RE.match(self.text, i)
        if m and m.end() > i:
            return m.group(0), m.end()
        raise self.error(f"Unsupported key starting with {self.text[i:i + 20]!r}", i)

    def obj(self, i: int, path: KeyPath) -> Tuple[Dict[str, Any], int]:
        result: Dict[str, Any] = {}
        i = self.ws(i + 1)
        while True:
            if i >= self.n:
                raise self.error("Unterminated object", i)
            if self.text[i] == "}":
                return result, i + 1
            key, i = self.key(i)
            i = self.ws(i)
            if self.text[i : i + 1] != ":":
                raise self.error(f"Expected ':' after key {key!r}", i)
            result[key], i = self.value(i + 1, path + (key,))
            i = self.ws(i)
            if self.text[i : i + 1] == ",":
                i = self.ws(i + 1)
            elif self.text[i : i + 1] != "}":
                raise self.error("Expected ',' or '}'", i)

    def arr(self, i: int, path: KeyPath) -> Tuple[List[Any], int]:
        result: List[Any] = []
        i = self.ws(i + 1)
        while True:
            if i >= self.n:
                raise self.error("Unterminated array", i)
            if self.text[i] == "]":
                return result, i + 1
            item, i = self.value(i, path + (str(len(result)),))
            result.append(item)
            i = self.ws(i)
            if self.text[i : i + 1] == ",":
                i = self.ws(i + 1)
            elif self.text[i : i + 1] != "]":
                raise self.error("Expected ',' or ']'", i)

    # -- strings -----------------------------------------------------------

    def _closes(self, i: int, value_position: bool) -> bool:
        """Is the quote at i the real end of the literal (lenient parsing)?"""
        if not (self.lenient and value_position):
            return True
        try:
            j = self.ws(i + 1)
        except TSParseError:
            return True
        return j >= self.n or self.text[j] in _AFTER_VALUE

    def escape(self, i: int) -> Tuple[str, int]:
        """Decode the escape sequence starting at the backslash at i."""
        t = self.text
        if i + 1 >= self.n:
            raise self.error("Unterminated escape", i)
        c = t[i + 1]
        if c in _SIMPLE_ESCAPES:
            return _SIMPLE_ESCAPES[c], i + 2
        if c == "0" and not t[i + 2 : i + 3].isdigit():
            return "\0", i + 2
        if c == "x":
            h = t[i + 2 : i + 4]
            if not re.fullmatch(r"[0-9a-fA-F]{2}", h):
                raise self.error("Invalid \\x escape", i)
            return chr(int(h, 16)), i + 4
        if c == "u":
            if t[i + 2 : i + 3] == "{":
                j = t.find("}", i + 3)
                h = t[i + 3 : j] if j != -1 else ""
                if not re.fullmatch(r"[0-9a-fA-F]{1,6}", h):
                    raise self.error("Invalid \\u{…} escape", i)
                return chr(int(h, 16)), j + 1
            h = t[i + 2 : i + 6]
            if not re.fullmatch(r"[0-9a-fA-F]{4}", h):
                raise self.error("Invalid \\u escape", i)
            return chr(int(h, 16)), i + 6
        if c == "\r":
            return "", i + (3 if t[i + 2 : i + 3] == "\n" else 2)
        if c in "\n  ":
            return "", i + 2
        return c, i + 2

    def string(self, i: int, value_position: bool) -> Tuple[str, int, bool]:
        """A '…' or "…" literal at i: (value, end, recovered)."""
        t = self.text
        quote = t[i]
        out: List[str] = []
        recovered = False
        j = i + 1
        while j < self.n:
            c = t[j]
            if c == "\\":
                s, j = self.escape(j)
                out.append(s)
            elif c == quote:
                if self._closes(j, value_position):
                    return _join(out), j + 1, recovered
                out.append(c)  # an unescaped quote inside the value
                recovered = True
                j += 1
            elif c in "\r\n":
                break
            else:
                out.append(c)
                j += 1
        raise self.error("Unterminated string", i)

    def template(self, i: int, value_position: bool) -> Tuple[str, int, List[str], bool]:
        """A `…` literal at i: (value with ${…} kept verbatim, end, substitutions, recovered)."""
        t = self.text
        out: List[str] = []
        subs: List[str] = []
        recovered = False
        j = i + 1
        while j < self.n:
            c = t[j]
            if c == "\\":
                s, j = self.escape(j)
                out.append(s)
            elif c == "`":
                if self._closes(j, value_position):
                    return _join(out), j + 1, subs, recovered
                out.append(c)
                recovered = True
                j += 1
            elif c == "$" and t.startswith("${", j):
                end = self.expression_end(j + 2)
                subs.append(t[j:end])
                out.append(t[j:end])
                j = end
            elif c == "\r":
                # Template literals normalize CRLF and CR to LF.
                out.append("\n")
                j += 2 if t[j + 1 : j + 2] == "\n" else 1
            else:
                out.append(c)
                j += 1
        raise self.error("Unterminated template literal", i)

    def expression_end(self, i: int) -> int:
        """End of a ${…} substitution whose expression starts at i (after the closing brace)."""
        t = self.text
        depth = 1
        start = i
        while i < self.n:
            c = t[i]
            if c in ("'", '"'):
                _, i, _ = _Parser(t).string(i, value_position=False)
                continue
            if c == "`":
                _, i, _, _ = _Parser(t).template(i, value_position=False)
                continue
            if t.startswith("//", i) or t.startswith("/*", i):
                i = self.ws(i)
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        raise self.error("Unterminated ${…} substitution", start - 2)


def _join(parts: List[str]) -> str:
    s = "".join(parts)
    if any("\ud800" <= ch <= "\udfff" for ch in s):
        # 😀 escapes: combine surrogate pairs into one character.
        s = s.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    return s


def _object_start(text: str) -> Tuple[int, Optional[str]]:
    match = _EXPORT_RE.search(text)
    if not match:
        raise TSParseError("No valid TypeScript export found")
    brace = text.find("{", match.end())
    if brace == -1:
        raise TSParseError("No opening brace found after export statement")
    return brace, match.group(1)


def parse_ts_module(text: str, lenient: bool = False) -> TSDocument:
    """
    Parse a translation module's exported object literal.

    With lenient=True, a quote of a value's own kind that is not followed by ',', '}' or ']' is
    read as part of the value (an unescaped apostrophe in 'Don't'), and the literal is marked
    `recovered`, so a file broken that way can still be checked and fixed.
    """
    start, export_name = _object_start(text)
    parser = _Parser(text, lenient)
    data, _ = parser.obj(start, ())
    return TSDocument(text=text, data=data, literals=parser.literals, export_name=export_name)


def read_ts_document(file_path: str, lenient: bool = False) -> TSDocument:
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    try:
        return parse_ts_module(text, lenient)
    except TSParseError as e:
        raise TSParseError(f"Failed to parse TypeScript object in {file_path}: {e}") from e


def read_ts_translation_file(file_path: str) -> Dict[str, Any]:
    """
    Read a TypeScript translation file and return the exported object as a dict.

    Raises ValueError if the file has no exported object literal or it cannot be parsed.
    """
    return read_ts_document(file_path).data


# ---------------------------------------------------------------------------
# Encoding string literals
# ---------------------------------------------------------------------------


def template_substitutions(value: str) -> List[Tuple[int, int]]:
    """Spans of balanced ${…} in a value (string and template literals inside are skipped)."""
    spans: List[Tuple[int, int]] = []
    i = 0
    while True:
        i = value.find("${", i)
        if i == -1:
            return spans
        try:
            end = _Parser(value).expression_end(i + 2)
        except TSParseError:
            return spans
        spans.append((i, end))
        i = end


def encode_ts_string(value: str, quote: str = '"', substitutions: Optional[Sequence[str]] = None) -> str:
    """
    The string literal for `value` in the given quote style.

    For a template literal (quote "`"), `substitutions` lists the ${…} that are real substitutions
    (normally the ones of the source value's literal); every other "${" in the value, e.g. one a
    translator wrote, is escaped as "\\${". With substitutions=None, every balanced ${…} in the
    value is a substitution.
    """
    if quote not in QUOTES:
        raise ValueError(f"Unknown quote {quote!r}")
    if quote != "`":
        out = []
        for ch in value:
            if ch == "\\":
                out.append("\\\\")
            elif ch == quote:
                out.append("\\" + quote)
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            elif ch in "  ":
                out.append(f"\\u{ord(ch):04x}")
            elif ord(ch) < 0x20:
                out.append(f"\\x{ord(ch):02x}")
            else:
                out.append(ch)
        return quote + "".join(out) + quote

    spans = template_substitutions(value)
    if substitutions is not None:
        allowed = Counter(substitutions)
        kept = []
        for s, e in spans:
            if allowed[value[s:e]] > 0:
                allowed[value[s:e]] -= 1
                kept.append((s, e))
        spans = kept
    out = []
    i = 0
    for s, e in spans + [(len(value), len(value))]:
        for j in range(i, s):
            ch = value[j]
            if ch == "\\":
                out.append("\\\\")
            elif ch == "`":
                out.append("\\`")
            elif ch == "$" and value[j + 1 : j + 2] == "{":
                out.append("\\$")
            elif ch == "\r":
                out.append("\\r")
            else:
                out.append(ch)
        out.append(value[s:e])
        i = e
    return "`" + "".join(out) + "`"


def _choose_quote(
    target: Optional[TSLiteral], source: Optional[TSLiteral]
) -> Tuple[str, Optional[Tuple[str, ...]]]:
    """
    Quote style and template substitutions for a value written to the target: the target
    literal's style, else the source's, else double quotes. A source template literal with
    substitutions always stays a template literal, so its ${…} are evaluated, not shown as text.
    """
    if source is not None and source.quote == "`" and source.substitutions:
        return "`", source.substitutions
    if target is not None:
        if target.quote == "`":
            return "`", source.substitutions if source is not None else target.substitutions
        return target.quote, None
    if source is not None:
        return source.quote, source.substitutions if source.quote == "`" else None
    return '"', None


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def write_ts_translation_file(
    file_path: str,
    content: Dict[str, Any],
    export_name: str = None,
    quotes: Optional[Dict[KeyPath, Tuple[str, Optional[Tuple[str, ...]]]]] = None,
) -> None:
    """
    Write a dictionary to a TypeScript translation file.

    Args:
        file_path: Path to the TypeScript file
        content: Dictionary to write
        export_name: Name of the exported constant (defaults to language code from filename)
        quotes: Optional {key path: (quote, template substitutions)} per string value;
            double quotes otherwise
    """
    if export_name is None:
        export_name = os.path.basename(file_path).split(".")[0]

    ts_object = _python_dict_to_ts_object(content, indent=0, quotes=quotes)
    _write_checked(file_path, f"export const {export_name} = {ts_object};\n")


def _write_checked(file_path: str, text: str) -> None:
    """Write the module only if it parses back; a broken file is never written."""
    parse_ts_module(text)
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _python_dict_to_ts_object(
    obj: Any,
    indent: int = 0,
    quotes: Optional[Dict[KeyPath, Tuple[str, Optional[Tuple[str, ...]]]]] = None,
    _path: KeyPath = (),
) -> str:
    """
    Convert a Python value to TypeScript literal syntax.

    Args:
        obj: Python object to convert
        indent: Current indentation level
        quotes: Optional {key path: (quote, template substitutions)} for string values
    """
    spaces = "  " * indent
    inner_spaces = "  " * (indent + 1)

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = ["{"]
        for key, value in obj.items():
            ts_value = _python_dict_to_ts_object(value, indent + 1, quotes, _path + (str(key),))
            lines.append(f"{inner_spaces}{_format_ts_key(str(key))}: {ts_value},")
        lines.append(f"{spaces}}}")
        return "\n".join(lines)

    if isinstance(obj, list):
        if not obj:
            return "[]"
        lines = ["["]
        for index, item in enumerate(obj):
            ts_value = _python_dict_to_ts_object(item, indent + 1, quotes, _path + (str(index),))
            lines.append(f"{inner_spaces}{ts_value},")
        lines.append(f"{spaces}]")
        return "\n".join(lines)

    if isinstance(obj, str):
        quote, substitutions = (quotes or {}).get(_path, ('"', None))
        if quote == "`" and substitutions is None:
            substitutions = ()
        return encode_ts_string(obj, quote, substitutions)

    if isinstance(obj, bool):
        return "true" if obj else "false"

    if obj is None:
        return "null"

    return str(obj)


def _format_ts_key(key: str) -> str:
    """Format a key for TypeScript object syntax, adding quotes if necessary."""
    if re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$", key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _resolve_path(key: str, literals: Dict[KeyPath, Any]) -> Optional[KeyPath]:
    """The literal a dotted translation key refers to ("a.b" -> ("a", "b"), or a key with a dot)."""
    split = tuple(key.split("."))
    if split in literals:
        return split
    if (key,) in literals:
        return (key,)
    return None


def replace_literals(
    text: str,
    literals: Dict[KeyPath, TSLiteral],
    values: Dict[KeyPath, str],
    source_literals: Optional[Dict[KeyPath, TSLiteral]] = None,
) -> str:
    """Replace only the given values' literals in `text`, each escaped for its quote style."""
    source_literals = source_literals or {}
    for path in sorted(values, key=lambda p: literals[p].start, reverse=True):
        literal = literals[path]
        if source_literals:
            quote, subs = _choose_quote(literal, source_literals.get(path))
        else:
            quote, subs = literal.quote, None
        text = text[: literal.start] + encode_ts_string(values[path], quote, subs) + text[literal.end :]
    return text


def _literals_of(file_path: Optional[str]) -> Dict[KeyPath, TSLiteral]:
    if not file_path or not os.path.exists(file_path):
        return {}
    try:
        return read_ts_document(file_path).literals
    except (OSError, ValueError):
        return {}


def _quote_map(
    target_literals: Dict[KeyPath, TSLiteral], source_literals: Dict[KeyPath, TSLiteral]
) -> Dict[KeyPath, Tuple[str, Optional[Tuple[str, ...]]]]:
    return {
        path: _choose_quote(target_literals.get(path), source_literals.get(path))
        for path in set(target_literals) | set(source_literals)
    }


def write_ts_translation_file_keeping_quotes(
    file_path: str, content: Dict[str, Any], source_file: Optional[str] = None, export_name: Optional[str] = None
) -> None:
    """write_ts_translation_file with each value in the quote style of the existing target or the source."""
    quotes = _quote_map(_literals_of(file_path), _literals_of(source_file))
    write_ts_translation_file(file_path, content, export_name, quotes)


def write_ts_translation_file_in_place(
    file_path: str,
    translations: Dict[str, str],
    export_name: Optional[str] = None,
    lock: Optional[threading.Lock] = None,
    source_file: Optional[str] = None,
) -> None:
    """
    Update a TypeScript translation file with new translations (dotted keys for nested values).

    If every key already has a string literal in the file, only those literals are replaced:
    comments, key order, formatting and each literal's quote style stay as they are. Otherwise the
    merged content is written out again, keeping each value's quote style (the target's, else the
    source file's). Template literal substitutions follow the source file: a translated "${" or
    backtick is escaped, never a new substitution. The written file always parses back.

    Args:
        file_path: Path to the TypeScript file
        translations: Dictionary of key -> translation to update/add
        export_name: Name of the exported constant (defaults to language code from filename)
        lock: Optional lock for thread-safe file access
        source_file: The source language module, for the quote style of new values
    """
    if lock:
        lock.acquire()
    try:
        source_literals = _literals_of(source_file)

        doc: Optional[TSDocument] = None
        if os.path.exists(file_path):
            try:
                doc = read_ts_document(file_path)
            except (OSError, ValueError):
                doc = None  # unreadable: written again from scratch below

        if doc is not None:
            in_place: Optional[Dict[KeyPath, str]] = {}
            for key, value in translations.items():
                path = _resolve_path(key, doc.literals)
                if path is None or not isinstance(value, str):
                    in_place = None
                    break
                in_place[path] = value
            if in_place is not None:
                if in_place:
                    _write_checked(file_path, replace_literals(doc.text, doc.literals, in_place, source_literals))
                return

        existing_content = doc.data if doc is not None else {}
        if export_name is None:
            export_name = (doc.export_name if doc is not None else None) or os.path.basename(file_path).split(".")[0]

        for key, value in translations.items():
            if "." in key and (key,) not in (doc.literals if doc else {}):
                set_nested_value(existing_content, key.split("."), value)
            else:
                existing_content[key] = value

        existing_content = convert_numeric_dicts_to_lists(existing_content)

        quotes = _quote_map(doc.literals if doc is not None else {}, source_literals)
        write_ts_translation_file(file_path, existing_content, export_name, quotes)
    finally:
        if lock:
            lock.release()


def convert_numeric_dicts_to_lists(obj: Any) -> Any:
    """
    Recursively convert dictionaries with only numeric keys to lists.
    This ensures that arrays are properly represented as lists in Python.

    Args:
        obj: Object to convert (dict, list, or primitive)

    Returns:
        Converted object with numeric-key dicts converted to lists
    """
    if isinstance(obj, dict):
        processed_dict = {k: convert_numeric_dicts_to_lists(v) for k, v in obj.items()}
        if processed_dict:
            all_numeric = all(isinstance(k, str) and k.isdigit() for k in processed_dict.keys())
            if all_numeric:
                max_index = max(int(k) for k in processed_dict.keys())
                arr = [None] * (max_index + 1)
                for k, v in processed_dict.items():
                    arr[int(k)] = v
                return arr
        return processed_dict
    elif isinstance(obj, list):
        return [convert_numeric_dicts_to_lists(item) for item in obj]
    else:
        return obj
