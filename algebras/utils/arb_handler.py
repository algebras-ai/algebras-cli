"""
Flutter ARB (Application Resource Bundle) file handler
"""

import json
import os
from typing import Dict, Any, List, Optional


def read_arb_file(file_path: str) -> Dict[str, Any]:
    """
    Read a Flutter ARB file and return its content as a dictionary.
    
    Args:
        file_path: Path to the ARB file
        
    Returns:
        Dictionary containing the ARB file content
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is not valid JSON or ARB format
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"ARB file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ARB file {file_path}: {str(e)}")
    
    if not isinstance(content, dict):
        raise ValueError(f"ARB file {file_path} must contain a JSON object")
    
    return content


def write_arb_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write content to a Flutter ARB file.
    
    Args:
        file_path: Path where to write the ARB file
        content: Dictionary containing the ARB content
        
    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("ARB content must be a dictionary")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2, sort_keys=True)


def extract_translatable_strings(arb_content: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract translatable strings from ARB content, filtering out metadata.
    
    Args:
        arb_content: ARB file content as dictionary
        
    Returns:
        Dictionary of key-value pairs for translatable strings only
    """
    translatable = {}
    
    for key, value in arb_content.items():
        # Skip metadata keys (prefixed with @)
        if key.startswith('@'):
            continue
        
        # Only include string values
        if isinstance(value, str):
            translatable[key] = value
    
    return translatable


def create_arb_from_translations(translations: Dict[str, str], 
                                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create ARB content from translations and optional metadata.
    
    Args:
        translations: Dictionary of key-value translation pairs
        metadata: Optional metadata dictionary (keys prefixed with @)
        
    Returns:
        ARB content dictionary
    """
    arb_content = {}
    
    # Add metadata first if provided
    if metadata:
        for key, value in metadata.items():
            if not key.startswith('@'):
                key = f"@{key}"
            arb_content[key] = value
    
    # Add translations
    arb_content.update(translations)
    
    return arb_content


def get_arb_metadata(arb_content: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from ARB content.
    
    Args:
        arb_content: ARB file content as dictionary
        
    Returns:
        Dictionary containing only metadata keys (prefixed with @)
    """
    metadata = {}
    
    for key, value in arb_content.items():
        if key.startswith('@'):
            metadata[key] = value
    
    return metadata


def is_valid_arb_file(file_path: str) -> bool:
    """
    Check if a file is a valid ARB file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file is a valid ARB file, False otherwise
    """
    try:
        content = read_arb_file(file_path)
        return isinstance(content, dict)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return False


def get_arb_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from ARB file path or content.
    
    Args:
        file_path: Path to the ARB file
        
    Returns:
        Language code if found, None otherwise
    """
    # Try to extract from filename (e.g., app_en.arb -> en, app_en_US.arb -> en_US)
    filename = os.path.basename(file_path)
    if '_' in filename:
        parts = filename.split('_')
        if len(parts) >= 3:
            # Check if the last two parts form a valid locale (e.g., en_US)
            last_two = '_'.join(parts[-2:]).split('.')[0]
            if len(last_two) == 5 and '_' in last_two:  # en_US format
                return last_two
        elif len(parts) >= 2:
            # Get the part before .arb
            name_part = parts[-1].split('.')[0]
            if len(name_part) == 2:  # en, de, etc.
                return name_part
    
    # Try to extract from @locale metadata
    try:
        content = read_arb_file(file_path)
        # Check for @locale metadata object first (higher priority)
        locale_metadata = content.get('@locale')
        if isinstance(locale_metadata, dict) and 'locale' in locale_metadata:
            return locale_metadata['locale']
        # Check for @@locale field (common in ARB files)
        locale_value = content.get('@@locale')
        if isinstance(locale_value, str):
            return locale_value
    except (ValueError, json.JSONDecodeError, FileNotFoundError):
        pass
    
    return None
