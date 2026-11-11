r"""
Android XML localization file handler

Values are read as the element's full inner content. Text runs are unescaped (XML entities and
Android backslash escapes), and child elements are kept as markup with their namespace prefix:

    <string name="x">Hello <xliff:g id="n">%1$s</xliff:g>, it\'s <b>here</b></string>
    -> "Hello <xliff:g id="n">%1$s</xliff:g>, it's <b>here</b>"

When writing, a value is written back as mixed content (child elements) if the string has markup
in the source or in the existing target element; otherwise it is plain text. Escaping applies to
text runs only, so restored markup is never written as &lt;xliff:g&gt;.

Text runs follow aapt2's rules, and the reader and the writers are symmetric:

    value   '    "    \    newline  tab   leading @ / ?    (\uXXXX is kept as written)
    raw     \'   \"   \\   \n       \t    \@ / \?

An unescaped " opens or closes a quoted section: the reader drops it (it is not part of the value)
and keeps the whitespace inside it. A value with leading or trailing spaces is written quoted so
aapt2 keeps them, and an element whose whole content was quoted ("It's") stays quoted when it is
rewritten. This escaping is what the file format requires, so it never depends on
api.normalize_strings, which only cleans up escapes in the model's output
(see algebras/services/string_normalizer.py).
"""

import html
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

PLURALS_SUFFIX = ".__plurals__"
QUANTITY_ORDER = ["zero", "one", "two", "few", "many", "other"]

XLIFF_NS = "urn:oasis:names:tc:xliff:document:1.2"
TOOLS_NS = "http://schemas.android.com/tools"
_DEFAULT_NAMESPACES = {"xliff": XLIFF_NS, "tools": TOOLS_NS}

for _prefix, _uri in _DEFAULT_NAMESPACES.items():
    ET.register_namespace(_prefix, _uri)

# Key path of a value: ("name",) for <string>, ("name.__plurals__", quantity) for a plural item.
KeyPath = Tuple[str, ...]

# A whole value that only references another resource: @string/app_name, @android:string/ok, ?attr/x.
_RESOURCE_REFERENCE = re.compile(r"^\s*[@?](?:[A-Za-z_][\w.]*:)?[A-Za-z_][\w]*/[\w.]+\s*$")

# \uXXXX escapes are kept as written in values (the translator masks them as placeholders).
_UNICODE_ESCAPE = re.compile(r"\\u[0-9A-Fa-f]{4}")
_BACKSLASH_ESCAPES = {"n": "\n", "t": "\t"}
# Whitespace aapt2 trims at the ends of a value when it is outside quotes.
_XML_SPACE = " \t\n\r"

_TAG_TOKEN = re.compile(r"<(/?)([A-Za-z_][\w.\-]*(?::[A-Za-z_][\w.\-]*)?)((?:\s+[^<>]*?)?)\s*(/?)>")
_ATTRIBUTE = re.compile(r"([A-Za-z_][\w.\-]*(?::[A-Za-z_][\w.\-]*)?)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")


def _parser() -> ET.XMLParser:
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def _file_namespaces(file_path: str) -> Dict[str, str]:
    """prefix -> uri for every namespace declared in the file, plus the Android defaults."""
    namespaces = dict(_DEFAULT_NAMESPACES)
    try:
        for _event, (prefix, uri) in ET.iterparse(file_path, events=("start-ns",)):
            if prefix:
                namespaces[prefix] = uri
    except ET.ParseError:
        pass
    return namespaces


def _register_namespaces(namespaces: Dict[str, str]) -> None:
    for prefix, uri in namespaces.items():
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass  # reserved prefix such as ns0


def is_resource_reference(value: str) -> bool:
    """True for a whole value like '@string/app_name' (never translated)."""
    return isinstance(value, str) and bool(_RESOURCE_REFERENCE.match(value))


def _is_translatable(elem: ET.Element) -> bool:
    return (elem.get("translatable") or "").strip().lower() != "false"


