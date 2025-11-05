"""
String extractor for generating translation keys and extracting strings to files
"""

import os
import hashlib
import re
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path

from algebras.utils.translation_file_manager import (
    read_translation_file,
    write_translation_file,
    merge_translations,
    get_translation_file_path
)


def generate_key_from_content(text: str, prefix: str = '') -> str:
    """
    Generate a translation key from string content.
    
    Args:
        text: The original string
        prefix: Optional prefix for the key
        
    Returns:
        Generated translation key
    """
    # Normalize text: lowercase, remove special chars, replace spaces with underscores
    normalized = re.sub(r'[^\w\s]', '', text.lower())
    normalized = re.sub(r'\s+', '_', normalized.strip())
    normalized = normalized[:50]  # Limit length
    
    # Remove common words that might make keys too long
    words = normalized.split('_')
    # Keep only meaningful words (skip very short words)
    meaningful_words = [w for w in words if len(w) > 2][:4]  # Max 4 words
    key = '_'.join(meaningful_words) if meaningful_words else normalized[:20]
    
    # Add hash suffix for uniqueness if needed
    hash_suffix = hashlib.md5(text.encode()).hexdigest()[:6]
    key = f"{key}_{hash_suffix}"
    
    if prefix:
        key = f"{prefix}_{key}"
    
    return key


def generate_key_from_file_path(file_path: str, line_number: int, prefix: str = '') -> str:
    """
    Generate a translation key from file path and line number.
    
    Args:
        file_path: Path to the source file
        line_number: Line number where the string appears
        prefix: Optional prefix for the key
        
    Returns:
        Generated translation key
    """
    # Get file name without extension
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    # Normalize file name (remove special chars, convert to lowercase)
    file_name = re.sub(r'[^\w]', '_', file_name.lower())
    
    key = f"{file_name}_{line_number}"
    
    if prefix:
        key = f"{prefix}_{key}"
    
    return key


def generate_translation_key(file_path: str, line_number: int, text: str, 
                             strategy: str = 'file-based', prefix: str = '') -> str:
    """
    Generate a translation key based on the specified strategy.
    
    Args:
        file_path: Path to the source file
        line_number: Line number where the string appears
        text: The original string
        strategy: Key generation strategy ('file-based', 'content-based', 'semantic')
        prefix: Optional prefix for the key
        
    Returns:
        Generated translation key
    """
    if strategy == 'file-based':
        return generate_key_from_file_path(file_path, line_number, prefix)
    elif strategy == 'content-based':
        return generate_key_from_content(text, prefix)
    elif strategy == 'semantic':
        # Try to extract semantic meaning from text
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = re.sub(r'\s+', '_', normalized.strip())
        # Take first few meaningful words
        words = [w for w in normalized.split('_') if len(w) > 2][:3]
        key = '_'.join(words) if words else normalized[:20]
        if prefix:
            key = f"{prefix}_{key}"
        return key
    else:
        # Default to file-based
        return generate_key_from_file_path(file_path, line_number, prefix)


def extract_strings_to_file(
    issues: Dict[str, List[Dict[str, Any]]],
    output_path: Optional[str] = None,
    source_language: str = 'en',
    key_prefix: str = '',
    key_strategy: str = 'file-based',
    project_root: str = None,
    dry_run: bool = False
) -> Tuple[Dict[Tuple[str, int, str], str], str]:
    """
    Extract hardcoded strings to a translation file.
    
    Args:
        issues: Dictionary mapping file paths to lists of issues
               Each issue has 'text' and 'line' keys
        output_path: Path to translation file (optional, will auto-detect if not provided)
        source_language: Source language code
        key_prefix: Prefix for generated keys
        key_strategy: Key generation strategy ('file-based', 'content-based', 'semantic')
        project_root: Project root directory
        dry_run: If True, don't write files, just return the mapping
        
    Returns:
        Tuple of (key_mapping, translation_file_path)
        key_mapping: Dictionary mapping (file_path, line_number, text) -> translation_key
        translation_file_path: Path to the translation file
    """
    if project_root is None:
        project_root = os.getcwd()
    
    # Determine translation file path
    translation_file_path = get_translation_file_path(output_path, source_language, project_root)
    
    # Read existing translations
    existing_translations = read_translation_file(translation_file_path)
    
    # Generate keys for all strings
    key_mapping = {}
    new_keys = {}
    used_keys = set(existing_translations.keys() if isinstance(existing_translations, dict) else [])
    
    for file_path, file_issues in issues.items():
        for issue in file_issues:
            text = issue.get('text', '')
            line = issue.get('line', 0)
            
            if not text:
                continue
            
            # Generate key
            key = generate_translation_key(file_path, line, text, key_strategy, key_prefix)
            
            # Ensure uniqueness
            original_key = key
            counter = 1
            while key in used_keys:
                # Check if existing key has the same value
                if isinstance(existing_translations, dict) and existing_translations.get(key) == text:
                    # Same content, reuse the key
                    break
                # Different content, generate new key
                key = f"{original_key}_{counter}"
                counter += 1
            
            used_keys.add(key)
            
            # Store mapping
            key_mapping[(file_path, line, text)] = key
            new_keys[key] = text
    
    # Merge with existing translations
    merged_translations = merge_translations(existing_translations, new_keys)
    
    # Write translation file
    if not dry_run:
        write_translation_file(translation_file_path, merged_translations)
    
    return key_mapping, translation_file_path

