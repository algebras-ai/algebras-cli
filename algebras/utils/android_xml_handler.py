"""
Android XML localization file handler

Values are read as the element's full inner content. Text runs are unescaped (XML entities and
Android backslash escapes), and child elements are kept as markup with their namespace prefix:

    <string name="x">Hello <xliff:g id="n">%1$s</xliff:g>, it\\'s <b>here</b></string>
    -> 'Hello <xliff:g id="n">%1$s</xliff:g>, it\\'s <b>here</b>'   (with \\' decoded to ')

When writing, a value is written back as mixed content (child elements) if the string has markup
in the source or in the existing target element; otherwise it is plain text. Escaping applies to
text runs only, so restored markup is never written as &lt;xliff:g&gt;.
"""

import html
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Import Config to check normalization settings
from algebras.config import Config

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

        text = _get_element_text(string_elem, prefixes)
        if text is not None and not is_resource_reference(text):
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
    normalize = _normalize_strings_enabled()

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
                        item_elem, text, _wants_markup((key, quantity), text, markup_paths, None), namespaces, normalize
                    )
        else:
            string_elem = ET.SubElement(root, 'string')
            string_elem.set('name', key)
            _copy_source_attributes(string_elem, (key,), source_attributes)
            text = str(value)
            _set_element_value(string_elem, text, _wants_markup((key,), text, markup_paths, None), namespaces, normalize)

    _indent_resources(root)
    tree = ET.ElementTree(root)
    with open(file_path, 'wb') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'.encode('utf-8'))
        tree.write(f, encoding='utf-8', xml_declaration=False)
        f.write(b'\n')


# ---------------------------------------------------------------------------
# Reading element content
# ---------------------------------------------------------------------------


def _decode_text(text: str) -> str:
    """Unescape one text run: XML entities and Android backslash escapes."""
    text = html.unescape(text)
    text = text.replace("\\'", "'")
    text = text.replace('\\"', '"')
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    return text


def _qualified(name: str, prefixes: Dict[str, str]) -> str:
    """'{uri}local' -> 'prefix:local'."""
    if name.startswith("{"):
        uri, local = name[1:].split("}", 1)
        prefix = prefixes.get(uri)
        return f"{prefix}:{local}" if prefix else local
    return name


def _serialize_child(elem: ET.Element, prefixes: Dict[str, str]) -> str:
    if not isinstance(elem.tag, str):
        return ""  # comment / processing instruction inside a string
    tag = _qualified(elem.tag, prefixes)
    attrs = "".join(
        f' {_qualified(k, prefixes)}="{html.escape(v, quote=True)}"' for k, v in elem.attrib.items()
    )
    inner = _inner_content(elem, prefixes)
    if not inner and len(elem) == 0:
        return f"<{tag}{attrs}/>"
    return f"<{tag}{attrs}>{inner}</{tag}>"


def _inner_content(elem: ET.Element, prefixes: Dict[str, str]) -> str:
    parts = []
    if elem.text:
        parts.append(_decode_text(elem.text))
    for child in elem:
        parts.append(_serialize_child(child, prefixes))
        if child.tail:
            parts.append(_decode_text(child.tail))
    return "".join(parts)


def _get_element_text(element: ET.Element, prefixes: Optional[Dict[str, str]] = None) -> str:
    """
    Extract the full inner content of a <string> or <item>.

    Text runs are unescaped; child elements (<xliff:g>, <b>, <a href> ...) are kept as markup,
    including their own text, with their namespace prefix.

    Args:
        element: The XML element
        prefixes: namespace uri -> prefix

    Returns:
        The content as a string
    """
    if prefixes is None:
        prefixes = {uri: prefix for prefix, uri in _DEFAULT_NAMESPACES.items()}
    return _inner_content(element, prefixes).strip()


# ---------------------------------------------------------------------------
# Writing element content
# ---------------------------------------------------------------------------


def _normalize_strings_enabled() -> bool:
    try:
        config = Config()
        if config.exists():
            config.load()
            return config.get_setting("api.normalize_strings", True)
        return True  # Default to True if no config
    except Exception:
        return True  # Default to True if config fails to load