def read_android_xml_file(file_path: str) -> Dict[str, Any]:
    """
    Read an Android XML localization file and extract strings and plurals.

    Strings with translatable="false" and whole-value resource references (@string/...) are left
    out: they are not translated, and Android falls back to the default resources for them.

    Args:
        file_path: Path to the Android XML file

    Returns:
        Dictionary containing the translation content
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in {file_path}: {str(e)}")

    if root.tag != 'resources':
        raise ValueError(f"Expected 'resources' root element in {file_path}, found '{root.tag}'")

    prefixes = {uri: prefix for prefix, uri in _file_namespaces(file_path).items()}
    result = {}

    # Process string elements
    for string_elem in root.findall('string'):
        name = string_elem.get('name')
        if name is None or not _is_translatable(string_elem):
            continue

        if not _has_child_elements(string_elem) and is_resource_reference(string_elem.text or ""):
            continue  # judged on the raw text: \@string/x is literal text, not a reference
        text = _get_element_text(string_elem, prefixes)
        if text is not None:
            result[name] = text

    # Process plurals elements
    for plurals_elem in root.findall('plurals'):
        name = plurals_elem.get('name')
        if name is None or not _is_translatable(plurals_elem):
            continue

        plural_dict = {}
        for item_elem in plurals_elem.findall('item'):
            quantity = item_elem.get('quantity')
            if quantity is None:
                continue

            text = _get_element_text(item_elem, prefixes)
            if text is not None:
                plural_dict[quantity] = text

        if plural_dict:
            # Store plurals with a special key structure
            result[f"{name}{PLURALS_SUFFIX}"] = plural_dict

    return result


def read_android_string_attributes(file_path: str) -> Dict[KeyPath, Dict[str, str]]:
    """Attributes of every <string> / plural <item> by key path (e.g. formatted="false")."""
    try:
        root = ET.parse(file_path).getroot()
    except (ET.ParseError, OSError):
        return {}
    attributes: Dict[KeyPath, Dict[str, str]] = {}
    for string_elem in root.findall('string'):
        name = string_elem.get('name')
        if name is not None:
            attributes[(name,)] = dict(string_elem.attrib)
    for plurals_elem in root.findall('plurals'):
        name = plurals_elem.get('name')
        if name is None:
            continue
        for item_elem in plurals_elem.findall('item'):
            quantity = item_elem.get('quantity')
            if quantity is not None:
                # The item inherits the <plurals> attributes (formatted="false" may sit on either).
                merged = dict(plurals_elem.attrib)
                merged.update(item_elem.attrib)
                attributes[(f"{name}{PLURALS_SUFFIX}", quantity)] = merged
    return attributes


def android_markup_paths(file_path: Optional[str]) -> Set[KeyPath]:
    """Key paths whose element contains child elements (<xliff:g>, <b> ...) in this file."""
    if not file_path or not os.path.exists(file_path):
        return set()
    try:
        root = ET.parse(file_path).getroot()
    except ET.ParseError:
        return set()
    paths: Set[KeyPath] = set()
    for string_elem in root.findall('string'):
        if string_elem.get('name') is not None and _has_child_elements(string_elem):
            paths.add((string_elem.get('name'),))
    for plurals_elem in root.findall('plurals'):
        name = plurals_elem.get('name')
        if name is None:
            continue
        for item_elem in plurals_elem.findall('item'):
            if item_elem.get('quantity') is not None and _has_child_elements(item_elem):
                paths.add((f"{name}{PLURALS_SUFFIX}", item_elem.get('quantity')))
    return paths


def _has_child_elements(elem: ET.Element) -> bool:
    return any(isinstance(child.tag, str) for child in elem)


def _sort_quantities(quantities: Iterable[str]) -> List[str]:
    return sorted(
        quantities,
        key=lambda x: QUANTITY_ORDER.index(x) if x in QUANTITY_ORDER else len(QUANTITY_ORDER),
    )


# Attributes carried from the source element to a newly written target element.
_COPIED_ATTRIBUTES = ("formatted",)


def _source_info(source_file: Optional[str]) -> Tuple[Set[KeyPath], Dict[KeyPath, Dict[str, str]]]:
    if not source_file or not os.path.exists(source_file):
        return set(), {}
    attributes = read_android_string_attributes(source_file)
    # <plurals> attributes, keyed by the plural key alone.
    try:
        root = ET.parse(source_file).getroot()
        for plurals_elem in root.findall('plurals'):
            if plurals_elem.get('name') is not None:
                attributes[(plurals_elem.get('name') + PLURALS_SUFFIX,)] = dict(plurals_elem.attrib)
    except ET.ParseError:
        pass
    return android_markup_paths(source_file), attributes


def _copy_source_attributes(elem: ET.Element, path: KeyPath, source_attributes: Dict[KeyPath, Dict[str, str]]) -> None:
    for name in _COPIED_ATTRIBUTES:
        value = source_attributes.get(path, {}).get(name)
        if value is not None and elem.get(name) is None:
            elem.set(name, value)


def _wants_markup(path: KeyPath, value: str, markup_paths: Optional[Set[KeyPath]], existing: Optional[ET.Element]) -> bool:
    if existing is not None and _has_child_elements(existing):
        return True
    if markup_paths and path in markup_paths:
        return True
    return "<xliff:g" in value


def write_android_xml_file(
    file_path: str,
    content: Dict[str, Any],
    source_file: Optional[str] = None,
) -> None:
    """
    Write a dictionary to an Android XML localization file.

    Args:
        file_path: Path to the Android XML file
        content: Dictionary to write
        source_file: The source-language file. Strings with markup there are written with
            markup (child elements), and formatted="false" is carried over.
    """
    markup_paths, source_attributes = _source_info(source_file)
    root = ET.Element('resources')
    namespaces = dict(_DEFAULT_NAMESPACES)

    for key in sorted(content.keys()):
        value = content[key]

        if key.endswith(PLURALS_SUFFIX):
            base_name = key[: -len(PLURALS_SUFFIX)]
            plurals_elem = ET.SubElement(root, 'plurals')
            plurals_elem.set('name', base_name)
            _copy_source_attributes(plurals_elem, (key,), source_attributes)

            if isinstance(value, dict):
                for quantity in _sort_quantities(value.keys()):
                    item_elem = ET.SubElement(plurals_elem, 'item')
                    item_elem.set('quantity', quantity)
                    text = str(value[quantity])
                    _set_element_value(
                        item_elem, text, _wants_markup((key, quantity), text, markup_paths, None), namespaces
                    )
        else:
            string_elem = ET.SubElement(root, 'string')
            string_elem.set('name', key)
            _copy_source_attributes(string_elem, (key,), source_attributes)
            text = str(value)
            _set_element_value(string_elem, text, _wants_markup((key,), text, markup_paths, None), namespaces)

    _indent_resources(root)
    tree = ET.ElementTree(root)
    with open(file_path, 'wb') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'.encode('utf-8'))
        tree.write(f, encoding='utf-8', xml_declaration=False)
        f.write(b'\n')


# ---------------------------------------------------------------------------
# Reading element content
# ---------------------------------------------------------------------------


class _ValueDecoder:
    """
    Decodes the text runs of one <string> / <item> the way aapt2 does. The quote state carries
    over child elements, as in aapt2. XML entities are already decoded by the parser.

    Each output piece is marked "kept" when aapt2 keeps it even at the ends of the value (escaped
    characters, text inside quotes, markup); only unkept whitespace is trimmed.
    """

    def __init__(self) -> None:
        self.in_quotes = False
        self.pieces: List[Tuple[str, bool]] = []

    def text(self, run: str) -> None:
        i = 0
        while i < len(run):
            c = run[i]
            if c == "\\" and i + 1 < len(run):
                if _UNICODE_ESCAPE.match(run, i):
                    self.pieces.append((run[i : i + 6], True))
                    i += 6
                    continue
                nxt = run[i + 1]
                # \' \" \\ \@ \? decode to the character itself, as do unknown escapes in aapt2.
                self.pieces.append((_BACKSLASH_ESCAPES.get(nxt, nxt), True))
                i += 2
                continue
            if c == '"':
                self.in_quotes = not self.in_quotes
            else:
                self.pieces.append((c, self.in_quotes))
            i += 1

    def markup(self, text: str) -> None:
        self.pieces.append((text, True))

    def value(self) -> str:
        pieces = self.pieces
        start, end = 0, len(pieces)
        while start < end and not pieces[start][1] and pieces[start][0] in _XML_SPACE:
            start += 1
        while end > start and not pieces[end - 1][1] and pieces[end - 1][0] in _XML_SPACE:
            end -= 1
        return "".join(p for p, _kept in pieces[start:end])


def _qualified(name: str, prefixes: Dict[str, str]) -> str:
    """'{uri}local' -> 'prefix:local'."""
    if name.startswith("{"):
        uri, local = name[1:].split("}", 1)
        prefix = prefixes.get(uri)
        return f"{prefix}:{local}" if prefix else local
    return name


def _decode_child(elem: ET.Element, prefixes: Dict[str, str], decoder: _ValueDecoder) -> None:
    if not isinstance(elem.tag, str):
        return  # comment / processing instruction inside a string
    tag = _qualified(elem.tag, prefixes)
    attrs = "".join(
        f' {_qualified(k, prefixes)}="{html.escape(v, quote=True)}"' for k, v in elem.attrib.items()
    )
    if not elem.text and len(elem) == 0:
        decoder.markup(f"<{tag}{attrs}/>")
        return
    decoder.markup(f"<{tag}{attrs}>")
    _decode_content(elem, prefixes, decoder)
    decoder.markup(f"</{tag}>")


def _decode_content(elem: ET.Element, prefixes: Dict[str, str], decoder: _ValueDecoder) -> None:
    if elem.text:
        decoder.text(elem.text)
    for child in elem:
        _decode_child(child, prefixes, decoder)
        if child.tail:
            decoder.text(child.tail)


def _get_element_text(element: ET.Element, prefixes: Optional[Dict[str, str]] = None) -> str:
    """
    Extract the full inner content of a <string> or <item>.

    Text runs are unescaped (see _ValueDecoder); child elements (<xliff:g>, <b>, <a href> ...)
    are kept as markup, including their own text, with their namespace prefix.

    Args:
        element: The XML element
        prefixes: namespace uri -> prefix

    Returns:
        The content as a string
    """
    if prefixes is None:
        prefixes = {uri: prefix for prefix, uri in _DEFAULT_NAMESPACES.items()}
    decoder = _ValueDecoder()
    _decode_content(element, prefixes, decoder)
    return decoder.value()


# ---------------------------------------------------------------------------
# Writing element content
# ---------------------------------------------------------------------------


def _escape_android_text(text: str, quoted: bool = False) -> str:
    """
    Android backslash escapes for one text run (XML escaping is left to the serializer).

    Pure: the escaping is required by the format and never depends on configuration. Inside a
    quoted section (`quoted`), an apostrophe needs no escape. \\uXXXX escapes are kept as written.
    A leading @ / ? is handled by the caller, which knows where the value starts.
    """
    out = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\":
            if _UNICODE_ESCAPE.match(text, i):
                out.append(text[i : i + 6])
                i += 6
                continue
            out.append("\\\\")
        elif c == "'":
            out.append("'" if quoted else "\\'")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _needs_quotes(value: str) -> bool:
    """aapt2 trims unquoted whitespace at the ends of a value; quoting keeps it."""
    return bool(value) and (value[0] in " \r" or value[-1] in " \r")


def _is_wholly_quoted(elem: Optional[ET.Element]) -> bool:
    """True if the element's whole content is one quoted section, as in <string>"It's"</string>."""
    if elem is None:
        return False
    # Every text run in document order, with the positions of its unescaped quotes.
    runs: List[str] = []

    def walk(e: ET.Element) -> None:
        runs.append(e.text or "")
        for child in e:
            if isinstance(child.tag, str):
                walk(child)
            runs.append(child.tail or "")

    walk(elem)
    joined = "\x00".join(runs)  # never split an escape across runs
    quotes = []
    i = 0
    while i < len(joined):
        if joined[i] == "\\":
            i += 2
            continue
        if joined[i] == '"':
            quotes.append(i)
        i += 1
    stripped = joined.strip(_XML_SPACE)
    offset = len(joined) - len(joined.lstrip(_XML_SPACE))
    return (
        len(quotes) == 2
        and quotes[0] == offset
        and quotes[1] == offset + len(stripped) - 1
    )


