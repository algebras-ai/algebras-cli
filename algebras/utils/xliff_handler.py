"""
XLIFF (XML Localization Interchange File Format) file handler
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from xml.dom import minidom


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
    if 'files' in content and isinstance(content['files'], list) and content['files']:
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
                        source_elem.text = unit['source']
                        target_elem = ET.SubElement(segment, 'target')
                        target_elem.text = unit.get('target', unit['source'])
                        # Add state attribute only if unit explicitly has one
                        if 'state' in unit and unit['state']:
                            target_elem.set('state', unit['state'])
                    else:
                        # XLIFF 1.2: use <trans-unit>
                        trans_unit = ET.SubElement(container, 'trans-unit')
                        trans_unit.set('id', unit['id'])
                        source_elem = ET.SubElement(trans_unit, 'source')
                        source_elem.text = unit['source']
                        target_elem = ET.SubElement(trans_unit, 'target')
                        target_elem.text = unit.get('target', unit['source'])
                        # Add state attribute only if unit explicitly has one
                        if 'state' in unit and unit['state']:
                            target_elem.set('state', unit['state'])
    else:
        # Handle flat dictionary structure (always write as XLIFF 1.2)
        for key, value in content.items():
            if isinstance(value, str):
                trans_unit = ET.SubElement(container, 'trans-unit')
                trans_unit.set('id', key)
                source_elem = ET.SubElement(trans_unit, 'source')
                source_elem.text = value
                target_elem = ET.SubElement(trans_unit, 'target')
                target_elem.text = value
                # Don't add state for flat dictionary structure - state should be set in update_xliff_targets
    
    # Write to file with proper formatting
    rough_string = ET.tostring(xliff_root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    
    with open(file_path, 'wb') as f:
        f.write(pretty_xml)


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


def update_xliff_targets(xliff_content: Dict[str, Any], translations: Dict[str, str], 
                         source_content: Optional[Dict[str, Any]] = None,
                         target_state: Optional[str] = None) -> Dict[str, Any]:
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
    
    # Track which unit IDs already exist in target
    existing_unit_ids = set()
    
    if 'files' in updated_content:
        for file_data in updated_content['files']:
            if 'trans-units' in file_data:
                for unit in file_data['trans-units']:
                    unit_id = unit.get('id')
                    if unit_id:
                        existing_unit_ids.add(unit_id)
                        if unit_id in translations:
                            # Update target with translation, preserve source
                            unit['target'] = translations[unit_id]
                        elif 'source' in unit and not unit.get('target'):
                            # If no translation provided but source exists, use source as target
                            unit['target'] = unit['source']
    
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
                            new_unit = {
                                'id': source_unit_id,
                                'source': source_unit.get('source', ''),
                                'target': translations.get(source_unit_id, source_unit.get('source', ''))
                            }
                            # Add state attribute if provided
                            if target_state:
                                new_unit['state'] = target_state
                            target_file_data['trans-units'].append(new_unit)
    
    return updated_content


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
                        unit_data['source'] = source_elem.text or ''
                    
                    target_elem = segment.find('target') or segment.find(f'{{{namespace}}}target')
                    if target_elem is not None:
                        unit_data['target'] = target_elem.text or ''
                        # Preserve state attribute if present (check for both None and empty string)
                        state_attr = target_elem.get('state')
                        if state_attr:
                            unit_data['state'] = state_attr
                else:
                    # Fallback: look for source/target directly in unit
                    source_elem = unit.find('source') or unit.find(f'{{{namespace}}}source')
                    if source_elem is not None:
                        unit_data['source'] = source_elem.text or ''
                    
                    target_elem = unit.find('target') or unit.find(f'{{{namespace}}}target')
                    if target_elem is not None:
                        unit_data['target'] = target_elem.text or ''
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
                    unit_data['source'] = source_elem.text or ''
                
                target_elem = trans_unit.find('target') or trans_unit.find(f'{{{namespace}}}target')
                if target_elem is not None:
                    unit_data['target'] = target_elem.text or ''
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