def _escape_android_text(text: str, normalize_strings: Optional[bool] = None) -> str:
    """Android backslash escapes for one text run (XML escaping is left to the serializer)."""
    if normalize_strings is None:
        normalize_strings = _normalize_strings_enabled()
    # Only escape quotes if normalization is disabled
    if not normalize_strings:
        text = text.replace("'", "\\'")
        text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\t', '\\t')
    return text


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


def _build_mixed_content(elem: ET.Element, value: str, namespaces: Dict[str, str], normalize: bool) -> bool:
    """Fill `elem` with text and child elements parsed from `value`. False if the markup is not well-formed."""
    stack: List[Tuple[ET.Element, str]] = [(elem, "")]

    def add_text(text: str) -> None:
        if not text:
            return
        text = _escape_android_text(text, normalize)
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
    elem: ET.Element, value: str, markup: bool, namespaces: Dict[str, str], normalize: bool
) -> None:
    for child in list(elem):
        elem.remove(child)
    elem.text = None
    if markup and _TAG_TOKEN.search(value):
        if _build_mixed_content(elem, value, namespaces, normalize):
            return
        for child in list(elem):
            elem.remove(child)
        elem.text = None
    elem.text = _escape_android_text(value, normalize)


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
    normalize = _normalize_strings_enabled()
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
                normalize,
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
                        normalize,
                    )
            # Add the forms the target language needs but the file lacks, in CLDR order.
            for quantity in _sort_quantities(q for q in plural_dict if q not in present):
                new_item = ET.Element('item', {'quantity': quantity})
                text = str(plural_dict[quantity])
                _set_element_value(
                    new_item, text, _wants_markup((plural_key, quantity), text, markup_paths, None), namespaces, normalize
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
                        item_elem, text, _wants_markup((key, quantity), text, markup_paths, None), namespaces, normalize
                    )
        elif not isinstance(content[key], dict):
            string_elem = ET.SubElement(root, 'string')
            string_elem.set('name', key)
            _copy_source_attributes(string_elem, (key,), source_attributes)
            text = str(content[key])
            _set_element_value(string_elem, text, _wants_markup((key,), text, markup_paths, None), namespaces, normalize)

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
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    namespaces = _file_namespaces(file_path)
    normalize = _normalize_strings_enabled()

    not_found: List[KeyPath] = []
    for path, new_value in values.items():
        span = _find_value_span(text, path)
        if span is None:
            not_found.append(path)
            continue
        raw = text[span[0]:span[1]]
        old_value = _decode_raw(raw, namespaces)
        new_raw = None
        if old_value is not None and old_value != new_value:
            candidate = _minimal_raw_edit(raw, old_value, new_value)
            if candidate is not None and _decode_raw(candidate, namespaces) == new_value:
                new_raw = candidate
        elif old_value == new_value:
            continue
        if new_raw is None:
            # Keep the file's quote escaping style (\' / \") for this value.
            keep_style = normalize and "\\'" not in raw and '\\"' not in raw
            new_raw = _serialize_value(raw, new_value, namespaces, keep_style)
        text = text[:span[0]] + new_raw + text[span[1]:]

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return not_found


def _serialize_value(raw: str, value: str, namespaces: Dict[str, str], normalize: bool) -> str:
    """Raw inner XML for `value`, as markup if the existing raw content has child elements."""
    _register_namespaces(namespaces)
    declarations = " ".join(f'xmlns:{p}="{html.escape(u, quote=True)}"' for p, u in namespaces.items())
    try:
        existing = ET.fromstring(f"<string {declarations}>{raw}</string>")
    except ET.ParseError:
        existing = None
    elem = ET.Element("string")
    _set_element_value(elem, value, _wants_markup((), value, None, existing), namespaces, normalize)
    serialized = ET.tostring(elem, encoding="unicode")
    # Strip the wrapper element and the namespace declarations ElementTree adds to it.
    inner = re.sub(r"^<string\b[^>]*>", "", serialized)
    inner = re.sub(r"</string>$", "", inner)
    return "" if serialized.endswith("/>") else inner