def _escape_xml_text(text: str) -> str:
    """
    Escape text for XML content, handling Android-specific requirements.

    Kept for callers that build XML text by hand. The writers in this module set element text
    through ElementTree, which escapes &, < and > itself, so they use _escape_android_text.
    """
    return _escape_android_text(html.escape(text, quote=False))


def _element_name(name: str, namespaces: Dict[str, str]) -> Optional[str]:
    """'xliff:g' -> '{uri}g'; None for an unknown prefix."""
    if ":" in name:
        prefix, local = name.split(":", 1)
        uri = namespaces.get(prefix)
        return f"{{{uri}}}{local}" if uri else None
    return name


def _build_mixed_content(elem: ET.Element, value: str, namespaces: Dict[str, str], quoted: bool) -> bool:
    """Fill `elem` with text and child elements parsed from `value`. False if the markup is not well-formed."""
    stack: List[Tuple[ET.Element, str]] = [(elem, "")]

    def add_text(text: str) -> None:
        if not text:
            return
        text = _escape_android_text(text, quoted)
        parent = stack[-1][0]
        if len(parent):
            last = parent[-1]
            last.tail = (last.tail or "") + text
        else:
            parent.text = (parent.text or "") + text

    pos = 0
    for m in _TAG_TOKEN.finditer(value):
        add_text(value[pos : m.start()])
        pos = m.end()
        closing, name, attr_text, self_closing = m.group(1), m.group(2), m.group(3), m.group(4)
        if closing:
            if len(stack) == 1 or stack[-1][1] != name:
                return False
            stack.pop()
            continue
        tag = _element_name(name, namespaces)
        if tag is None:
            return False
        attrs = {}
        for a in _ATTRIBUTE.finditer(attr_text or ""):
            attr_name = _element_name(a.group(1), namespaces)
            if attr_name is None:
                return False
            raw = a.group(2) if a.group(2) is not None else a.group(3)
            attrs[attr_name] = html.unescape(raw)
        child = ET.SubElement(stack[-1][0], tag, attrs)
        if not self_closing:
            stack.append((child, name))
    add_text(value[pos:])
    return len(stack) == 1


