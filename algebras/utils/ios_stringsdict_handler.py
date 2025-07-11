"""
iOS .stringsdict localization file handler
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
import os


def read_ios_stringsdict_file(file_path: str) -> Dict[str, Any]:
    """
    Read an iOS .stringsdict localization file and extract key-value pairs.
    
    Args:
        file_path: Path to the iOS .stringsdict file
        
    Returns:
        Dictionary containing the translation content
    """
    if not os.path.exists(file_path):
        return {}
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Find the main dict element
        main_dict = root.find('.//dict')
        if main_dict is None:
            return {}
        
        return _parse_dict_element(main_dict)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in .stringsdict file {file_path}: {e}")


def write_ios_stringsdict_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write a dictionary to an iOS .stringsdict localization file.
    
    Args:
        file_path: Path to the iOS .stringsdict file
        content: Dictionary to write
    """
    # Create the XML structure
    root = ET.Element("plist")
    root.set("version", "1.0")
    
    # Add DOCTYPE
    # Note: ElementTree doesn't handle DOCTYPE well, so we'll add it manually later
    
    main_dict = ET.SubElement(root, "dict")
    _dict_to_xml(content, main_dict)
    
    # Create the tree and write
    tree = ET.ElementTree(root)
    
    # Write with proper formatting
    _write_formatted_xml(tree, file_path)


def _parse_dict_element(dict_elem: ET.Element) -> Dict[str, Any]:
    """
    Parse a dict XML element into a Python dictionary.
    
    Args:
        dict_elem: The dict XML element
        
    Returns:
        Python dictionary representation
    """
    result = {}
    
    # Process key-value pairs
    children = list(dict_elem)
    for i in range(0, len(children), 2):
        if i + 1 >= len(children):
            break
            
        key_elem = children[i]
        value_elem = children[i + 1]
        
        if key_elem.tag != "key":
            continue
            
        key = key_elem.text or ""
        value = _parse_value_element(value_elem)
        result[key] = value
    
    return result


def _parse_value_element(elem: ET.Element) -> Any:
    """
    Parse a value XML element (string, dict, etc.) into a Python value.
    
    Args:
        elem: The value XML element
        
    Returns:
        Python value representation
    """
    if elem.tag == "string":
        return elem.text or ""
    elif elem.tag == "dict":
        return _parse_dict_element(elem)
    elif elem.tag == "integer":
        return int(elem.text or "0")
    elif elem.tag == "real":
        return float(elem.text or "0.0")
    elif elem.tag == "true":
        return True
    elif elem.tag == "false":
        return False
    else:
        # Default to string representation
        return elem.text or ""


def _dict_to_xml(data: Dict[str, Any], parent: ET.Element) -> None:
    """
    Convert a Python dictionary to XML dict format.
    
    Args:
        data: Dictionary to convert
        parent: Parent XML element to append to
    """
    # Sort keys for consistent output
    sorted_keys = sorted(data.keys())
    
    for key in sorted_keys:
        value = data[key]
        
        # Add key element
        key_elem = ET.SubElement(parent, "key")
        key_elem.text = str(key)
        
        # Add value element
        _value_to_xml(value, parent)


def _value_to_xml(value: Any, parent: ET.Element) -> None:
    """
    Convert a Python value to appropriate XML element.
    
    Args:
        value: Value to convert
        parent: Parent XML element to append to
    """
    if isinstance(value, dict):
        dict_elem = ET.SubElement(parent, "dict")
        _dict_to_xml(value, dict_elem)
    elif isinstance(value, bool):
        if value:
            ET.SubElement(parent, "true")
        else:
            ET.SubElement(parent, "false")
    elif isinstance(value, int):
        int_elem = ET.SubElement(parent, "integer")
        int_elem.text = str(value)
    elif isinstance(value, float):
        real_elem = ET.SubElement(parent, "real")
        real_elem.text = str(value)
    else:
        # Default to string
        string_elem = ET.SubElement(parent, "string")
        string_elem.text = str(value)


def _write_formatted_xml(tree: ET.ElementTree, file_path: str) -> None:
    """
    Write XML tree to file with proper formatting and DOCTYPE.
    
    Args:
        tree: ElementTree to write
        file_path: Path to write to
    """
    # First, format the XML
    _indent_xml(tree.getroot())
    
    # Write to file with DOCTYPE
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n')
        
        # Write the rest of the XML
        xml_str = ET.tostring(tree.getroot(), encoding='unicode')
        f.write(xml_str)
        f.write('\n')


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """
    Add proper indentation to XML elements for pretty printing.
    
    Args:
        elem: Element to indent
        level: Current indentation level
    """
    indent = "\n" + level * "\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "\t"
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def extract_translatable_strings(content: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract translatable strings from .stringsdict content.
    This flattens the nested structure to get just the translatable text values.
    
    Args:
        content: Parsed .stringsdict content
        
    Returns:
        Flat dictionary of translatable strings with dot-notation keys
    """
    result = {}
    
    def _extract_from_dict(data: Dict[str, Any], prefix: str = "") -> None:
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Check if this is a plural rule dict (contains NSStringFormatSpecTypeKey)
                if "NSStringFormatSpecTypeKey" in value and value.get("NSStringFormatSpecTypeKey") == "NSStringPluralRuleType":
                    # Extract plural forms (zero, one, two, few, many, other)
                    plural_forms = ["zero", "one", "two", "few", "many", "other"]
                    for form in plural_forms:
                        if form in value and isinstance(value[form], str):
                            result[f"{current_key}.{form}"] = value[form]
                else:
                    # Recursively process nested dicts
                    _extract_from_dict(value, current_key)
            elif isinstance(value, str):
                # Skip format keys and other metadata
                if not key.startswith("NSString"):
                    result[current_key] = value
    
    _extract_from_dict(content)
    return result


def update_translatable_strings(content: Dict[str, Any], translations: Dict[str, str]) -> Dict[str, Any]:
    """
    Update .stringsdict content with new translations.
    
    Args:
        content: Original .stringsdict content
        translations: New translations with dot-notation keys
        
    Returns:
        Updated content
    """
    import copy
    result = copy.deepcopy(content)
    
    def _update_dict(data: Dict[str, Any], prefix: str = "") -> None:
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Check if this is a plural rule dict
                if "NSStringFormatSpecTypeKey" in value and value.get("NSStringFormatSpecTypeKey") == "NSStringPluralRuleType":
                    # Update plural forms
                    plural_forms = ["zero", "one", "two", "few", "many", "other"]
                    for form in plural_forms:
                        form_key = f"{current_key}.{form}"
                        if form_key in translations:
                            data[key][form] = translations[form_key]
                else:
                    # Recursively process nested dicts
                    _update_dict(value, current_key)
            elif isinstance(value, str):
                # Update direct string values
                if current_key in translations and not key.startswith("NSString"):
                    data[key] = translations[current_key]
    
    _update_dict(result)
    return result 