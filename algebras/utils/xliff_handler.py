"""
XLIFF (XML Localization Interchange File Format) file handler
"""

import os
import re
import logging
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from xml.dom import minidom

logger = logging.getLogger(__name__)


def read_xliff_file(file_path: str) -> Dict[str, Any]:
    """
    Read an XLIFF file and return its content as a dictionary.
    
    Args:
        file_path: Path to the XLIFF file
        
    Returns:
        Dictionary containing the XLIFF file content
        
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
    
    return _parse_xliff_root(root)


def write_xliff_file(file_path: str, content: Dict[str, Any], 
                    source_language: str = "en", target_language: str = "en",
                    target_state: Optional[str] = None) -> None:
    """
    Write content to an XLIFF file.
    
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
    
    # For XLIFF 2.0, set srcLang on root element
    if version == '2.0':
        xliff_root.set('srcLang', source_language)
    
    file_elem = ET.SubElement(xliff_root, 'file')
    
    # Preserve original file attributes from content if available
    if 'files' in content and content['files']:
        file_data = content['files'][0]
        file_elem.set('original', file_data.get('original', 'messages'))
        file_elem.set('source-language', file_data.get('source-language', source_language))
        file_elem.set('target-language', file_data.get('target-language', target_language))
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
        file_data = content['files'][0]
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
                            logger.debug(f"Added state '{unit_state}' to segment for unit {unit.get('id', 'unknown')} (XLIFF 2.0)")
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
                            logger.debug(f"Added state '{unit_state}' to target for unit {unit.get('id', 'unknown')} (XLIFF 1.2)")
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
                    logger.debug(f"Added state '{target_state}' to target for unit {key} from flat dict (XLIFF 1.2)")
    
    # Write to file with proper formatting
    # Use ET.tostring with xml_declaration for better compatibility
    rough_string = ET.tostring(xliff_root, encoding='unicode', xml_declaration=True)
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    if inline_xml:
        pretty_text = pretty_xml.decode('utf-8')
        for marker, xml in inline_xml.items():
            pretty_text = pretty_text.replace(marker, xml, 1)
        pretty_xml = pretty_text.encode('utf-8')
    
    # Ensure the file is written correctly
    with open(file_path, 'wb') as f:
        f.write(pretty_xml)
    
    # Verify the written file can be parsed correctly
    # This ensures namespace handling is correct
    try:
        test_tree = ET.parse(file_path)
        test_root = test_tree.getroot()
        # Try to find target element to verify it's accessible
        # This helps catch namespace issues early
        test_target = test_root.find(f'.//{{{namespace}}}target')
        if test_target is None:
            test_target = test_root.find('.//target')
    except Exception:
        # If verification fails, it's not critical - the file was still written
        pass


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
            logger.warning(f"Not writing target with malformed inline elements: {e}")
            element.text = ''
            return False
        xml = _escape_text(value)
    marker = f"\ue000{len(inline_xml)}\ue001"
    inline_xml[marker] = xml
    element.text = marker
    return True