def _set_element_value(
    elem: ET.Element, value: str, markup: bool, namespaces: Dict[str, str], quoted: bool = False
) -> None:
    """
    Write `value` (as the reader returns it) into `elem` with the escaping aapt2 requires.

    `quoted` keeps the element's whole content in one quoted section ("It's"); a value with
    leading or trailing spaces is always quoted, or aapt2 would trim them.
    """
    for child in list(elem):
        elem.remove(child)
    elem.text = None
    if is_resource_reference(value):
        elem.text = value.strip()  # @string/x stays a reference
        return
    quoted = quoted or _needs_quotes(value)
    built = False
    if markup and _TAG_TOKEN.search(value):
        built = _build_mixed_content(elem, value, namespaces, quoted)
        if not built:
            for child in list(elem):
                elem.remove(child)
            elem.text = None
    if not built:
        elem.text = _escape_android_text(value, quoted)
    if value[:1] in ("@", "?"):
        # Not a reference (checked above), so the leading character is escaped as text.
        elem.text = "\\" + (elem.text or "")
    if quoted:
        elem.text = '"' + (elem.text or "")
        if len(elem):
            elem[-1].tail = (elem[-1].tail or "") + '"'
        else:
            elem.text += '"'


def _indent_resources(root: ET.Element, space: str = "    ") -> None:
    """
    Indent <resources> children and <plurals> items only. Unlike ET.indent this never adds
    whitespace inside a <string> or <item>, where it would become part of the value.
    """
    children = list(root)
    if not children:
        return
    if not (root.text or "").strip():
        root.text = "\n" + space
    for i, child in enumerate(children):
        if not (child.tail or "").strip():
            child.tail = "\n" + (space if i < len(children) - 1 else "")
        if child.tag == "plurals":
            items = list(child)
            if not items:
                continue
            if not (child.text or "").strip():
                child.text = "\n" + space * 2
            for j, item in enumerate(items):
                if not (item.tail or "").strip():
                    item.tail = "\n" + (space * 2 if j < len(items) - 1 else space)


def _normalize_keys_to_update(keys_to_update: Optional[Set[str]]) -> Optional[Set[str]]:
    """'name.__plurals__.few' -> 'name.__plurals__' (the writer updates whole <plurals>)."""
    if keys_to_update is None:
        return None
    normalized = set()
    for key in keys_to_update:
        marker = PLURALS_SUFFIX + "."
        if marker in key:
            normalized.add(key.split(marker, 1)[0] + PLURALS_SUFFIX)
        else:
            normalized.add(key)
    return normalized


def write_android_xml_file_in_place(
    file_path: str,
    content: Dict[str, Any],
    keys_to_update: Optional[Set[str]] = None,
    source_file: Optional[str] = None,
) -> None:
    """
    Update an existing Android XML file in-place, preserving structure, comments, formatting, and order.

    Args:
        file_path: Path to the Android XML file
        content: Dictionary containing translations to update
        keys_to_update: Optional set of keys to update. If None, all keys in content will be updated.
        source_file: The source-language file. Strings with markup there are written with
            markup (child elements), and formatted="false" is carried over to new strings.
    """
    if not os.path.exists(file_path):
        # If file doesn't exist, fall back to regular write
        write_android_xml_file(file_path, content, source_file)
        return

    keys_to_update = _normalize_keys_to_update(keys_to_update)
    markup_paths, source_attributes = _source_info(source_file)

    # Read the existing file content as text to preserve comments and formatting
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # Extract original namespace declaration from <resources> tag to preserve it
    # Match: <resources xmlns:tools="..."> or <resources xmlns:ns0="..."> etc.
    namespace_match = re.search(r'<resources\s+([^>]*)>', original_content)
    original_resources_tag = None
    namespace_prefix_map = {}  # Map from namespace uri to original prefix (tools, etc.)

    if namespace_match:
        original_resources_tag = namespace_match.group(1)
        ns_decl_pattern = r'xmlns:([a-zA-Z_][a-zA-Z0-9_]*)=["\']([^"\']+)["\']'
        for ns_match in re.finditer(ns_decl_pattern, original_resources_tag):
            namespace_prefix_map[ns_match.group(2)] = ns_match.group(1)

    # Track which keys originally had &#160; entities (for preservation)
    keys_with_entities = set()
    for match in re.finditer(r'<string\s+name="([^"]+)"[^>]*>([^<]*)&#160;([^<]*)</string>', original_content):
        keys_with_entities.add(match.group(1))

    # Parse XML to get structure (comments included, so they are written back)
    try:
        tree = ET.parse(file_path, parser=_parser())
        root = tree.getroot()
    except ET.ParseError:
        # If parsing fails, fall back to regular write
        write_android_xml_file(file_path, content, source_file)
        return

    if root.tag != 'resources':
        # If not a resources file, fall back to regular write
        write_android_xml_file(file_path, content, source_file)
        return

    namespaces = _file_namespaces(file_path)
    _register_namespaces(namespaces)

    # Track which keys we've updated
    updated_keys = set()

    # Update existing string elements
    for string_elem in root.findall('string'):
        name = string_elem.get('name')
        if name is None:
            continue
        if keys_to_update is not None and name not in keys_to_update:
            continue
        if name in content and not isinstance(content[name], dict):
            new_value = str(content[name])
            _set_element_value(
                string_elem,
                new_value,
                _wants_markup((name,), new_value, markup_paths, string_elem),
                namespaces,
                quoted=_is_wholly_quoted(string_elem),
            )
            updated_keys.add(name)

    # Update existing plurals elements
    for plurals_elem in root.findall('plurals'):
        name = plurals_elem.get('name')
        if name is None:
            continue

        plural_key = f"{name}{PLURALS_SUFFIX}"
        if keys_to_update is not None and plural_key not in keys_to_update:
            continue

        if plural_key in content and isinstance(content[plural_key], dict):
            plural_dict = content[plural_key]
            present = set()
            for item_elem in plurals_elem.findall('item'):
                quantity = item_elem.get('quantity')
                if quantity and quantity in plural_dict:
                    present.add(quantity)
                    text = str(plural_dict[quantity])
                    _set_element_value(
                        item_elem,
                        text,
                        _wants_markup((plural_key, quantity), text, markup_paths, item_elem),
                        namespaces,
                        quoted=_is_wholly_quoted(item_elem),
                    )
            # Add the forms the target language needs but the file lacks, in CLDR order.
            for quantity in _sort_quantities(q for q in plural_dict if q not in present):
                new_item = ET.Element('item', {'quantity': quantity})
                text = str(plural_dict[quantity])
                _set_element_value(
                    new_item, text, _wants_markup((plural_key, quantity), text, markup_paths, None), namespaces
                )
                _insert_item(plurals_elem, new_item)
            updated_keys.add(plural_key)

    # Add new keys that don't exist in the file
    if keys_to_update is None:
        new_keys = set(content.keys()) - updated_keys
    else:
        new_keys = keys_to_update - updated_keys

    for key in sorted(new_keys):
        if key not in content:
            continue
        if key.endswith(PLURALS_SUFFIX):
            if isinstance(content[key], dict):
                plurals_elem = ET.SubElement(root, 'plurals')
                plurals_elem.set('name', key[: -len(PLURALS_SUFFIX)])
                _copy_source_attributes(plurals_elem, (key,), source_attributes)
                for quantity in _sort_quantities(content[key].keys()):
                    item_elem = ET.SubElement(plurals_elem, 'item')
                    item_elem.set('quantity', quantity)
                    text = str(content[key][quantity])
                    _set_element_value(
                        item_elem, text, _wants_markup((key, quantity), text, markup_paths, None), namespaces
                    )
        elif not isinstance(content[key], dict):
            string_elem = ET.SubElement(root, 'string')
            string_elem.set('name', key)
            _copy_source_attributes(string_elem, (key,), source_attributes)
            text = str(content[key])
            _set_element_value(string_elem, text, _wants_markup((key,), text, markup_paths, None), namespaces)

    _indent_resources(root)

    # Write with XML declaration and UTF-8 encoding
    with open(file_path, 'wb') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'.encode('utf-8'))
        tree.write(f, encoding='utf-8', xml_declaration=False)
        f.write(b'\n')

    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # Map ElementTree's generated prefixes (ns0, ns1) back to the original ones.
    et_to_original = {}
    if namespace_prefix_map:
        et_ns_pattern = r'xmlns:(ns\d+)=["\']([^"\']+)["\']'
        for et_match in re.finditer(et_ns_pattern, file_content):
            if et_match.group(2) in namespace_prefix_map:
                et_to_original[et_match.group(1)] = namespace_prefix_map[et_match.group(2)]

    with open(file_path, 'w', encoding='utf-8') as f:
        lines = file_content.split('\n')
        for i, line in enumerate(lines):
            # Restore the original attributes of the <resources> tag (namespace declarations)
            if '<resources' in line and original_resources_tag:
                if re.search(r'<resources\s+[^>]*>', line):
                    line = re.sub(r'<resources\s+[^>]*>', lambda _m: f'<resources {original_resources_tag}>', line)
                else:
                    line = re.sub(r'<resources>', lambda _m: f'<resources {original_resources_tag}>', line)
                lines[i] = line

            # Restore namespace prefixes (e.g., ns0:ignore -> tools:ignore)
            if et_to_original:
                for et_prefix, original_prefix in et_to_original.items():
                    pattern = rf'\b{re.escape(et_prefix)}:([a-zA-Z_][a-zA-Z0-9_]*)'
                    line = re.sub(pattern, rf'{original_prefix}:\1', line)
                lines[i] = line

            # Keep non-breaking spaces as &#160; in strings that used the entity
            if '<string name=' in line and '>' in line:
                key_match = re.search(r'<string\s+name="([^"]+)"', line)
                if key_match:
                    key_name = key_match.group(1)
                    if key_name in keys_with_entities or '\u00A0' in line:
                        lines[i] = line.replace('\u00A0', '&#160;')
        f.write('\n'.join(lines))


