"""
XLIFF (XML Localization Interchange File Format) file handler

Reading: read_xliff_file parses a file into a dictionary (one entry per translatable text, see
_parse_xliff_root) and keeps the file text on the result (XliffContent.text).

Writing: write_xliff_file never rebuilds a file it has the text of. With the text of the target
(an existing target) only the <target> of the units whose translation changed is rewritten, plus
units the source gained, copied from the source file; everything else stays byte for byte. With
the text of the source only (a new target), the source file is the template: notes, context,
groups and unit attributes are kept, target-language / trgLang is set and every translated unit
gets its <target>. A dictionary without file text (built in code) is written from scratch.
"""

import bisect
import codecs
import copy
import html
import os
import re
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from xml.dom import minidom

logger = logging.getLogger(__name__)


class XliffContent(dict):
    """
    A parsed XLIFF file (see _parse_xliff_root) plus the text it was read from.

    text / encoding: the file this content was read from (None when built in code).
    template_text / template_encoding: the source file, set by update_xliff_targets; the template
    of a new target and of the units an existing target lacks.
    """

    text: Optional[str] = None
    encoding: str = "utf-8"
    template_text: Optional[str] = None
    template_encoding: str = "utf-8"


def _read_text(file_path: str) -> Tuple[Optional[str], str]:
    """(text, encoding) of a file; text is None if it cannot be decoded."""
    with open(file_path, "rb") as f:
        raw = f.read()
    try:
        if raw.startswith(codecs.BOM_UTF8):
            return raw[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8-sig"
        if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            return raw.decode("utf-16"), "utf-16"
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return None, "utf-8"


def read_xliff_file(file_path: str) -> Dict[str, Any]:
    """
    Read an XLIFF file and return its content as a dictionary.

    Args:
        file_path: Path to the XLIFF file

    Returns:
        Dictionary containing the XLIFF file content (an XliffContent holding the file text)

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is not valid XLIFF format
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"XLIFF file not found: {file_path}")

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in XLIFF file {file_path}: {str(e)}")

    # Check if it's a valid XLIFF file
    if root.tag != 'xliff' and not root.tag.endswith('}xliff'):
        raise ValueError(f"File {file_path} is not a valid XLIFF file")

    content = XliffContent(_parse_xliff_root(root))
    content.text, content.encoding = _read_text(file_path)
    return content


def write_xliff_file(file_path: str, content: Dict[str, Any],
                    source_language: str = "en", target_language: str = "en",
                    target_state: Optional[str] = None) -> None:
    """
    Write content to an XLIFF file.

    When `content` carries the text of the file it was read from (an existing target) or of the
    source file (a new target, see update_xliff_targets), that text is edited in place: see the
    module docstring. Otherwise the file is built from the dictionary alone.

    Args:
        file_path: Path where to write the XLIFF file
        content: Dictionary containing the XLIFF content
        source_language: Source language code
        target_language: Target language code
        target_state: Optional state attribute to add to target elements (e.g., "translated", "needs-review-translation")

    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("XLIFF content must be a dictionary")

    # Ensure the directory exists
    if os.path.dirname(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    base_text = getattr(content, "text", None)
    template_text = getattr(content, "template_text", None)
    if base_text is not None or template_text is not None:
        existing = base_text is not None
        try:
            text = render_xliff(
                content,
                base_text if existing else template_text,
                template_text,
                existing,
                target_language,
            )
        except (ET.ParseError, ValueError) as e:
            logger.warning(f"Could not edit {file_path} in place ({e}); writing it from its content")
        else:
            encoding = content.encoding if existing else content.template_encoding
            with open(file_path, "w", encoding=encoding, newline="") as f:
                f.write(text)
            return

    _write_xliff_from_dict(file_path, content, source_language, target_language, target_state)


def _write_xliff_from_dict(file_path: str, content: Dict[str, Any],
                           source_language: str, target_language: str,
                           target_state: Optional[str]) -> None:
    """Build an XLIFF file from a dictionary alone (no file text to keep)."""
    # Determine XLIFF version from content or default to 1.2
    version = content.get('version', '1.2')
    if version == '2.0':
        namespace = 'urn:oasis:names:tc:xliff:document:2.0'
        xmlns_attr = namespace
    else:
        namespace = 'urn:oasis:names:tc:xliff:document:1.2'
        xmlns_attr = namespace
        version = '1.2'

    logger.debug(f"Writing XLIFF file with version {version}, target_state={target_state}")

    # Inner XML of <source>/<target> elements, keyed by a marker set as their text while the
    # document is pretty-printed (pretty-printing must not add whitespace inside mixed content).
    inline_xml: Dict[str, str] = {}

    # Create XLIFF structure
    xliff_root = ET.Element('xliff')
    xliff_root.set('version', version)
    xliff_root.set('xmlns', xmlns_attr)

    # Get source language from content if available
    if 'files' in content and content['files'] and content['files'][0].get('source-language'):
        source_language = content['files'][0]['source-language']

    # For XLIFF 2.0, set srcLang/trgLang on root element
    if version == '2.0':
        xliff_root.set('srcLang', source_language)
        files = content.get('files') or [{}]
        trg_lang = files[0].get('target-language') or target_language
        if trg_lang:
            xliff_root.set('trgLang', trg_lang)

    file_elem = ET.SubElement(xliff_root, 'file')

    # Preserve original file attributes from content if available
    if 'files' in content and content['files']:
        file_data = content['files'][0]
        file_elem.set('original', file_data.get('original', 'messages'))
        file_elem.set('source-language', file_data.get('source-language', source_language))
        # An empty target-language (as in most source files) becomes the target language.
        file_elem.set('target-language', file_data.get('target-language') or target_language)
        if file_data.get('datatype'):
            file_elem.set('datatype', file_data['datatype'])
        if version == '2.0' and file_data.get('id'):
            file_elem.set('id', file_data['id'])
    else:
        file_elem.set('original', 'messages')
        file_elem.set('source-language', source_language)
        file_elem.set('target-language', target_language)
        file_elem.set('datatype', 'plaintext')

    if version == '2.0':
        # XLIFF 2.0: units go directly under file, not in body
        container = file_elem
    else:
        # XLIFF 1.2: units go in body
        body_elem = ET.SubElement(file_elem, 'body')
        container = body_elem

    # Handle different content structures
    # Check for structured format: must have 'files' key and it must be a list (even if empty)
    # Empty list is valid - it means no units yet, but we still use structured format
    if 'files' in content and isinstance(content['files'], list):
        # Use the first file's data
        file_data = content['files'][0] if content['files'] else {}
        if 'trans-units' in file_data:
            for unit in file_data['trans-units']:
                if 'id' in unit and 'source' in unit:
                    if version == '2.0':
                        # XLIFF 2.0: use <unit> with <segment>
                        unit_elem = ET.SubElement(container, 'unit')
                        unit_elem.set('id', unit['id'])
                        segment = ET.SubElement(unit_elem, 'segment')
                        source_elem = ET.SubElement(segment, 'source')
                        _set_inline(source_elem, unit['source'], inline_xml)
                        target_elem = ET.SubElement(segment, 'target')
                        target_ok = _set_inline(target_elem, unit.get('target', unit['source']), inline_xml, is_target=True)
                        # For XLIFF 2.0, state goes on segment, not target
                        # Only add state if unit explicitly has one and it's not empty
                        unit_state = unit.get('state')
                        if target_ok and unit_state and unit_state.strip():
                            segment.set('state', unit_state)
                    else:
                        # XLIFF 1.2: use <trans-unit>
                        trans_unit = ET.SubElement(container, 'trans-unit')
                        trans_unit.set('id', unit['id'])
                        source_elem = ET.SubElement(trans_unit, 'source')
                        _set_inline(source_elem, unit['source'], inline_xml)
                        target_elem = ET.SubElement(trans_unit, 'target')
                        target_ok = _set_inline(target_elem, unit.get('target', unit['source']), inline_xml, is_target=True)
                        # For XLIFF 1.2, state goes on target
                        # Only add state if unit explicitly has one and it's not empty
                        unit_state = unit.get('state')
                        if target_ok and unit_state and unit_state.strip():
                            target_elem.set('state', unit_state)
    else:
        # Handle flat dictionary structure (always write as XLIFF 1.2)
        # Skip metadata keys like 'version' that shouldn't be translation units
        metadata_keys = {'version'}
        for key, value in content.items():
            if key in metadata_keys:
                continue  # Skip metadata keys
            if isinstance(value, str):
                trans_unit = ET.SubElement(container, 'trans-unit')
                trans_unit.set('id', key)
                source_elem = ET.SubElement(trans_unit, 'source')
                _set_inline(source_elem, value, inline_xml)
                target_elem = ET.SubElement(trans_unit, 'target')
                target_ok = _set_inline(target_elem, value, inline_xml, is_target=True)
                # Add state if target_state is provided (for flat dict structure from new file creation)
                if target_ok and target_state:
                    target_elem.set('state', target_state)

    # Write to file with proper formatting
    rough_string = ET.tostring(xliff_root, encoding='unicode', xml_declaration=True)
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    if inline_xml:
        pretty_text = pretty_xml.decode('utf-8')
        for marker, xml in inline_xml.items():
            pretty_text = pretty_text.replace(marker, xml, 1)
        pretty_xml = pretty_text.encode('utf-8')

    with open(file_path, 'wb') as f:
        f.write(pretty_xml)


def _set_inline(element: ET.Element, value: Optional[str], inline_xml: Dict[str, str], is_target: bool = False) -> bool:
    """
    Set a <source>/<target> from a flat string, turning inline markup back into elements.
    Returns False if a target was left empty because its inline markup is malformed.
    """
    if not value:
        element.text = value
        return True
    try:
        xml = flat_to_file_xml(value)
    except ValueError as e:
        if is_target:
            # Never write broken inline markup into a target: leave it empty (untranslated).
            logger.warning(f"Not writing target with malformed inline elements: {decode_flat(str(e))}")
            element.text = ''
            return False
        xml = _escape_text(value)
    marker = f"{len(inline_xml)}"
    inline_xml[marker] = xml
    element.text = marker
    return True


def extract_translatable_strings(xliff_content: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract translatable strings from XLIFF content.

    Units with translate="no" are left out: they are never translated.

    Args:
        xliff_content: XLIFF file content as dictionary

    Returns:
        Dictionary of key-value pairs for translatable strings
    """
    translatable = {}

    # Look for translation units in the content
    if 'files' in xliff_content:
        for file_data in xliff_content['files']:
            if 'trans-units' in file_data:
                for unit in file_data['trans-units']:
                    if 'id' in unit and 'source' in unit and unit.get('translate') is not False:
                        translatable[unit['id']] = unit['source']
    else:
        # If it's a flat dictionary, use it directly
        for key, value in xliff_content.items():
            if isinstance(value, str):
                translatable[key] = value

    return translatable


def create_xliff_from_translations(translations: Dict[str, str],
                                  source_language: str = "en",
                                  target_language: str = "en") -> Dict[str, Any]:
    """
    Create XLIFF content from translations.

    Args:
        translations: Dictionary of key-value translation pairs
        source_language: Source language code
        target_language: Target language code

    Returns:
        XLIFF content dictionary
    """
    trans_units = []
    for key, value in translations.items():
        trans_units.append({
            'id': key,
            'source': value,
            'target': value
        })

    return {
        'files': [{
            'original': 'messages',
            'source-language': source_language,
            'target-language': target_language,
            'trans-units': trans_units
        }]
    }


def _translation_problem(source: str, translation: str) -> Optional[str]:
    """Why `translation` must not be written as the target of `source` (None = OK), for display."""
    from algebras.services.placeholders.formats.xliff import translation_problem

    problem = translation_problem(source, translation)
    return decode_flat(problem) if problem else None


_UNIT_META = ('unit_id', 'segment', 'segments', 'translate')


def update_xliff_targets(xliff_content: Dict[str, Any], translations: Dict[str, str],
                         source_content: Optional[Dict[str, Any]] = None,
                         target_state: Optional[str] = None,
                         only_missing: bool = False) -> Dict[str, Any]:
    """
    Update XLIFF target elements with translated strings while preserving source text.
    Also adds new units from source that don't exist in target.

    Units with translate="no" are never changed. The result keeps the file text of
    `xliff_content` and the source file text of `source_content` (XliffContent), so
    write_xliff_file can edit the file instead of rebuilding it.

    Args:
        xliff_content: Original XLIFF content structure (target file)
        translations: Dictionary of translated strings (key -> translated_value)
        source_content: Optional source XLIFF content to add missing units from
        target_state: Optional state attribute to add to target elements (e.g., "translated", "needs-review-translation")

    Returns:
        Updated XLIFF content with target elements updated and new units added
    """
    updated_content = XliffContent(copy.deepcopy(dict(xliff_content)))
    updated_content.text = getattr(xliff_content, 'text', None)
    updated_content.encoding = getattr(xliff_content, 'encoding', 'utf-8')
    if source_content is not None:
        updated_content.template_text = getattr(source_content, 'text', None)
        updated_content.template_encoding = getattr(source_content, 'encoding', 'utf-8')

    # Ensure version is preserved in updated content
    if 'version' not in updated_content:
        if source_content and 'version' in source_content:
            updated_content['version'] = source_content['version']

    logger.debug(
        f"Processing XLIFF with version {updated_content.get('version', 'unknown')}, "
        f"target_state={target_state}, only_missing={only_missing}"
    )

    # Track which unit IDs already exist in target
    existing_unit_ids = set()
    source_by_id = extract_translatable_strings(source_content) if source_content else {}

    # Ensure 'files' structure exists
    if 'files' not in updated_content:
        updated_content['files'] = []

    # If files list is empty, create a file entry from source_content if available
    if not updated_content['files'] and source_content and 'files' in source_content and source_content['files']:
        source_file_data = source_content['files'][0]
        updated_content['files'].append({
            'original': source_file_data.get('original', 'messages'),
            'source-language': source_file_data.get('source-language', 'en'),
            'target-language': source_file_data.get('target-language', 'en'),
            'trans-units': []
        })

    for file_data in updated_content['files']:
        for unit in file_data.get('trans-units', []):
            unit_id = unit.get('id')
            if not unit_id:
                continue
            existing_unit_ids.add(unit_id)
            if unit.get('translate') is False:
                continue  # translate="no": never changed
            existing_target = unit.get('target', '').strip()
            existing_state = unit.get('state')

            if unit_id in translations:
                # Update target with translation
                # If only_missing is True, only update if target is empty
                if only_missing and existing_target:
                    # Preserve existing target when in only-missing mode
                    pass
                else:
                    # Update target (either not only-missing mode, or target is empty),
                    # unless the translation damaged inline elements or placeholders:
                    # then the previous target (and state) stays.
                    new_value = translations[unit_id]
                    problem = None
                    if new_value != unit.get('target'):
                        problem = _translation_problem(
                            source_by_id.get(unit_id, unit.get('source', '')), new_value
                        )
                    if problem:
                        logger.warning(f"Not writing translation of unit {unit_id}: {problem}")
                        print(f"  ⚠ Kept the previous target of '{unit_id}': {problem}")
                    else:
                        unit['target'] = new_value

                # For existing units, preserve existing state if present
                # DO NOT add new state to existing units
                if existing_state:
                    unit['state'] = existing_state
            elif 'source' in unit and not existing_target:
                # No translation and no target: leave it empty (missing), never copy the source
                unit['target'] = ''

    # Add new units from source that don't exist in target
    if source_content and 'files' in source_content:
        target_file_data = updated_content['files'][0] if updated_content['files'] else None
        if target_file_data is not None and 'trans-units' not in target_file_data:
            target_file_data['trans-units'] = []
        for source_file_data in source_content['files']:
            if target_file_data is None:
                break
            for source_unit in source_file_data.get('trans-units', []):
                source_unit_id = source_unit.get('id')
                if not source_unit_id or source_unit_id in existing_unit_ids:
                    continue
                new_unit = {
                    'id': source_unit_id,
                    'source': source_unit.get('source', ''),
                }
                for meta in _UNIT_META:
                    if meta in source_unit:
                        new_unit[meta] = source_unit[meta]
                if source_unit.get('translate') is False:
                    # Copied as it is in the source.
                    new_unit['target'] = source_unit.get('target', '')
                    target_file_data['trans-units'].append(new_unit)
                    continue
                target_value = translations.get(source_unit_id, '')
                problem = _translation_problem(source_unit.get('source', ''), target_value) if target_value else None
                if problem:
                    logger.warning(f"Not writing translation of unit {source_unit_id}: {problem}")
                    print(f"  ⚠ Left '{source_unit_id}' untranslated: {problem}")
                    target_value = ''
                if not target_value:
                    logger.warning(f"No translation provided for new unit {source_unit_id}, leaving it untranslated")
                new_unit['target'] = target_value
                # Add state attribute if provided (an untranslated unit gets none)
                if target_state and target_value:
                    new_unit['state'] = target_state
                target_file_data['trans-units'].append(new_unit)

    return updated_content


# ---------------------------------------------------------------------------
# Inline content: <source>/<target> with inline elements <-> flat string
# ---------------------------------------------------------------------------
#
# A <source> or <target> is read into one flat string: text runs as plain text (unescaped) and
# inline elements as XML markup without namespace prefixes, e.g.
#
#     Hello <x id="INTERPOLATION" equiv-text="{{ name }}"/>, <g id="1">welcome</g>!
#
# (inside attribute values the braces are stored as private-use characters; see _FLAT_ATTR_CHARS). The
# placeholder profile in algebras/services/placeholders/formats/xliff.py masks each inline element
# (or each open/close tag of a paired element) as one opaque token, so the model never sees its
# attributes. The writer turns the markup back into elements (build_inline_content), so <target>
# never contains escaped "&lt;x .../&gt;".

# Standalone inline elements (XLIFF 1.2 and 2.x).
INLINE_STANDALONE = ("x", "bx", "ex", "ph", "bpt", "ept", "it", "sc", "ec", "sm", "em", "cp", "g", "pc", "mrk")
# Elements whose content is native code (XLIFF 1.2), never translatable: masked whole.
INLINE_NATIVE_CODE = ("ph", "bpt", "ept", "it", "sub")
# Elements whose content is translatable text: open and close tags are masked separately.
INLINE_PAIRED = ("g", "pc", "mrk")

_NAME_END = r"(?=[\s/>])"
# A whole element whose content is not translatable: 1.2 native code, or protected markers.
INLINE_ATOMIC_PATTERN = (
    r"<(?P<native>ph|bpt|ept|it)" + _NAME_END + r"[^<>]*(?<!/)>.*?</(?P=native)\s*>"
    r"|<mrk" + _NAME_END + r"[^<>]*\b(?:mtype=\"protected\"|translate=\"no\")[^<>]*(?<!/)>.*?</mrk\s*>"
    r"|<(?:" + "|".join(INLINE_STANDALONE) + r")" + _NAME_END + r"[^<>]*/>"
)
INLINE_OPEN_PATTERN = r"<(?:" + "|".join(INLINE_PAIRED) + r")" + _NAME_END + r"[^<>]*(?<!/)>"
INLINE_CLOSE_PATTERN = r"</(?:" + "|".join(INLINE_PAIRED) + r")\s*>"

_INLINE_TOKEN_RE = re.compile(
    r"(?P<atomic>" + INLINE_ATOMIC_PATTERN + r")"
    r"|(?P<open>" + INLINE_OPEN_PATTERN + r")"
    r"|(?P<close>" + INLINE_CLOSE_PATTERN + r")",
    re.DOTALL,
)

# Characters that mean something to ICU MessageFormat ("{", "}" and "#" in plural branches) are
# replaced inside attribute values and native code in the flat string, so an Angular
# equiv-text="{{ count }}" is never parsed as ICU syntax. Private-use characters are used because
# every XML character reference contains "#". The writer maps them back.
_FLAT_ATTR_CHARS = {"{": "\ue07b", "}": "\ue07d", "#": "\ue023"}
# Whitespace in attribute values would otherwise be normalized to spaces when the markup is parsed.
_FLAT_ATTR_WHITESPACE = {"\n": "\ue00a", "\t": "\ue009", "\r": "\ue00d"}
_FLAT_ATTR_DECODE = {v: k for k, v in {**_FLAT_ATTR_CHARS, **_FLAT_ATTR_WHITESPACE}.items()}
_XML_NS = "http://www.w3.org/XML/1998/namespace"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else str(tag)


def _attr_name(name: str) -> str:
    if name.startswith("{" + _XML_NS + "}"):
        return "xml:" + name.split("}", 1)[1]
    return _local_name(name)


def _escape_text(text: str, flat_native: bool = False) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if flat_native:
        text = text.replace("'", "&apos;")
        for ch, sub in _FLAT_ATTR_CHARS.items():
            text = text.replace(ch, sub)
    return text


def _escape_attr(value: str, flat: bool) -> str:
    value = _escape_text(value, flat_native=flat).replace('"', "&quot;")
    if flat:
        for ch, sub in _FLAT_ATTR_WHITESPACE.items():
            value = value.replace(ch, sub)
        return value
    return value.replace("\n", "&#10;").replace("\t", "&#9;").replace("\r", "&#13;")


def decode_flat(value: str) -> str:
    """Undo the private-use substitution of the flat form (for display and attribute values)."""
    for sub, ch in _FLAT_ATTR_DECODE.items():
        value = value.replace(sub, ch)
    return value


def _open_tag(element: ET.Element, flat: bool, self_closing: bool = False) -> str:
    attrs = "".join(f' {_attr_name(k)}="{_escape_attr(v, flat)}"' for k, v in element.attrib.items())
    return f"<{_local_name(element.tag)}{attrs}{'/' if self_closing else ''}>"


def serialize_inline(element: ET.Element, flat: bool = True, native: bool = False) -> str:
    """
    One inline element (without its tail) as markup.

    flat=True gives the form used in the flat string: text inside paired elements stays plain
    (it is translatable), attributes and native code are escaped and ICU-neutral.
    flat=False gives normal XML for the file.
    """
    name = _local_name(element.tag)
    native = native or name in INLINE_NATIVE_CODE or (
        name == "mrk" and (element.get("mtype") == "protected" or element.get("translate") == "no")
    )
    if element.text is None and len(element) == 0 and name not in INLINE_PAIRED:
        return _open_tag(element, flat, self_closing=True)
    parts = [_open_tag(element, flat)]
    parts.append(_serialize_runs(element, flat, native))
    parts.append(f"</{name}>")
    return "".join(parts)


def _serialize_runs(element: ET.Element, flat: bool, native: bool) -> str:
    """Text and children of `element` (not the element itself)."""

    def text(value: Optional[str]) -> str:
        if not value:
            return ""
        if flat and not native:
            return value  # translatable text: plain
        return _escape_text(value, flat_native=flat and native)

    parts = [text(element.text)]
    for child in element:
        parts.append(serialize_inline(child, flat, native))
        parts.append(text(child.tail))
    return "".join(parts)


def _decode_element(element: ET.Element) -> ET.Element:
    for el in element.iter():
        for k, v in list(el.attrib.items()):
            el.set(k, decode_flat(v))
        if el.text:
            el.text = decode_flat(el.text)
        if el.tail and el is not element:
            el.tail = decode_flat(el.tail)
    return element


def _parse_markup(markup: str) -> ET.Element:
    # The flat form may use the xml: prefix on attributes; it is predeclared in XML.
    return _decode_element(ET.fromstring(markup))


def build_inline_content(value: str) -> ET.Element:
    """
    Parse a flat string into a container element whose text/children are the inline content.

    Raises ValueError if the inline markup is malformed or not properly nested.
    """
    root = ET.Element("content")
    stack = [root]

    def add_text(text: str) -> None:
        if not text:
            return
        parent = stack[-1]
        if len(parent):
            parent[-1].tail = (parent[-1].tail or "") + text
        else:
            parent.text = (parent.text or "") + text

    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(value or ""):
        add_text(value[pos : m.start()])
        pos = m.end()
        markup = m.group(0)
        try:
            if m.group("atomic"):
                stack[-1].append(_parse_markup(markup))
            elif m.group("open"):
                name = re.match(r"<([A-Za-z]+)", markup).group(1)
                element = _parse_markup(markup + f"</{name}>")
                stack[-1].append(element)
                stack.append(element)
            else:
                name = re.match(r"</([A-Za-z]+)", markup).group(1)
                if len(stack) == 1 or _local_name(stack[-1].tag) != name:
                    raise ValueError(f"Unexpected closing tag {markup}")
                stack.pop()
        except ET.ParseError as e:
            raise ValueError(f"Malformed inline element {markup}: {e}")
    add_text((value or "")[pos:])
    if len(stack) != 1:
        raise ValueError(f"Unclosed inline element <{_local_name(stack[-1].tag)}>")
    return root


def flat_to_file_xml(value: str) -> str:
    """Flat string -> inner XML of <source>/<target> (text escaped, inline elements as elements)."""
    return _serialize_runs(build_inline_content(value), flat=False, native=False)


def _extract_full_text_from_element(element: ET.Element) -> str:
    """
    Read a <source>/<target> element into one flat string: plain text plus inline elements
    (<x/>, <ph/>, <g>…</g>, <pc>…</pc>, <sc/>, <ec/>, <mrk>…</mrk> …) as markup.

    Args:
        element: XML element to extract text from

    Returns:
        Full text content including child element representations
    """
    if element is None:
        return ''
    return _serialize_runs(element, flat=True, native=False).strip()



def _parse_xliff_root(root: ET.Element) -> Dict[str, Any]:
    """
    Parse an XLIFF root element into a dictionary (XLIFF 1.2 and 2.x).

    Every translatable text is one entry of a file's 'trans-units' list, keyed by 'id':
    - 1.2: one entry per <trans-unit>, id = the unit id;
    - 2.x: one entry per <segment> of a <unit>. A unit with one segment keeps the unit id as its
      key; a unit with several gives "<unit id>#1", "<unit id>#2", ... (segment_key), and its
      entries also hold 'unit_id', 'segment' (0-based) and 'segments'. <ignorable> content is
      not translatable and is not read.
    Entries of a unit with translate="no" (on the unit or an enclosing group/file) have
    'translate': False: they are never sent for translation and never changed.
    """
    version = root.get('version', '1.2')
    is2 = _is_v2(version)
    result = {
        'version': version,
        'files': []
    }

    # Source language from root (XLIFF 2.x) or from the file element (XLIFF 1.2)
    source_lang = root.get('srcLang') or root.get('source-language', '')
    target_lang = root.get('trgLang', '')

    for file_elem in (e for e in root.iter() if _local_name(e.tag) == 'file'):
        file_data = {
            'original': file_elem.get('original', ''),
            'source-language': file_elem.get('source-language') or source_lang,
            'target-language': file_elem.get('target-language') or target_lang,
            'datatype': file_elem.get('datatype', 'plaintext'),
            'trans-units': []
        }
        file_translatable = file_elem.get('translate') != 'no'
        for unit, translatable in _iter_units(file_elem, file_translatable):
            entries = _parse_unit_v2(unit) if is2 else [_parse_unit_v12(unit)]
            for entry in entries:
                if not translatable:
                    entry['translate'] = False
                file_data['trans-units'].append(entry)
        result['files'].append(file_data)

    return result


def _is_v2(version: Any) -> bool:
    return str(version or '').startswith('2')


def segment_key(unit_id: str, index: int, count: int) -> str:
    """Key of segment `index` (0-based) of a 2.x unit with `count` segments."""
    return unit_id if count <= 1 else f"{unit_id}#{index + 1}"


def _children(element: ET.Element, name: str) -> List[ET.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _child(element: ET.Element, name: str) -> Optional[ET.Element]:
    found = _children(element, name)
    return found[0] if found else None


def _iter_units(container: ET.Element, translatable: bool):
    """(unit element, translatable) in document order; translate="no" is inherited from groups."""
    for child in container:
        name = _local_name(child.tag)
        flag = child.get('translate')
        child_translatable = translatable if flag is None else flag != 'no'
        if name in ('trans-unit', 'unit'):
            yield child, child_translatable
        elif name in ('body', 'group'):
            yield from _iter_units(child, child_translatable)


def _parse_unit_v12(unit: ET.Element) -> Dict[str, Any]:
    unit_data = {'id': unit.get('id', ''), 'source': '', 'target': ''}
    source_elem = _child(unit, 'source')
    if source_elem is not None:
        unit_data['source'] = _extract_full_text_from_element(source_elem)
    target_elem = _child(unit, 'target')
    if target_elem is not None:
        unit_data['target'] = _extract_full_text_from_element(target_elem)
        if target_elem.get('state'):
            unit_data['state'] = target_elem.get('state')
    return unit_data


def _parse_unit_v2(unit: ET.Element) -> List[Dict[str, Any]]:
    unit_id = unit.get('id', '')
    segments = _children(unit, 'segment')
    if not segments:
        # Not valid 2.x, but accepted: <source>/<target> directly in the unit.
        return [_parse_unit_v12(unit)]
    entries = []
    for index, segment in enumerate(segments):
        entry = {'id': segment_key(unit_id, index, len(segments)), 'source': '', 'target': ''}
        if len(segments) > 1:
            entry.update({'unit_id': unit_id, 'segment': index, 'segments': len(segments)})
        source_elem = _child(segment, 'source')
        if source_elem is not None:
            entry['source'] = _extract_full_text_from_element(source_elem)
        target_elem = _child(segment, 'target')
        if target_elem is not None:
            entry['target'] = _extract_full_text_from_element(target_elem)
        # In 2.x the state is on the segment (on the target only in non-conforming files).
        state = segment.get('state') or (target_elem.get('state') if target_elem is not None else None)
        if state:
            entry['state'] = state
        entries.append(entry)
    return entries


def _plain_text(flat: str) -> str:
    """A flat string as plain text for a translator note: inline elements left out."""
    return re.sub(r"\s+", " ", decode_flat(_INLINE_TOKEN_RE.sub("", flat or ""))).strip()


def segment_contexts(xliff_content: Dict[str, Any]) -> Dict[str, str]:
    """
    Translator notes for the segments of multi-segment 2.x units: each segment is translated as
    its own text, with the whole message (every segment of the unit) as context.
    """
    by_unit: Dict[str, List[Dict[str, Any]]] = {}
    for file_data in xliff_content.get('files', []):
        for unit in file_data.get('trans-units', []):
            if unit.get('unit_id') is not None and unit.get('translate') is not False:
                by_unit.setdefault(unit['unit_id'], []).append(unit)
    contexts = {}
    for entries in by_unit.values():
        whole = " ".join(_plain_text(e.get('source', '')) for e in entries)
        for entry in entries:
            contexts[entry['id']] = (
                f"Segment {entry['segment'] + 1} of {entry['segments']} of one message: translate "
                f"only this segment, so that the translated segments read as one text. "
                f"Whole message: {whole}"
            )
    return contexts


# ---------------------------------------------------------------------------
# Writing by editing the file text
# ---------------------------------------------------------------------------
#
# The file is scanned with regular expressions over a masked copy of its text (comments, CDATA,
# processing instructions and 1.2 <alt-trans> blanked out, same length), so positions found in
# the copy are positions in the file. Edits are collected against the original text and applied
# in one pass; nothing outside them changes.

_ATTRS = r"(?P<attrs>(?:[^>\"']|\"[^\"]*\"|'[^']*')*?)"


def _open_tag_re(name: str) -> "re.Pattern[str]":
    return re.compile(r"<" + name + r"(?=[\s/>])" + _ATTRS + r"(?P<sc>/?)>")


_UNIT_OPEN_RE = re.compile(r"<(?P<name>trans-unit|unit)(?=[\s/>])" + _ATTRS + r"(?P<sc>/?)>")
_SEGMENT_OPEN_RE = _open_tag_re("segment")
_SOURCE_OPEN_RE = _open_tag_re("source")
_TARGET_OPEN_RE = _open_tag_re("target")
_FILE_OPEN_RE = _open_tag_re("file")
_XLIFF_OPEN_RE = _open_tag_re("xliff")
_HIDDEN_RE = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>", re.DOTALL)
_ALT_TRANS_RE = re.compile(r"<alt-trans(?=[\s/>]).*?</alt-trans\s*>", re.DOTALL)

Edit = Tuple[int, int, str]


@dataclass
class _Element:
    start: int
    open_end: int
    end: int
    attrs: str
    self_closing: bool


@dataclass
class _Unit:
    unit_id: str
    start: int
    open_end: int
    close_start: int
    end: int


@dataclass
class _Slot:
    """Where the <source>/<target> of one key live: a 1.2 unit or a 2.x segment."""
    key: str
    unit: _Unit
    lo: int
    hi: int
    segment: Optional[_Element] = None


def _mask(text: str) -> str:
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    return _ALT_TRANS_RE.sub(blank, _HIDDEN_RE.sub(blank, text))


def _attr_value(attrs: str, name: str) -> Optional[str]:
    m = re.search(r"(?:^|\s)" + re.escape(name) + r"\s*=\s*([\"'])(.*?)\1", attrs, re.DOTALL)
    return html.unescape(m.group(2)) if m else None


def _quote_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def _set_attr(attrs: str, name: str, value: str) -> str:
    pattern = re.compile(r"(\s" + re.escape(name) + r"\s*=\s*)([\"'])(.*?)\2", re.DOTALL)
    quoted = _quote_attr(value)
    if pattern.search(attrs):
        return pattern.sub(lambda m: m.group(1) + '"' + quoted + '"', attrs, count=1)
    return attrs.rstrip() + f' {name}="{quoted}"'


def _remove_attr(attrs: str, name: str) -> str:
    return re.sub(r"\s+" + re.escape(name) + r"\s*=\s*([\"']).*?\1", "", attrs, flags=re.DOTALL)


def _find_element(masked: str, open_re, name: str, lo: int, hi: int) -> Optional[_Element]:
    m = open_re.search(masked, lo, hi)
    if not m:
        return None
    if m.group("sc"):
        return _Element(m.start(), m.end(), m.end(), m.group("attrs"), True)
    close = re.compile(r"</" + name + r"\s*>").search(masked, m.end(), hi)
    if not close:
        return None
    return _Element(m.start(), m.end(), close.end(), m.group("attrs"), False)


def _indent_before(text: str, pos: int) -> Optional[str]:
    """The whitespace between the start of the line and `pos`, or None if there is other text."""
    line_start = text.rfind("\n", 0, pos) + 1
    indent = text[line_start:pos]
    return indent if indent.strip() == "" else None


def _scan_units(masked: str) -> List[_Unit]:
    units = []
    pos = 0
    while True:
        m = _UNIT_OPEN_RE.search(masked, pos)
        if not m:
            return units
        pos = m.end()
        if m.group("sc"):
            continue
        close = re.compile(r"</" + m.group("name") + r"\s*>").search(masked, m.end())
        if not close:
            return units
        units.append(_Unit(_attr_value(m.group("attrs"), "id") or "", m.start(), m.end(), close.start(), close.end()))
        pos = close.end()


def _scan_slots(masked: str, is2: bool) -> List[_Slot]:
    slots = []
    for unit in _scan_units(masked):
        if not unit.unit_id:
            continue
        segments = []
        if is2:
            pos = unit.open_end
            while True:
                seg = _find_element(masked, _SEGMENT_OPEN_RE, "segment", pos, unit.close_start)
                if seg is None:
                    break
                segments.append(seg)
                pos = seg.end
        if not segments:
            slots.append(_Slot(unit.unit_id, unit, unit.open_end, unit.close_start))
            continue
        for index, seg in enumerate(segments):
            key = segment_key(unit.unit_id, index, len(segments))
            slots.append(_Slot(key, unit, seg.open_end, seg.end, seg))
    return slots


def _is2_text(masked: str) -> bool:
    m = _XLIFF_OPEN_RE.search(masked)
    return bool(m) and _is_v2(_attr_value(m.group("attrs"), "version"))


def _slot_edits(text: str, masked: str, slot: _Slot, op: Tuple, is2: bool, newline: str) -> List[Edit]:
    """
    Edits for one key. op: ("set", target inner XML, state or None) or ("clear",).
    A state of None keeps the attributes the target (1.2) or segment (2.x) has.
    """
    edits: List[Edit] = []
    target = _find_element(masked, _TARGET_OPEN_RE, "target", slot.lo, slot.hi)
    if op[0] == "set":
        _, xml, state = op
        if target is not None:
            attrs = target.attrs.rstrip() if target.self_closing else target.attrs
            if state and not is2:
                attrs = _set_attr(attrs, "state", state)
            edits.append((target.start, target.end, f"<target{attrs}>{xml}</target>"))
        else:
            attrs = f' state="{_quote_attr(state)}"' if state and not is2 else ""
            element = f"<target{attrs}>{xml}</target>"
            source = _find_element(masked, _SOURCE_OPEN_RE, "source", slot.lo, slot.hi)
            if source is None:
                return []
            indent = _indent_before(text, source.start)
            separator = newline + indent if indent is not None else ""
            edits.append((source.end, source.end, separator + element))
        if is2 and state and slot.segment is not None:
            seg = slot.segment
            edits.append((seg.start, seg.open_end, f"<segment{_set_attr(seg.attrs, 'state', state)}>"))
    elif op[0] == "clear":
        if target is not None:
            start = target.start
            while start > slot.lo and text[start - 1] in " \t\r\n":
                start -= 1
            edits.append((start, target.end, ""))
        if is2 and slot.segment is not None:
            seg = slot.segment
            attrs = _remove_attr(_remove_attr(seg.attrs, "state"), "subState")
            if attrs != seg.attrs:
                edits.append((seg.start, seg.open_end, f"<segment{attrs}>"))
    return edits


def _language_edits(masked: str, is2: bool, language: str, force: bool) -> List[Edit]:
    """target-language on every 1.2 <file> / trgLang on the 2.x <xliff>: always, or if empty."""
    if not language:
        return []
    if is2:
        found = _XLIFF_OPEN_RE.search(masked)
        tags, name = ([found] if found else []), "trgLang"
    else:
        tags, name = list(_FILE_OPEN_RE.finditer(masked)), "target-language"
    edits = []
    for m in tags:
        attrs = m.group("attrs")
        if force or not (_attr_value(attrs, name) or "").strip():
            new_attrs = _set_attr(attrs, name, language)
            if m.group("sc") and new_attrs.endswith(" "):
                new_attrs = new_attrs.rstrip()
            edits.append((m.start("attrs"), m.end("attrs"), new_attrs))
    return edits


def _apply_edits(text: str, edits: List[Edit]) -> str:
    out = []
    pos = 0
    for start, end, new in sorted(edits, key=lambda e: (e[0], e[1])):
        out.append(text[pos:start])
        out.append(new)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _units_by_key(text: str) -> Dict[str, Dict[str, Any]]:
    parsed = _parse_xliff_root(ET.fromstring(text))
    units: Dict[str, Dict[str, Any]] = {}
    for file_data in parsed['files']:
        for unit in file_data['trans-units']:
            units.setdefault(unit['id'], unit)
    return units


def _target_xml(key: str, value: str) -> Optional[str]:
    try:
        return flat_to_file_xml(value)
    except ValueError as e:
        logger.warning(f"Not writing target of {key} with malformed inline elements: {decode_flat(str(e))}")
        return None


def _op_for(key: str, unit: Optional[Dict[str, Any]], current: Dict[str, Any], existing: bool) -> Optional[Tuple]:
    """The edit of one key of the file being written (None = leave it as it is)."""
    value = (unit or {}).get('target') or ''
    state = (unit or {}).get('state')
    if existing:
        # An existing target changes only where the translation changed; never cleared.
        if unit is None or not value.strip():
            return None
        if value == current.get('target') and (not state or state == current.get('state')):
            return None
        xml = _target_xml(key, value)
        if xml is None:
            return None
        return ("set", xml, state if state and state != current.get('state') else None)
    # A new target built from the source: translated units get their target, others none.
    xml = _target_xml(key, value) if value.strip() else None
    return ("set", xml, state) if xml is not None else ("clear",)


def render_xliff(content: Dict[str, Any], text: str, template_text: Optional[str],
                 existing: bool, target_language: Optional[str]) -> str:
    """
    The new text of a target file.

    existing=True: `text` is the target file; only the targets in `content` that differ from it
    are written, units of the source (`template_text`) the target lacks are copied in after the
    unit that precedes them in the source, and an empty target-language / trgLang is set.
    existing=False: `text` is the source file, used as the template of a new target.
    """
    masked = _mask(text)
    is2 = _is2_text(masked)
    newline = "\r\n" if "\r\n" in text else "\n"
    current = _units_by_key(text)
    wanted: Dict[str, Dict[str, Any]] = {}
    for file_data in content.get('files', []):
        for unit in file_data.get('trans-units', []):
            if unit.get('id'):
                wanted.setdefault(unit['id'], unit)

    edits = _language_edits(masked, is2, target_language or '', force=not existing)
    slots = _scan_slots(masked, is2)
    seen = set()
    for slot in slots:
        unit = current.get(slot.key)
        if slot.key in seen or unit is None or unit.get('translate') is False:
            continue
        seen.add(slot.key)
        op = _op_for(slot.key, wanted.get(slot.key), unit, existing)
        if op is not None:
            edits.extend(_slot_edits(text, masked, slot, op, is2, newline))

    if existing and template_text is not None:
        edits.extend(_new_unit_edits(text, masked, slots, template_text, wanted, newline))
    return _apply_edits(text, edits)


def _new_unit_edits(text: str, masked: str, slots: List[_Slot], template_text: str,
                    wanted: Dict[str, Dict[str, Any]], newline: str) -> List[Edit]:
    """Units of the source the target lacks: copied from the source with their target set."""
    t_masked = _mask(template_text)
    t_is2 = _is2_text(t_masked)
    if t_is2 != _is2_text(masked):
        logger.warning("Source and target XLIFF versions differ; new source units are not copied")
        return []
    t_current = _units_by_key(template_text)
    t_newline = "\r\n" if "\r\n" in template_text else "\n"
    t_slots = _scan_slots(t_masked, t_is2)
    base_units = {}
    for unit in _scan_units(masked):
        base_units.setdefault(unit.unit_id, unit)

    t_units: List[_Unit] = []
    slots_of: Dict[int, List[_Slot]] = {}
    for slot in t_slots:
        if id(slot.unit) not in slots_of:
            t_units.append(slot.unit)
            slots_of[id(slot.unit)] = []
        slots_of[id(slot.unit)].append(slot)

    t_path_at, _ = _containers(t_masked)
    path_at, containers = _containers(masked)
    t_unit_paths = {id(u): t_path_at(u.start) for u in t_units}
    base_paths = {id(u): path_at(u.start) for u in base_units.values()}
    position = {id(u): i for i, u in enumerate(t_units)}
    present = [i for i, u in enumerate(t_units) if u.unit_id in base_units]

    def sibling(u: _Unit, path: Tuple) -> Optional[Tuple[int, int]]:
        """
        (start, end) in the target of the child of container `path` that holds template unit `u`
        (the unit itself, or the group it is in); None if `u` is not in `path` there.
        """
        if not _within(t_unit_paths[id(u)], path):
            return None
        unit = base_units.get(u.unit_id)
        if unit is None:
            return None
        base_path = base_paths[id(unit)]
        if base_path == path:
            return unit.start, unit.end
        if _within(base_path, path):
            return containers[base_path[:len(path) + 1]][:2]
        return None

    edits: List[Edit] = []
    for t_unit in t_units:
        keys = [s.key for s in slots_of[id(t_unit)]]
        if t_unit.unit_id in base_units or not any(k in wanted for k in keys):
            continue
        block_edits: List[Edit] = []
        for slot in slots_of[id(t_unit)]:
            unit = t_current.get(slot.key)
            if unit is None or unit.get('translate') is False:
                continue
            op = _op_for(slot.key, wanted.get(slot.key), unit, existing=False)
            block_edits.extend(_slot_edits(template_text, t_masked, slot, op, t_is2, t_newline))
        block = _apply_edits(
            template_text[t_unit.start:t_unit.end],
            [(s - t_unit.start, e - t_unit.start, new) for s, e, new in block_edits],
        )
        if t_newline != newline:
            block = block.replace(t_newline, newline)

        # Placed after the unit (or group) that precedes it in its container (file, body, group)
        # in the source, else before the one that follows it, else at the end of the container:
        # it never ends up in a group it is not in (a translate="no" group, say).
        path = t_unit_paths[id(t_unit)]
        index = position[id(t_unit)]
        cut = bisect.bisect_left(present, index)
        previous = next(
            (s for s in (sibling(t_units[i], path) for i in reversed(present[:cut])) if s), None
        )
        following = next(
            (s for s in (sibling(t_units[i], path) for i in present[cut:]) if s), None
        )
        if previous is not None:
            indent = _indent_before(text, previous[0])
            edits.append((previous[1], previous[1], newline + (indent or "") + block))
        elif following is not None:
            indent = _indent_before(text, following[0])
            edits.append((following[0], following[0], block + newline + (indent or "")))
        else:
            # The end of the same container in the target, or of the closest enclosing one.
            close = next(
                (containers[path[:n]][2] for n in range(len(path), 0, -1) if path[:n] in containers),
                None,
            )
            if close is None:
                logger.warning(f"No place found for new unit {t_unit.unit_id}; not added")
                continue
            pos = close
            while pos > 0 and text[pos - 1] in " \t\r\n":
                pos -= 1
            indent = _indent_before(template_text, t_unit.start) or ""
            edits.append((pos, pos, newline + indent + block))
    return edits


_CONTAINER_TAG_RE = re.compile(r"<(?P<close>/?)(?P<name>file|body|group)(?=[\s/>])" + _ATTRS + r"(?P<sc>/?)>")


def _within(path: Tuple, container: Tuple) -> bool:
    return path[:len(container)] == container


def _containers(masked: str):
    """
    (path_at(pos), containers): path_at gives the file/body/group elements enclosing a position,
    as a tuple of (name, id); containers maps each such path to (start, end, close tag start).
    """
    spans = []  # (open_end, close_start, path)
    containers: Dict[Tuple, Tuple[int, int, int]] = {}
    stack: List[Tuple[Tuple, int, int]] = []
    for m in _CONTAINER_TAG_RE.finditer(masked):
        if m.group("close"):
            if stack:
                path, start, open_end = stack.pop()
                spans.append((open_end, m.start(), path))
                containers.setdefault(path, (start, m.end(), m.start()))
        elif not m.group("sc"):
            attrs = m.group("attrs")
            ident = _attr_value(attrs, "id") or _attr_value(attrs, "original") or ""
            parent = stack[-1][0] if stack else ()
            stack.append((parent + ((m.group("name"), ident),), m.start(), m.end()))

    def path_at(pos: int) -> Tuple:
        best: Tuple = ()
        for open_end, close_start, path in spans:
            if open_end <= pos < close_start and len(path) > len(best):
                best = path
        return best

    return path_at, containers


def set_targets(text: str, values: Dict[str, str]) -> Tuple[str, List[str]]:
    """
    Replace the <target> of the given keys (flat strings) in an XLIFF file text, keeping its
    attributes and everything else. Returns (new text, keys whose unit was not found).
    """
    masked = _mask(text)
    is2 = _is2_text(masked)
    newline = "\r\n" if "\r\n" in text else "\n"
    slots = {}
    for slot in _scan_slots(masked, is2):
        slots.setdefault(slot.key, slot)
    edits: List[Edit] = []
    not_found = []
    for key, value in values.items():
        slot = slots.get(key)
        slot_edits = (
            _slot_edits(text, masked, slot, ("set", flat_to_file_xml(value), None), is2, newline)
            if slot is not None else []
        )
        if not slot_edits:
            not_found.append(key)
        edits.extend(slot_edits)
    return _apply_edits(text, edits), not_found


def is_valid_xliff_file(file_path: str) -> bool:
    """
    Check if a file is a valid XLIFF file.

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file is a valid XLIFF file, False otherwise
    """
    try:
        content = read_xliff_file(file_path)
        return 'files' in content and isinstance(content['files'], list)
    except (FileNotFoundError, ValueError, ET.ParseError):
        return False


def get_xliff_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from XLIFF file path or content.

    Args:
        file_path: Path to the XLIFF file

    Returns:
        Language code if found, None otherwise
    """
    # Try to extract from filename (e.g., messages.en.xlf -> en, messages.en_US.xlf -> en_US)
    filename = os.path.basename(file_path)
    if '.' in filename:
        parts = filename.split('.')
        if len(parts) >= 3:  # messages.en.xlf or messages.en_US.xlf
            potential_lang = parts[-2]
            if len(potential_lang) == 2 or len(potential_lang) == 5:  # en or en_US
                return potential_lang
            # Handle cases like messages.en_US.xlf where we need to check for underscore
            elif '_' in potential_lang and len(potential_lang) == 5:  # en_US format
                return potential_lang

    # Try to extract from XLIFF content
    try:
        content = read_xliff_file(file_path)
        if 'files' in content and content['files']:
            file_data = content['files'][0]
            return file_data.get('target-language')
    except (ValueError, ET.ParseError, FileNotFoundError):
        pass

    return None