def extract_translatable_strings(xliff_content: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract translatable strings from XLIFF content.
    
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
                    if 'id' in unit and 'source' in unit:
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
    """Why `translation` must not be written as the target of `source` (None = OK)."""
    from algebras.services.placeholders.formats.xliff import translation_problem

    return translation_problem(source, translation)


def update_xliff_targets(xliff_content: Dict[str, Any], translations: Dict[str, str], 
                         source_content: Optional[Dict[str, Any]] = None,
                         target_state: Optional[str] = None,
                         only_missing: bool = False) -> Dict[str, Any]:
    """
    Update XLIFF target elements with translated strings while preserving source text.
    Also adds new units from source that don't exist in target.
    
    Args:
        xliff_content: Original XLIFF content structure (target file)
        translations: Dictionary of translated strings (key -> translated_value)
        source_content: Optional source XLIFF content to add missing units from
        target_state: Optional state attribute to add to target elements (e.g., "translated", "needs-review-translation")
        
    Returns:
        Updated XLIFF content with target elements updated and new units added
    """
    import copy
    updated_content = copy.deepcopy(xliff_content)
    
    # Ensure version is preserved in updated content
    # If version is missing, try to get it from source_content or original xliff_content
    if 'version' not in updated_content:
        if source_content and 'version' in source_content:
            updated_content['version'] = source_content['version']
            logger.debug(f"XLIFF version {source_content['version']} copied from source_content")
        elif 'version' in xliff_content:
            updated_content['version'] = xliff_content['version']
            logger.debug(f"XLIFF version {xliff_content['version']} preserved from xliff_content")
    else:
        logger.debug(f"XLIFF version {updated_content['version']} already present in updated_content")
    
    final_version = updated_content.get('version', 'unknown')
    logger.debug(f"Processing XLIFF with version {final_version}, target_state={target_state}, only_missing={only_missing}")
    
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
        logger.debug("Created file entry in updated_content from source_content")
    
    if 'files' in updated_content:
        for file_data in updated_content['files']:
            if 'trans-units' in file_data:
                for unit in file_data['trans-units']:
                    unit_id = unit.get('id')
                    if unit_id:
                        existing_unit_ids.add(unit_id)
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
                                logger.debug(f"Preserved existing state '{existing_state}' for unit {unit_id}")
                        elif 'source' in unit and not existing_target:
                            # If no translation provided but source exists and target is empty
                            # Leave target empty rather than copying source - this indicates missing translation
                            logger.debug(f"No translation provided for existing unit {unit_id}, leaving target empty")
                            unit['target'] = ''
                            # DO NOT add state to existing units
    
    # Add new units from source that don't exist in target
    if source_content and 'files' in source_content:
        for source_file_data in source_content['files']:
            if 'trans-units' in source_file_data:
                # Find the corresponding target file data
                target_file_data = None
                if 'files' in updated_content and updated_content['files']:
                    target_file_data = updated_content['files'][0]
                    if 'trans-units' not in target_file_data:
                        target_file_data['trans-units'] = []
                
                if target_file_data:
                    for source_unit in source_file_data['trans-units']:
                        source_unit_id = source_unit.get('id')
                        if source_unit_id and source_unit_id not in existing_unit_ids:
                            # This is a new unit from source, add it to target
                            # Check if we have a translation, otherwise use empty string (not source)
                            target_value = translations.get(source_unit_id, '')
                            problem = _translation_problem(source_unit.get('source', ''), target_value) if target_value else None
                            if problem:
                                logger.warning(f"Not writing translation of unit {source_unit_id}: {problem}")
                                print(f"  ⚠ Left '{source_unit_id}' untranslated: {problem}")
                                target_value = ''
                            if not target_value:
                                # No translation provided - this is important to detect
                                logger.warning(f"No translation provided for new unit {source_unit_id}, using empty target")
                            
                            new_unit = {
                                'id': source_unit_id,
                                'source': source_unit.get('source', ''),
                                'target': target_value
                            }
                            # Add state attribute if provided (an untranslated unit gets none)
                            if target_state and target_value:
                                new_unit['state'] = target_state
                                logger.debug(f"Added state '{target_state}' to new unit {source_unit_id} from source")
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
    Parse XLIFF root element into a dictionary.
    Supports both XLIFF 1.2 and 2.0 formats.
    
    Args:
        root: XLIFF root element
        
    Returns:
        Dictionary representation of XLIFF content
    """
    version = root.get('version', '1.2')
    result = {
        'version': version,
        'files': []
    }
    
    # Determine namespace based on version
    if version == '2.0':
        namespace = 'urn:oasis:names:tc:xliff:document:2.0'
    else:
        namespace = 'urn:oasis:names:tc:xliff:document:1.2'
    
    # Get source language from root (XLIFF 2.0) or from file element (XLIFF 1.2)
    source_lang = root.get('srcLang') or root.get('source-language', '')
    
    # Parse file elements (handle both with and without namespace)
    file_elements = root.findall('.//file') or root.findall(f'.//{{{namespace}}}file')
    
    for file_elem in file_elements:
        # XLIFF 2.0 uses srcLang on root, 1.2 uses source-language on file
        file_source_lang = file_elem.get('source-language') or source_lang
        file_data = {
            'original': file_elem.get('original', ''),
            'source-language': file_source_lang,
            'target-language': file_elem.get('target-language', ''),
            'datatype': file_elem.get('datatype', 'plaintext'),
            'trans-units': []
        }
        
        if version == '2.0':
            # XLIFF 2.0: <unit> with <segment> containing <source>/<target>
            units = file_elem.findall('.//unit') or file_elem.findall(f'.//{{{namespace}}}unit')
            
            for unit in units:
                unit_data = {
                    'id': unit.get('id', ''),
                    'source': '',
                    'target': ''
                }
                
                # Find segment element
                segment = unit.find('segment') or unit.find(f'{{{namespace}}}segment')
                if segment is not None:
                    # Find source and target within segment
                    source_elem = segment.find('source') or segment.find(f'{{{namespace}}}source')
                    if source_elem is not None:
                        unit_data['source'] = _extract_full_text_from_element(source_elem)
                    
                    target_elem = segment.find('target') or segment.find(f'{{{namespace}}}target')
                    if target_elem is not None:
                        unit_data['target'] = _extract_full_text_from_element(target_elem)
                    
                    # For XLIFF 2.0, state is on segment, not target
                    state_attr = segment.get('state')
                    if state_attr:
                        unit_data['state'] = state_attr
                    else:
                        # Fallback: check target for state (for compatibility)
                        if target_elem is not None:
                            target_state_attr = target_elem.get('state')
                            if target_state_attr:
                                unit_data['state'] = target_state_attr
                else:
                    # Fallback: look for source/target directly in unit
                    source_elem = unit.find('source') or unit.find(f'{{{namespace}}}source')
                    if source_elem is not None:
                        unit_data['source'] = _extract_full_text_from_element(source_elem)
                    
                    target_elem = unit.find('target') or unit.find(f'{{{namespace}}}target')
                    if target_elem is not None:
                        unit_data['target'] = _extract_full_text_from_element(target_elem)
                        # Preserve state attribute if present (check for both None and empty string)
                        state_attr = target_elem.get('state')
                        if state_attr:
                            unit_data['state'] = state_attr
                
                file_data['trans-units'].append(unit_data)
        else:
            # XLIFF 1.2: <trans-unit> with <source>/<target> in <body>
            trans_units = file_elem.findall('.//trans-unit') or file_elem.findall(f'.//{{{namespace}}}trans-unit')
            
            for trans_unit in trans_units:
                unit_data = {
                    'id': trans_unit.get('id', ''),
                    'source': '',
                    'target': ''
                }
                
                # Find source and target elements (handle both with and without namespace)
                source_elem = trans_unit.find('source') or trans_unit.find(f'{{{namespace}}}source')
                if source_elem is not None:
                    unit_data['source'] = _extract_full_text_from_element(source_elem)
                
                target_elem = trans_unit.find('target') or trans_unit.find(f'{{{namespace}}}target')
                if target_elem is not None:
                    unit_data['target'] = _extract_full_text_from_element(target_elem)
                    # Preserve state attribute if present (check for both None and empty string)
                    state_attr = target_elem.get('state')
                    if state_attr:
                        unit_data['state'] = state_attr
                
                file_data['trans-units'].append(unit_data)
        
        result['files'].append(file_data)
    
    return result


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