def _insert_item(plurals_elem: ET.Element, new_item: ET.Element) -> None:
    """Insert a plural <item> before the first item that comes later in CLDR order."""
    quantity = new_item.get('quantity')
    rank = QUANTITY_ORDER.index(quantity) if quantity in QUANTITY_ORDER else len(QUANTITY_ORDER)
    children = list(plurals_elem)
    for index, child in enumerate(children):
        if child.tag != 'item':
            continue
        q = child.get('quantity')
        child_rank = QUANTITY_ORDER.index(q) if q in QUANTITY_ORDER else len(QUANTITY_ORDER)
        if child_rank > rank:
            # Take the indentation that precedes the item we insert before.
            new_item.tail = plurals_elem.text if index == 0 else children[index - 1].tail
            plurals_elem.insert(index, new_item)
            return
    if children:
        last = children[-1]
        new_item.tail = last.tail
        last.tail = children[-2].tail if len(children) > 1 else plurals_elem.text
    plurals_elem.append(new_item)


# ---------------------------------------------------------------------------
# Targeted in-place edits (placeholder fixes): change only the given values
# ---------------------------------------------------------------------------


def _attr_pattern(name: str, value: str) -> str:
    return rf'\b{name}\s*=\s*(?:"{re.escape(value)}"|\'{re.escape(value)}\')'


def _find_value_span(text: str, path: KeyPath) -> Optional[Tuple[int, int]]:
    """(start, end) of the raw inner content of the element at `path`, or None."""
    if len(path) == 1:
        m = re.search(
            rf'<string\b[^>]*?{_attr_pattern("name", path[0])}[^>]*?(?<!/)>(.*?)</string\s*>', text, re.DOTALL
        )
        return (m.start(1), m.end(1)) if m else None
    if len(path) == 2 and path[0].endswith(PLURALS_SUFFIX):
        name = path[0][: -len(PLURALS_SUFFIX)]
        p = re.search(
            rf'<plurals\b[^>]*?{_attr_pattern("name", name)}[^>]*?(?<!/)>(.*?)</plurals\s*>', text, re.DOTALL
        )
        if not p:
            return None
        body_start = p.start(1)
        m = re.search(
            rf'<item\b[^>]*?{_attr_pattern("quantity", path[1])}[^>]*?(?<!/)>(.*?)</item\s*>', p.group(1), re.DOTALL
        )
        return (body_start + m.start(1), body_start + m.end(1)) if m else None
    return None


