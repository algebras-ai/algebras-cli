"""
Translation file manager for creating and updating translation files
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

from algebras.utils.ts_handler import read_ts_translation_file, write_ts_translation_file


def detect_translation_file_format(file_path: str) -> str:
    """
    Detect the format of a translation file based on extension.
    
    Args:
        file_path: Path to the translation file
        
    Returns:
        Format name: 'json', 'ts', 'yaml', or 'yml'
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.json':
        return 'json'
    elif ext == '.ts':
        return 'ts'
    elif ext in ['.yaml', '.yml']:
        return 'yaml'
    else:
        return 'json'  # Default to JSON


def read_translation_file(file_path: str) -> Dict[str, Any]:
    """
    Read a translation file in any supported format.
    
    Args:
        file_path: Path to the translation file
        
    Returns:
        Dictionary containing translation content
    """
    if not os.path.exists(file_path):
        return {}
    
    format_type = detect_translation_file_format(file_path)
    
    if format_type == 'json':
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    elif format_type == 'ts':
        return read_ts_translation_file(file_path)
    elif format_type == 'yaml':
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    else:
        raise ValueError(f"Unsupported translation file format: {format_type}")


def write_translation_file(file_path: str, content: Dict[str, Any], format_type: Optional[str] = None) -> None:
    """
    Write a translation file in the appropriate format.
    
    Args:
        file_path: Path to the translation file
        content: Dictionary containing translation content
        format_type: Format type ('json', 'ts', 'yaml'). If None, auto-detect from extension.
    """
    if format_type is None:
        format_type = detect_translation_file_format(file_path)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    if format_type == 'json':
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
    elif format_type == 'ts':
        # Extract export name from file path or use default
        export_name = os.path.splitext(os.path.basename(file_path))[0]
        write_ts_translation_file(file_path, content, export_name)
    elif format_type == 'yaml':
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(content, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    else:
        raise ValueError(f"Unsupported translation file format: {format_type}")


def merge_translations(existing: Dict[str, Any], new_keys: Dict[str, str]) -> Dict[str, Any]:
    """
    Merge new translation keys into existing translations.
    
    Args:
        existing: Existing translation dictionary
        new_keys: New keys to add (flat dictionary: key -> value)
        
    Returns:
        Merged dictionary
    """
    result = existing.copy() if existing else {}
    
    for key, value in new_keys.items():
        # Handle nested keys (e.g., "common.welcome")
        if '.' in key:
            parts = key.split('.')
            current = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    # Conflict: key exists but is not a dict, convert to dict
                    current[part] = {'_value': current[part]}
                current = current[part]
            # Set the final value
            final_key = parts[-1]
            if final_key not in current or current[final_key] == value:
                current[final_key] = value
        else:
            # Flat key
            if key not in result or result[key] == value:
                result[key] = value
    
    return result


def get_translation_file_path(output_path: Optional[str], source_language: str = 'en', 
                              project_root: str = None) -> str:
    """
    Determine the translation file path.
    
    Args:
        output_path: User-specified output path (may contain placeholders)
        source_language: Source language code
        project_root: Project root directory
        
    Returns:
        Resolved translation file path
    """
    if project_root is None:
        project_root = os.getcwd()
    
    if output_path:
        # Replace placeholders
        path = output_path.replace('%algebras_locale_code%', source_language)
        path = path.replace('%lang%', source_language)
        
        # If relative, make it relative to project root
        if not os.path.isabs(path):
            path = os.path.join(project_root, path)
        
        return path
    
    # Default: try to find existing translation files
    common_paths = [
        'messages',
        'locales',
        'i18n',
        'translations',
        'src/locales',
        'src/messages',
        'src/i18n',
        'app/locales',
        'app/messages',
        'public/locales'
    ]
    
    for base_path in common_paths:
        full_path = os.path.join(project_root, base_path)
        if os.path.exists(full_path):
            # Check for JSON files
            json_file = os.path.join(full_path, f"{source_language}.json")
            if os.path.exists(json_file):
                return json_file
            # Check for TS files
            ts_file = os.path.join(full_path, f"{source_language}.ts")
            if os.path.exists(ts_file):
                return ts_file
    
    # Default: create messages/en.json
    default_path = os.path.join(project_root, 'messages', f"{source_language}.json")
    return default_path

