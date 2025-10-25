"""
CSV translation file handler for multi-language translations
"""

import csv
import os
from typing import Dict, Any, List, Optional, Tuple


def read_csv_file(file_path: str) -> Dict[str, Any]:
    """
    Read a CSV translation file and return its content as a dictionary.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        Dictionary containing the CSV file content with language columns
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is not valid CSV format
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except UnicodeDecodeError:
        # Try with latin-1 encoding
        with open(file_path, 'r', encoding='latin-1') as f:
            reader = csv.reader(f)
            rows = list(reader)
    
    if not rows:
        raise ValueError(f"CSV file {file_path} is empty")
    
    # First row should be headers
    headers = rows[0]
    if len(headers) < 2:
        raise ValueError(f"CSV file {file_path} must have at least 2 columns (key and at least one language)")
    
    # First column is the key, rest are language codes
    key_column = headers[0]
    language_columns = headers[1:]
    
    # Validate language codes
    for lang in language_columns:
        if not lang or not lang.strip():
            raise ValueError(f"Empty language code found in header: {headers}")
    
    # Parse data rows
    translations = {}
    for row_num, row in enumerate(rows[1:], start=2):
        if not row:  # Skip empty rows
            continue
        
        if len(row) != len(headers):
            continue  # Skip malformed rows
        
        key = row[0].strip()
        if not key:
            continue  # Skip rows without keys
        
        # Create language translations
        lang_translations = {}
        for i, lang in enumerate(language_columns):
            value = row[i + 1].strip() if i + 1 < len(row) else ""
            if value:  # Only include non-empty translations
                lang_translations[lang] = value
        
        if lang_translations:  # Only include keys with at least one translation
            translations[key] = lang_translations
    
    return {
        'key_column': key_column,
        'languages': language_columns,
        'translations': translations
    }


def write_csv_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write content to a CSV translation file.
    
    Args:
        file_path: Path where to write the CSV file
        content: Dictionary containing the CSV content
        
    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("CSV content must be a dictionary")
    
    if 'translations' not in content or 'languages' not in content:
        raise ValueError("CSV content must contain 'translations' and 'languages' keys")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    key_column = content.get('key_column', 'key')
    languages = content['languages']
    translations = content['translations']
    
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow([key_column] + languages)
        
        # Write data rows
        for key, lang_translations in translations.items():
            if isinstance(lang_translations, dict):
                row = [key]
                for lang in languages:
                    row.append(lang_translations.get(lang, ""))
                writer.writerow(row)


def extract_translatable_strings(csv_content: Dict[str, Any], 
                               target_language: str) -> Dict[str, str]:
    """
    Extract translatable strings from CSV content for a specific language.
    
    Args:
        csv_content: CSV file content as dictionary
        target_language: Target language code
        
    Returns:
        Dictionary of key-value pairs for translatable strings
    """
    if 'translations' not in csv_content:
        return {}
    
    translatable = {}
    translations = csv_content['translations']
    
    for key, lang_translations in translations.items():
        if isinstance(lang_translations, dict) and target_language in lang_translations:
            translatable[key] = lang_translations[target_language]
    
    return translatable


def create_csv_from_translations(translations: Dict[str, str], 
                               languages: List[str],
                               key_column: str = "key") -> Dict[str, Any]:
    """
    Create CSV content from translations.
    
    Args:
        translations: Dictionary of key-value translation pairs
        languages: List of language codes
        key_column: Name of the key column
        
    Returns:
        CSV content dictionary
    """
    # For single language translations, we need to create a structure
    # that can be extended with more languages
    csv_translations = {}
    
    for key, value in translations.items():
        # Create a single-language translation structure
        lang_translations = {languages[0]: value} if languages else {}
        csv_translations[key] = lang_translations
    
    return {
        'key_column': key_column,
        'languages': languages,
        'translations': csv_translations
    }


def add_language_to_csv(csv_content: Dict[str, Any], 
                       language: str, 
                       translations: Dict[str, str]) -> Dict[str, Any]:
    """
    Add a new language to existing CSV content.
    
    Args:
        csv_content: Existing CSV content
        language: New language code to add
        translations: Translations for the new language
        
    Returns:
        Updated CSV content dictionary
    """
    if 'translations' not in csv_content:
        csv_content['translations'] = {}
    
    if language not in csv_content['languages']:
        csv_content['languages'].append(language)
    
    for key, value in translations.items():
        if key not in csv_content['translations']:
            csv_content['translations'][key] = {}
        csv_content['translations'][key][language] = value
    
    return csv_content


def get_csv_language_codes(csv_content: Dict[str, Any]) -> List[str]:
    """
    Get all language codes from CSV content.
    
    Args:
        csv_content: CSV file content as dictionary
        
    Returns:
        List of language codes
    """
    return csv_content.get('languages', [])


def is_valid_csv_file(file_path: str) -> bool:
    """
    Check if a file is a valid CSV translation file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file is a valid CSV file, False otherwise
    """
    try:
        content = read_csv_file(file_path)
        return 'translations' in content and 'languages' in content
    except (FileNotFoundError, ValueError, UnicodeDecodeError):
        return False


def get_csv_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from CSV file path.
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        Language code if found, None otherwise
    """
    # For CSV files, we typically don't extract language from filename
    # since they contain multiple languages. Return None to indicate
    # this is a multi-language file.
    return None


def is_glossary_csv(file_path: str) -> bool:
    """
    Check if a CSV file is a glossary file (vs translation file).
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        True if the file appears to be a glossary file, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            
            # Glossary files typically have "Record ID" as first column
            # Translation files typically have "key" as first column
            if headers and len(headers) > 0:
                first_header = headers[0].lower().strip()
                return first_header in ['record id', 'record_id', 'id']
    except (FileNotFoundError, UnicodeDecodeError, StopIteration):
        pass
    
    return False