def _decode_raw(raw: str, namespaces: Dict[str, str]) -> Optional[str]:
    """What the reader returns for an element with this raw inner content."""
    declarations = " ".join(f'xmlns:{p}="{html.escape(u, quote=True)}"' for p, u in namespaces.items())
    try:
        elem = ET.fromstring(f"<string {declarations}>{raw}</string>")
    except ET.ParseError:
        return None
    return _get_element_text(elem, {u: p for p, u in namespaces.items()})


def _minimal_raw_edit(raw: str, old: str, new: str) -> Optional[str]:
    """
    Apply the old -> new value change to the raw XML text with the smallest edit: each changed
    span is replaced at the same occurrence in the raw text. Only spans without characters that
    need escaping are handled; None otherwise.
    """
    import difflib

    special = set("&<>\\'\"\n\t")
    edits = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        # Widen to the previous character so the searched span is never empty.
        if i1 > 0:
            i1, j1 = i1 - 1, j1 - 1
        elif i2 < len(old):
            i2, j2 = i2 + 1, j2 + 1
        a, b = old[i1:i2], new[j1:j2]
        if not a or special & set(a + b):
            return None
        edits.append((_occurrence(old, a, i1), a, b))

    result = raw
    # Apply from the end so earlier occurrences keep their positions.
    for occurrence, a, b in reversed(edits):
        pos = _nth_find(result, a, occurrence)
        if pos < 0:
            return None
        result = result[:pos] + b + result[pos + len(a):]
    return result


def _occurrence(text: str, sub: str, index: int) -> int:
    """How many (possibly overlapping) occurrences of `sub` start before `index`."""
    count, pos = 0, text.find(sub)
    while 0 <= pos < index:
        count += 1
        pos = text.find(sub, pos + 1)
    return count


def _nth_find(text: str, sub: str, n: int) -> int:
    pos = text.find(sub)
    while pos >= 0 and n > 0:
        pos = text.find(sub, pos + 1)
        n -= 1
    return pos


