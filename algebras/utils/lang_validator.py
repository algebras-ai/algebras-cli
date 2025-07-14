import os
import json
import yaml
from typing import Dict, Any, Set, List, Tuple
from tqdm import tqdm
from datetime import datetime
from algebras.utils.git_utils import (
    is_git_available, 
    is_git_repository, 
    get_key_last_modification, 
    compare_key_modifications,
    get_keys_last_modifications_batch
)
from algebras.utils.ts_handler import read_ts_translation_file
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.ios_strings_handler import read_ios_strings_file
from algebras.utils.ios_stringsdict_handler import read_ios_stringsdict_file, extract_translatable_strings
from algebras.utils.po_handler import read_po_file


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
    elif file_path.endswith('.ts'):
        return read_ts_translation_file(file_path)
    elif file_path.endswith('.xml'):
        return read_android_xml_file(file_path)
    elif file_path.endswith('.strings'):
        return read_ios_strings_file(file_path)
    elif file_path.endswith('.stringsdict'):
        # For .stringsdict files, extract translatable strings to get a flat dictionary
        content = read_ios_stringsdict_file(file_path)
        return extract_translatable_strings(content)
    elif file_path.endswith('.po'):
        return read_po_file(file_path)
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


def get_key_value(data: Dict[str, Any], key: str) -> Any:
    """
    Get the value of a key from a nested dictionary.
    
    Args:
        data: Dictionary to get value from
        key: Key to get value for (can be nested using dot notation)
        
    Returns:
        Value of the key or None if key doesn't exist
    """
    parts = key.split('.')
    current = data
    
    for part in parts:
        if part not in current:
            return None
        current = current[part]
        
    return current


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


def find_outdated_keys(source_file: str, target_file: str) -> Tuple[bool, Set[str]]:
    """
    Find keys that exist in both source and target files but might be outdated.
    This checks if the value is different and if the source key was modified more recently than the target.
    
    Args:
        source_file: Path to the source language file
        target_file: Path to the target language file
        
    Returns:
        Tuple of (has_outdated_keys, outdated_keys)
    """
    try:
        # Check if git is available
        if not is_git_available() or not is_git_repository(source_file):
            # Skip git-based validation if not available
            return False, set()
            
        source_data = read_language_file(source_file)
        target_data = read_language_file(target_file)
        
        source_keys = extract_all_keys(source_data)
        target_keys = extract_all_keys(target_data)
        
        # Get keys that exist in both files
        common_keys = source_keys.intersection(target_keys)
        
        # Filter keys that have different values first (potential candidates for being outdated)
        different_value_keys = []
        for key in common_keys:
            source_value = get_key_value(source_data, key)
            target_value = get_key_value(target_data, key)
            
            # Only consider keys with different values
            if source_value != target_value:
                different_value_keys.append(key)
        
        # If there are no keys with different values, we're done
        if not different_value_keys:
            return False, set()
        
        outdated_keys = set()
        
        # Use batch git operations for O(1) performance - single operation for all keys
        print(f"Checking {len(different_value_keys)} keys for outdated status...")
        
        # Get last modification dates for all keys in a single batch operation
        source_dates = get_keys_last_modifications_batch(source_file, different_value_keys)
        target_dates = get_keys_last_modifications_batch(target_file, different_value_keys)
        
        # Compare the dates for each key - this is O(n) but very fast since it's just dict lookups
        for key in different_value_keys:
            source_date = source_dates.get(key)
            target_date = target_dates.get(key)
            
            # If both dates are available, compare them
            if source_date and target_date:
                # Parse dates for comparison
                try:
                    # Handle different date formats that might come from git
                    source_dt = datetime.fromisoformat(source_date.replace('Z', '+00:00'))
                    target_dt = datetime.fromisoformat(target_date.replace('Z', '+00:00'))
                    
                    if source_dt > target_dt:
                        outdated_keys.add(key)
                except (ValueError, AttributeError):
                    # If date parsing fails, skip this key rather than falling back to slow operations
                    continue
            # If either date is missing, we can't determine if it's outdated
            # Skip rather than falling back to slow serial processing
                    
        return len(outdated_keys) > 0, outdated_keys
    except Exception as e:
        print(f"Error finding outdated keys: {str(e)}")
        return False, set()


def map_language_code(lang_code: str) -> str:
    """
    Map a language code to its ISO 2-letter format.
    For example: 'pt-BR' -> 'pt', 'en-US' -> 'en'
    
    Args:
        lang_code: Language code to map
        
    Returns:
        ISO 2-letter language code
    """
    # If the code is already 2 letters, return it as is
    if len(lang_code) == 2:
        return lang_code.lower()
    
    # Split by common separators and take the first part
    for separator in ['-', '_']:
        if separator in lang_code:
            return lang_code.split(separator)[0].lower()
    
    # If no separator found, return the first two characters
    return lang_code[:2].lower() 