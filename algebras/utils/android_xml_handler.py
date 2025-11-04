"""
Android XML localization file handler
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Set
import html
import re

# Import Config to check normalization settings
from algebras.config import Config


def read_android_xml_file(file_path: str) -> Dict[str, Any]:
    """
    Read an Android XML localization file and extract strings and plurals.
    
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
    
    result = {}
    
    # Process string elements
    for string_elem in root.findall('string'):
        name = string_elem.get('name')
        if name is None:
            continue
            
        # Get the text content, handling CDATA and escaped characters
        text = _get_element_text(string_elem)
        if text is not None:
            result[name] = text
    
    # Process plurals elements
    for plurals_elem in root.findall('plurals'):
        name = plurals_elem.get('name')
        if name is None:
            continue
            
        plural_dict = {}
        for item_elem in plurals_elem.findall('item'):
            quantity = item_elem.get('quantity')
            if quantity is None:
                continue
                
            text = _get_element_text(item_elem)
            if text is not None:
                plural_dict[quantity] = text
        
        if plural_dict:
            # Store plurals with a special key structure
            result[f"{name}.__plurals__"] = plural_dict
    
    return result


def write_android_xml_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write a dictionary to an Android XML localization file.
    
    Args:
        file_path: Path to the Android XML file
        content: Dictionary to write
    """
    # Create the root element
    root = ET.Element('resources')
    
    # Sort keys to ensure consistent output
    sorted_keys = sorted(content.keys())
    
    for key in sorted_keys:
        value = content[key]
        
        if key.endswith('.__plurals__'):
            # Handle plurals
            base_name = key[:-12]  # Remove '.__plurals__' suffix
            plurals_elem = ET.SubElement(root, 'plurals')
            plurals_elem.set('name', base_name)
            
            if isinstance(value, dict):
                # Sort quantities in a logical order
                quantity_order = ['zero', 'one', 'two', 'few', 'many', 'other']
                sorted_quantities = sorted(value.keys(), key=lambda x: quantity_order.index(x) if x in quantity_order else len(quantity_order))
                
                for quantity in sorted_quantities:
                    if quantity in value:
                        item_elem = ET.SubElement(plurals_elem, 'item')
                        item_elem.set('quantity', quantity)
                        item_elem.text = _escape_xml_text(str(value[quantity]))
        else:
            # Handle regular strings
            string_elem = ET.SubElement(root, 'string')
            string_elem.set('name', key)
            string_elem.text = _escape_xml_text(str(value))
    
    # Create the tree and write it
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")  # Pretty print with 4 spaces
    
    # Write with XML declaration and UTF-8 encoding
    with open(file_path, 'wb') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'.encode('utf-8'))
        tree.write(f, encoding='utf-8', xml_declaration=False)


def _get_element_text(element: ET.Element) -> str:
    """
    Extract text content from an XML element, handling CDATA and mixed content.
    
    Args:
        element: The XML element
        
    Returns:
        The text content as a string
    """
    # Get all text content including tail text of child elements
    text_parts = []
    
    if element.text:
        text_parts.append(element.text)
    
    for child in element:
        if child.tail:
            text_parts.append(child.tail)
    
    text = ''.join(text_parts).strip()
    
    # Unescape XML entities
    text = html.unescape(text)
    
    # Handle Android-specific escape sequences
    text = text.replace("\\'", "'")
    text = text.replace('\\"', '"')
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    
    return text


def _escape_xml_text(text: str) -> str:
    """
    Escape text for XML content, handling Android-specific requirements.
    
    Args:
        text: The text to escape
        
    Returns:
        Escaped text suitable for XML
    """
    # Escape XML special characters
    text = html.escape(text, quote=False)
    
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
    
    # Handle Android-specific escape sequences
    # Only escape quotes if normalization is disabled
    if not normalize_strings:
        text = text.replace("'", "\\'")
        text = text.replace('"', '\\"')
    
    # Always escape newlines and tabs for XML compatibility
    text = text.replace('\n', '\\n')
    text = text.replace('\t', '\\t')
    
    return text


def write_android_xml_file_in_place(file_path: str, content: Dict[str, Any], keys_to_update: Optional[Set[str]] = None) -> None:
    """
    Update an existing Android XML file in-place, preserving structure, comments, formatting, and order.
    
    Args:
        file_path: Path to the Android XML file
        content: Dictionary containing translations to update
        keys_to_update: Optional set of keys to update. If None, all keys in content will be updated.
    """
    import os
    
    if not os.path.exists(file_path):
        # If file doesn't exist, fall back to regular write
        write_android_xml_file(file_path, content)
        return
    
    # Read the existing file content as text to preserve comments and formatting
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # Extract original namespace declaration from <resources> tag to preserve it
    # Match: <resources xmlns:tools="..."> or <resources xmlns:ns0="..."> etc.
    namespace_match = re.search(r'<resources\s+([^>]*)>', original_content)
    original_resources_tag = None
    if namespace_match:
        original_resources_tag = namespace_match.group(1)
    
    # Track which keys originally had &#160; entities (for preservation)
    keys_with_entities = set()
    # Find all string elements with &#160; entities
    for match in re.finditer(r'<string\s+name="([^"]+)"[^>]*>([^<]*)&#160;([^<]*)</string>', original_content):
        key_name = match.group(1)
        keys_with_entities.add(key_name)
    
    # Parse XML to get structure
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        # If parsing fails, fall back to regular write
        write_android_xml_file(file_path, content)
        return
    
    if root.tag != 'resources':
        # If not a resources file, fall back to regular write
        write_android_xml_file(file_path, content)
        return
    
    # Track which keys we've updated
    updated_keys = set()
    
    # Update existing string elements
    for string_elem in root.findall('string'):
        name = string_elem.get('name')
        if name is None:
            continue
        
        # Check if we should update this key
        if keys_to_update is not None and name not in keys_to_update:
            continue
        
        if name in content:
            # Update the text content
            new_value = str(content[name])
            string_elem.text = _escape_xml_text(new_value)
            updated_keys.add(name)
    
    # Update existing plurals elements
    for plurals_elem in root.findall('plurals'):
        name = plurals_elem.get('name')
        if name is None:
            continue
        
        plural_key = f"{name}.__plurals__"
        
        # Check if we should update this key
        if keys_to_update is not None and plural_key not in keys_to_update:
            continue
        
        if plural_key in content and isinstance(content[plural_key], dict):
            # Update plural items
            plural_dict = content[plural_key]
            for item_elem in plurals_elem.findall('item'):
                quantity = item_elem.get('quantity')
                if quantity and quantity in plural_dict:
                    item_elem.text = _escape_xml_text(str(plural_dict[quantity]))
            updated_keys.add(plural_key)
    
    # Add new keys that don't exist in the file
    new_keys = set()
    if keys_to_update is None:
        # Add all keys from content that weren't updated
        new_keys = set(content.keys()) - updated_keys
    else:
        # Add only keys from keys_to_update that weren't updated
        new_keys = keys_to_update - updated_keys
    
    # Add new string elements at the end
    for key in sorted(new_keys):
        if key.endswith('.__plurals__'):
            # Handle new plurals
            base_name = key[:-12]
            if key in content and isinstance(content[key], dict):
                plurals_elem = ET.SubElement(root, 'plurals')
                plurals_elem.set('name', base_name)
                
                quantity_order = ['zero', 'one', 'two', 'few', 'many', 'other']
                sorted_quantities = sorted(content[key].keys(), key=lambda x: quantity_order.index(x) if x in quantity_order else len(quantity_order))
                
                for quantity in sorted_quantities:
                    if quantity in content[key]:
                        item_elem = ET.SubElement(plurals_elem, 'item')
                        item_elem.set('quantity', quantity)
                        item_elem.text = _escape_xml_text(str(content[key][quantity]))
        else:
            # Handle new strings
            if key in content:
                string_elem = ET.SubElement(root, 'string')
                string_elem.set('name', key)
                string_elem.text = _escape_xml_text(str(content[key]))
    
    # Write the updated tree back
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")  # Pretty print with 4 spaces
    
    # Write with XML declaration and UTF-8 encoding
    with open(file_path, 'wb') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'.encode('utf-8'))
        tree.write(f, encoding='utf-8', xml_declaration=False)
    
    # Now we need to preserve HTML entities like &#160; by post-processing
    # Read the file back and replace escaped non-breaking spaces with entities
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    # Replace non-breaking space character (U+00A0) with &#160; entity
    # This preserves the entity format if it was in the original
    # We need to be careful - only replace if the value actually contains a non-breaking space
    # But since we're writing, we should preserve entities properly
    # Actually, the issue is that html.escape converts entities, so we need to handle this differently
    
    # For now, let's ensure that if the original content had &#160;, we check if we should preserve it
    # But since we're updating in-place, we should preserve the entity format when possible
    
    # Write back with proper entity handling and namespace prefix preservation
    # Replace non-breaking space character (U+00A0) with &#160; entity
    # This preserves the entity format for keys that originally had it
    # Also restore original namespace prefix (xmlns:tools instead of xmlns:ns0)
    with open(file_path, 'w', encoding='utf-8') as f:
        lines = file_content.split('\n')
        for i, line in enumerate(lines):
            # Restore original namespace prefix in <resources> tag
            if '<resources' in line and original_resources_tag:
                # Replace the namespace declaration with the original one
                # Handle both cases: <resources> (no attributes) and <resources xmlns:ns0="..."> (renamed)
                if re.search(r'<resources\s+[^>]*>', line):
                    # Has attributes - replace them
                    line = re.sub(r'<resources\s+[^>]*>', f'<resources {original_resources_tag}>', line)
                else:
                    # No attributes - add the original namespace
                    line = re.sub(r'<resources>', f'<resources {original_resources_tag}>', line)
                lines[i] = line
            
            # Check if this line contains a string element we updated
            if '<string name=' in line and '>' in line:
                # Extract key name to check if it should preserve entities
                key_match = re.search(r'<string\s+name="([^"]+)"', line)
                if key_match:
                    key_name = key_match.group(1)
                    # Replace non-breaking space with entity if:
                    # 1. The key originally had &#160; entities, OR
                    # 2. The line currently contains a non-breaking space
                    if key_name in keys_with_entities or '\u00A0' in line:
                        lines[i] = line.replace('\u00A0', '&#160;')
        f.write('\n'.join(lines)) 