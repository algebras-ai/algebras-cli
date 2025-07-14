"""
Android XML localization file handler
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any
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
    # Only escape apostrophes if normalization is disabled
    if not normalize_strings:
        text = text.replace("'", "\\'")
    
    # Always escape double quotes, newlines, and tabs for XML compatibility
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\t', '\\t')
    
    return text 