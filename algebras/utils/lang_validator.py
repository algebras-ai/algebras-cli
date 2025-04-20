import os
import json
import yaml
from typing import Dict, Any, Set, List, Tuple


def read_language_file(file_path: str) -> Dict[str, Any]:
    """
    Read a language file and return its contents as a dictionary.
    
    Args:
        file_path: Path to the language file
        
    Returns:
        Dictionary containing the file contents
    """
    if file_path.endswith('.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif file_path.endswith(('.yaml', '.yml')):
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def extract_all_keys(data: Dict[str, Any], prefix: str = '') -> Set[str]:
    """
    Extract all keys from a nested dictionary, including nested keys.
    
    Args:
        data: Dictionary to extract keys from
        prefix: Prefix for nested keys
        
    Returns:
        Set of all keys in the dictionary, including nested keys
    """
    keys = set()
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        keys.add(full_key)
        
        # Recursively extract keys from nested dictionaries
        if isinstance(value, dict):
            nested_keys = extract_all_keys(value, full_key)
            keys.update(nested_keys)
    
    return keys


def validate_language_files(source_file: str, target_file: str) -> Tuple[bool, Set[str]]:
    """
    Validate if a target language file contains all keys from the source language file.
    
    Args:
        source_file: Path to the source language file
        target_file: Path to the target language file
        
    Returns:
        Tuple of (is_valid, missing_keys)
    """
    try:
        source_data = read_language_file(source_file)
        target_data = read_language_file(target_file)
        
        source_keys = extract_all_keys(source_data)
        target_keys = extract_all_keys(target_data)
        
        missing_keys = source_keys - target_keys
        
        return len(missing_keys) == 0, missing_keys
    except Exception as e:
        print(f"Error validating language files: {str(e)}")
        return False, set() 