def update_android_xml_values(file_path: str, values: Dict[KeyPath, str]) -> List[KeyPath]:
    """
    Replace only the given values in an Android XML file, keeping every other byte as it is.

    `values` maps key paths (("name",) or ("name.__plurals__", quantity)) to the new value as
    read_android_xml_file would return it. Returns the key paths that were not found.
    """
    with open(file_path, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    namespaces = _file_namespaces(file_path)

    not_found: List[KeyPath] = []
    for path, new_value in values.items():
        span = _find_value_span(text, path)
        if span is None:
            not_found.append(path)
            continue
        new_raw = _changed_raw(text[span[0]:span[1]], new_value, namespaces)
        if new_raw is not None:
            text = text[:span[0]] + new_raw + text[span[1]:]

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return not_found


def _changed_raw(raw: str, new_value: str, namespaces: Dict[str, str], markup: bool = False) -> Optional[str]:
    """
    New raw inner content for an element whose raw content is `raw`, or None if it already
    holds `new_value`. The smallest edit when it decodes right, else the value escaped as the
    writers do (a wholly quoted value stays quoted). `markup` writes tags in the value as child
    elements even if `raw` has none (the source string has markup).
    """
    old_value = _decode_raw(raw, namespaces)
    if old_value == new_value:
        return None
    if old_value is not None:
        candidate = _minimal_raw_edit(raw, old_value, new_value)
        if (
            candidate is not None
            # An unescaped leading @ / ? would make aapt2 read the value as a reference.
            and candidate.lstrip(_XML_SPACE)[:1] not in ("@", "?")
            and _decode_raw(candidate, namespaces) == new_value
        ):
            return candidate
    return _serialize_value(raw, new_value, namespaces, markup)


def _serialize_value(raw: str, value: str, namespaces: Dict[str, str], markup: bool = False) -> str:
    """Raw inner XML for `value`, as markup if the existing raw content has child elements."""
    _register_namespaces(namespaces)
    declarations = " ".join(f'xmlns:{p}="{html.escape(u, quote=True)}"' for p, u in namespaces.items())
    try:
        existing = ET.fromstring(f"<string {declarations}>{raw}</string>")
    except ET.ParseError:
        existing = None
    elem = ET.Element("string")
    _set_element_value(
        elem,
        value,
        markup or _wants_markup((), value, None, existing),
        namespaces,
        quoted=_is_wholly_quoted(existing),
    )
    serialized = ET.tostring(elem, encoding="unicode")
    # Strip the wrapper element and the namespace declarations ElementTree adds to it.
    inner = re.sub(r"^<string\b[^>]*>", "", serialized)
    inner = re.sub(r"</string>$", "", inner)
    return "" if serialized.endswith("/>") else inner


# ---------------------------------------------------------------------------
# Layout-preserving writes (translate / update)
# ---------------------------------------------------------------------------

_OPEN_RESOURCES = re.compile(r"<!--.*?-->|<resources\b(?P<attrs>[^>]*?)(?P<selfclose>/?)>", re.DOTALL)
_CLOSE_RESOURCES = re.compile(r"</resources\s*>")
# Children of <resources>. <string-array> is not a <string> (hence the lookahead).
_BODY_TOKEN = re.compile(
    r"<!--.*?-->"
    r"|<(?P<tag>string|plurals)(?=[\s/>])(?P<attrs>[^>]*?)(?:/>|>(?P<inner>.*?)</(?P=tag)\s*>)"
    r"|<(?P<otag>[A-Za-z_][\w.\-:]*)(?=[\s/>])[^>]*?(?:/>|>.*?</(?P=otag)\s*>)"
    r"|<!\[CDATA\[.*?\]\]>|<\?.*?\?>",
    re.DOTALL,
)
_ITEM_TOKEN = re.compile(
    r"<!--.*?-->|<item(?=[\s/>])(?P<attrs>[^>]*?)(?:/>|>(?P<inner>.*?)</item\s*>)", re.DOTALL
)
_TOOLS_LOCALE = re.compile(r"\s+tools:locale\s*=\s*(?:\"[^\"]*\"|'[^']*')")
_XMLNS = re.compile(r"xmlns:([A-Za-z_][\w.\-]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")


def _attr(attrs: Optional[str], name: str) -> Optional[str]:
    for a in _ATTRIBUTE.finditer(attrs or ""):
        if a.group(1) == name:
            return html.unescape(a.group(2) if a.group(2) is not None else a.group(3))
    return None


class _XmlLayout:
    """The <resources> children of an Android XML text, as layout_merge items."""

    def __init__(self, text: str):
        from algebras.utils.layout_merge import COMMENT, ENTRY, OTHER, Item

        self.text = text
        self.open = None
        for m in _OPEN_RESOURCES.finditer(text):
            if m.group("attrs") is not None:
                self.open = m
                break
        if self.open is None or self.open.group("selfclose"):
            raise ValueError("no <resources> element to merge into")
        close = None
        for close in _CLOSE_RESOURCES.finditer(text, self.open.end()):
            pass
        if close is None:
            raise ValueError("no </resources>")
        self.items = []
        self.matches = []
        for m in _BODY_TOKEN.finditer(text, self.open.end(), close.start()):
            if m.group(0).startswith("<!--"):
                item = Item(COMMENT, m.start(), m.end())
            elif m.group("tag") and _attr(m.group("attrs"), "name") is not None:
                name = _attr(m.group("attrs"), "name")
                key = name + PLURALS_SUFFIX if m.group("tag") == "plurals" else name
                item = Item(ENTRY, m.start(), m.end(), key)
            else:
                item = Item(OTHER, m.start(), m.end())
            self.items.append(item)
            self.matches.append(m)

    def declared(self) -> Dict[str, str]:
        """prefix -> uri declared on <resources>."""
        return {
            m.group(1): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in _XMLNS.finditer(self.open.group("attrs") or "")
        }

    def namespaces(self) -> Dict[str, str]:
        found = dict(_DEFAULT_NAMESPACES)
        found.update(self.declared())
        return found


def _quantity_rank(quantity: Optional[str]) -> int:
    return QUANTITY_ORDER.index(quantity) if quantity in QUANTITY_ORDER else len(QUANTITY_ORDER)


def _content_edit(
    m: "re.Match[str]", tag: str, value: str, namespaces: Dict[str, str], markup: bool
) -> Optional[Tuple[int, int, str]]:
    """Edit giving the <string> / <item> match `m` this value, or None if it already has it."""
    if m.group("inner") is None:
        # <string name="x"/>: write it out with content.
        open_tag = m.group(0)[:-2].rstrip() + ">"
        return (m.start(), m.end(), f"{open_tag}{_serialize_value('', value, namespaces, markup)}</{tag}>")
    new_raw = _changed_raw(m.group("inner"), value, namespaces, markup)
    if new_raw is None:
        return None
    return (m.start("inner"), m.end("inner"), new_raw)


def _shares_line(text: str, pos: int) -> bool:
    """True if something other than whitespace comes before `pos` on its line."""
    return bool(text[text.rfind("\n", 0, pos) + 1:pos].strip())


def _indent_of(text: str, pos: int) -> str:
    ls = text.rfind("\n", 0, pos) + 1
    before = text[ls:pos]
    return before if not before.strip() else ""


def _plurals_edits(
    m: "re.Match[str]",
    forms: Dict[str, Any],
    namespaces: Dict[str, str],
    markup_quantities: Set[str],
    nl: str,
    drop_missing: bool,
) -> List[Tuple[int, int, str]]:
    """
    Edits (positions in m.string) that give the <plurals> match `m` these forms: items already
    there get the new value if it changed, in their order; forms it lacks are added in CLDR order,
    indented like their neighbours. drop_missing leaves out items whose form is not in `forms`.
    """
    from algebras.utils import layout_merge
    from algebras.utils.layout_merge import COMMENT, ENTRY, Item

    text = m.string
    if m.group("inner") is None:
        return []
    body_start, body_end = m.span("inner")
    items: List[Item] = []
    item_matches = []
    for im in _ITEM_TOKEN.finditer(text, body_start, body_end):
        if im.group(0).startswith("<!--"):
            items.append(Item(COMMENT, im.start(), im.end()))
        else:
            items.append(Item(ENTRY, im.start(), im.end(), _attr(im.group("attrs"), "quantity")))
        item_matches.append(im)

    edits: List[Tuple[int, int, str]] = []
    kept = []
    for i, (item, im) in enumerate(zip(items, item_matches)):
        if item.kind != ENTRY:
            continue
        if item.key not in forms:
            if drop_missing:
                edits.append(layout_merge.deletion_span(text, items, i) + ("",))
            else:
                kept.append((i, item, im))
            continue
        kept.append((i, item, im))
        edit = _content_edit(im, "item", str(forms[item.key]), namespaces, item.key in markup_quantities)
        if edit:
            edits.append(edit)

    present = {item.key for item in items if item.kind == ENTRY}
    missing = sorted((q for q in forms if q not in present), key=_quantity_rank)
    if not missing:
        return edits

    default_indent = _indent_of(text, m.start()) + "    "
    groups: Dict[int, List[str]] = {}
    for q in missing:
        markup = q in markup_quantities or "other" in markup_quantities
        new_item = f'<item quantity="{q}">{_serialize_value("", str(forms[q]), namespaces, markup)}</item>'
        later = next((e for e in kept if _quantity_rank(e[1].key) > _quantity_rank(q)), None)
        if later is not None:
            # Before the first item that comes later in CLDR order.
            i, _item, im = later
            if _shares_line(text, im.start()):
                groups.setdefault(im.start(), []).append(new_item)
            else:
                pos = layout_merge.block_span(text, items, i)[0]
                groups.setdefault(pos, []).append(_indent_of(text, im.start()) + new_item + nl)
        elif kept:
            i, _item, im = kept[-1]
            if _shares_line(text, im.start()):
                groups.setdefault(im.end(), []).append(new_item)
            else:
                pos = layout_merge.block_span(text, items, i)[1]
                groups.setdefault(pos, []).append(nl + _indent_of(text, im.start()) + new_item)
        elif "\n" in text[body_start:body_end]:
            groups.setdefault(body_start, []).append(nl + default_indent + new_item)
        else:
            groups.setdefault(body_start, []).append(new_item)  # <plurals ...></plurals> on one line
    for pos, parts in groups.items():
        edits.append((pos, pos, "".join(parts)))
    return edits


def _markup_quantities(markup_paths: Set[KeyPath], key: str) -> Set[str]:
    return {p[1] for p in markup_paths if len(p) == 2 and p[0] == key}


def _render_source_element(
    source: "_XmlLayout",
    index: int,
    value: Any,
    namespaces: Dict[str, str],
    markup_paths: Set[KeyPath],
    nl: str,
) -> str:
    """Source element `index` with the translated value(s): attributes and layout as in the source."""
    from algebras.utils import layout_merge

    m = source.matches[index]
    key = source.items[index].key
    if m.group("tag") == "plurals":
        forms = value if isinstance(value, dict) else {}
        edits = _plurals_edits(m, forms, namespaces, _markup_quantities(markup_paths, key), nl, drop_missing=True)
    else:
        edit = _content_edit(m, "string", str(value), namespaces, (key,) in markup_paths)
        edits = [edit] if edit else []
    shifted = [(s - m.start(), e - m.start(), t) for s, e, t in edits]
    return layout_merge.apply_edits(m.group(0), shifted)


def _wants_value(key: str, value: Any) -> bool:
    if key.endswith(PLURALS_SUFFIX):
        return isinstance(value, dict) and bool(value)
    return value is not None and not isinstance(value, (dict, list))


def write_android_xml_preserving_layout(
    file_path: str,
    content: Dict[str, Any],
    source_file: str,
    keys_to_update: Optional[Set[str]] = None,
) -> None:
    """
    Write translations keeping the file's layout.

    Target exists: only values that changed are replaced; strings / plurals new to the target are
    added at their source position, copied from the source element (attributes such as formatted,
    translatable and tools:*, attached comments). Plural forms the file lacks are added in CLDR
    order. Keys the source no longer has stay. Comments, order, blank lines, escaping of untouched
    values, line endings and the trailing newline are kept.

    Target does not exist: the source file is the template (prolog, xmlns declarations, order,
    comments, blank lines, plural item order), each value replaced by its translation. Strings
    missing from `content` (left untranslated, translatable="false", references) and resources
    that are not strings are left out. tools:locale on <resources> names the source language, so
    it is not copied.

    Falls back to the element-tree writers if a file cannot be handled as text.

    Args:
        file_path: Target strings.xml
        content: {name: value, "name.__plurals__": {quantity: value}}
        source_file: Source-language strings.xml (template and positions of new keys)
        keys_to_update: Keys to write; None for every key in content
    """
    from algebras.utils import layout_merge

    keys_to_update = _normalize_keys_to_update(keys_to_update)
    keys = set(content) if keys_to_update is None else {k for k in keys_to_update if k in content}
    keys = {k for k in keys if _wants_value(k, content[k])}
    exists = os.path.exists(file_path)

    def fallback() -> None:
        if exists:
            write_android_xml_file_in_place(file_path, content, keys, source_file)
        else:
            write_android_xml_file(file_path, {k: content[k] for k in keys}, source_file)

    try:
        with open(source_file, 'r', encoding='utf-8', newline='') as f:
            source = _XmlLayout(f.read())
        target = None
        if exists:
            with open(file_path, 'r', encoding='utf-8', newline='') as f:
                target = _XmlLayout(f.read())
    except (OSError, ValueError):
        fallback()
        return

    markup_paths = android_markup_paths(source_file)
    source_text = source.text
    source_keys = {it.key for it in source.items if it.kind == layout_merge.ENTRY}

    if target is None:
        namespaces = source.namespaces()
        nl = layout_merge.newline_of(source_text)
        extra_edits = []
        locale = _TOOLS_LOCALE.search(source.open.group("attrs") or "")
        if locale:
            start = source.open.start("attrs") + locale.start()
            extra_edits.append((start, start + len(locale.group(0)), ""))
        output = layout_merge.build_from_template(
            source_text,
            source.items,
            keep=lambda i: source.items[i].key in keys,
            render_item=lambda i: _render_source_element(
                source, i, content[source.items[i].key], namespaces, markup_paths, nl
            ),
            extra_edits=extra_edits,
        )
        orphans = {k: content[k] for k in keys if k not in source_keys}
    else:
        target_text = target.text
        namespaces = source.namespaces()
        namespaces.update(target.namespaces())
        nl = layout_merge.newline_of(target_text, layout_merge.newline_of(source_text))

        edits = []
        present = set()
        for item, m in zip(target.items, target.matches):
            if item.kind != layout_merge.ENTRY:
                continue
            present.add(item.key)
            if item.key not in keys:
                continue
            value = content[item.key]
            if m.group("tag") == "plurals":
                if isinstance(value, dict):
                    edits.extend(
                        _plurals_edits(
                            m, value, namespaces, _markup_quantities(markup_paths, item.key), nl, drop_missing=False
                        )
                    )
            elif not isinstance(value, dict):
                edit = _content_edit(m, "string", str(value), namespaces, (item.key,) in markup_paths)
                if edit:
                    edits.append(edit)

        new_keys = keys - present
        new_indices = []
        placed = set()
        for i, item in enumerate(source.items):
            if item.kind == layout_merge.ENTRY and item.key in new_keys and item.key not in placed:
                new_indices.append(i)
                placed.add(item.key)
        orphans = {k: content[k] for k in new_keys - placed}
        if not edits and not new_indices and not orphans:
            return

        # A copied element may use a prefix (tools:) the target does not declare yet.
        inserted = "".join(source.matches[i].group(0) for i in new_indices)
        target_declared = target.declared()
        declarations = "".join(
            f' xmlns:{prefix}="{html.escape(uri, quote=True)}"'
            for prefix, uri in source.declared().items()
            if prefix not in target_declared and re.search(rf"[\s<]{re.escape(prefix)}:", inserted)
        )
        if declarations:
            pos = target.open.end("attrs")
            edits.append((pos, pos, declarations))

        output = layout_merge.merge(
            target_text,
            target.items,
            source_text,
            source.items,
            new_indices,
            render_item=lambda i: _render_source_element(
                source, i, content[source.items[i].key], namespaces, markup_paths, nl
            ),
            edits=edits,
            # An empty <resources></resources> on one line: the closing tag gets its own line.
            empty_insert=(target.open.end(), nl, "" if "\n" in target_text[target.open.end():] else nl),
        )

    try:
        ET.fromstring(output.encode("utf-8"))
    except ET.ParseError:
        fallback()
        return
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(output)
    if orphans:
        # Keys the source does not have (not expected): appended by the element-tree writer.
        write_android_xml_file_in_place(file_path, orphans, set(orphans), source_file)
