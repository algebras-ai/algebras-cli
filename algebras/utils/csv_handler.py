"""
CSV translation file handler for multi-language translations
"""

import csv
import os
import re
import warnings
from typing import Dict, Any, List, Optional, Tuple, Set


def _get_delimiter(file_path: str) -> str:
    """
    Get the delimiter for CSV/TSV files based on file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Delimiter character (',' for CSV, '\t' for TSV)
    """
    if file_path.lower().endswith('.tsv'):
        return '\t'
    return ','


def _match_language_to_column(column_name: str, language_code: str) -> bool:
    """
    Check if a column name matches a language code.
    
    Supports both exact matches and fuzzy matching for column headers
    that contain language codes in parentheses, e.g., "Chinese (Simplified)(zh)".
    
    Args:
        column_name: The column header name (e.g., "Chinese (Simplified)(zh)")
        language_code: The language code to match (e.g., "zh")
        
    Returns:
        True if the column matches the language code, False otherwise
    """
    if not column_name or not language_code:
        return False
    
    # Exact match
    if column_name.strip() == language_code.strip():
        return True
    
    # Fuzzy match: look for language code in parentheses
    # Pattern: matches (language_code) at the end or anywhere in the string
    # Examples: "English(en)", "Chinese (Simplified)(zh)", "Chinese (Traditional)(zh_Hant)"
    pattern = r'\(([^)]+)\)'
    matches = re.findall(pattern, column_name)
    
    for match in matches:
        # Check if the matched code equals the language code
        if match.strip() == language_code.strip():
            return True
    
    return False


def _find_matching_column(language_columns: List[str], language_code: str) -> Optional[str]:
    """
    Find a column that matches the given language code.
    
    Args:
        language_columns: List of column header names
        language_code: The language code to find
        
    Returns:
        The matching column name if found, None otherwise
    """
    # First try exact match
    if language_code in language_columns:
        return language_code
    
    # Then try fuzzy match
    for column in language_columns:
        if _match_language_to_column(column, language_code):
            return column
    
    return None


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
    
    delimiter = _get_delimiter(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
    except UnicodeDecodeError:
        # Try with latin-1 encoding
        with open(file_path, 'r', encoding='latin-1') as f:
            reader = csv.reader(f, delimiter=delimiter)
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
            # Include all translations, even empty ones, so we can track which columns exist
            lang_translations[lang] = value
        
        # Include the key even if all translations are empty (so we know the key exists)
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
    
    # Validate that translations is actually a dict of translation keys, not the content dict itself
    if not isinstance(translations, dict):
        raise ValueError(f"CSV content 'translations' must be a dictionary, got {type(translations)}")
    
    # Additional safety check: ensure translations is not the entire content dict
    # (which would have keys like 'key_column', 'languages', 'translations')
    # Filter out metadata keys if they somehow got into translations
    metadata_keys = {'key_column', 'languages', 'translations'}
    if metadata_keys.intersection(translations.keys()):
        # Filter out metadata keys - they shouldn't be in translations
        translations = {k: v for k, v in translations.items() if k not in metadata_keys}
    
    delimiter = _get_delimiter(file_path)
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter=delimiter)
        
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
    
    Supports both exact column name matches and fuzzy matching for column headers
    that contain language codes in parentheses.
    
    Args:
        csv_content: CSV file content as dictionary
        target_language: Target language code (e.g., "zh" or "zh_Hant")
        
    Returns:
        Dictionary of key-value pairs for translatable strings (includes empty strings for missing translations)
    """
    if 'translations' not in csv_content:
        return {}
    
    # Get available language columns
    language_columns = csv_content.get('languages', [])
    
    # Find the matching column (exact or fuzzy match)
    matching_column = _find_matching_column(language_columns, target_language)
    
    if not matching_column:
        # No matching column found
        return {}
    
    translatable = {}
    translations = csv_content['translations']
    
    for key, lang_translations in translations.items():
        if isinstance(lang_translations, dict):
            # Get the value for the matching column, defaulting to empty string if not present
            value = lang_translations.get(matching_column, "")
            translatable[key] = value
    
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


def _normalize_key(key: str) -> str:
    """
    Normalize a key for matching purposes.
    
    Args:
        key: The key to normalize
        
    Returns:
        Normalized key (stripped of whitespace)
    """
    if not key:
        return ""
    return key.strip()


def write_csv_file_in_place(file_path: str, translations: Dict[str, str], 
                            target_language: str, keys_to_update: Optional[Set[str]] = None) -> None:
    """
    Update an existing CSV file in-place, preserving structure, formatting, and other language columns.
    
    Args:
        file_path: Path to the CSV file to update
        translations: Dictionary of key-value translation pairs to update
        target_language: Language code for the column to update
        keys_to_update: Optional set of keys to update. If None, all keys in translations will be updated.
    """
    if not os.path.exists(file_path):
        # If file doesn't exist, create new CSV file
        csv_content = create_csv_from_translations(translations, [target_language])
        write_csv_file(file_path, csv_content)
        return
    
    # Determine encoding by trying to read the file
    delimiter = _get_delimiter(file_path)
    encoding = 'utf-8'
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
    except UnicodeDecodeError:
        # Try with latin-1 encoding
        encoding = 'latin-1'
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)
    
    if not rows:
        # Empty file, create new
        csv_content = create_csv_from_translations(translations, [target_language])
        write_csv_file(file_path, csv_content)
        return
    
    # First row is headers
    headers = rows[0]
    if len(headers) < 2:
        raise ValueError(f"CSV file {file_path} must have at least 2 columns (key and at least one language)")
    
    key_column = headers[0]
    language_columns = headers[1:]
    
    # Check if target language column exists (exact or fuzzy match), add if needed
    language_index = None
    matching_column = _find_matching_column(language_columns, target_language)
    
    if matching_column:
        # Use existing column
        language_index = language_columns.index(matching_column) + 1  # +1 for key column
    else:
        # Add new language column
        language_columns.append(target_language)
        language_index = len(headers)  # New column index
        headers.append(target_language)
    
    # Create a map of normalized key to row index for quick lookup
    # Also track duplicate keys to warn about them
    key_to_row_index = {}
    duplicate_keys = []
    normalized_to_original = {}  # Map normalized key to original key for validation
    
    for i, row in enumerate(rows[1:], start=1):
        if not row or len(row) == 0:
            continue
        
        original_key = row[0] if len(row) > 0 else ""
        normalized_key = _normalize_key(original_key)
        
        if not normalized_key:
            continue
        
        # Check for duplicate keys
        if normalized_key in key_to_row_index:
            if normalized_key not in duplicate_keys:
                duplicate_keys.append(normalized_key)
                warnings.warn(
                    f"Duplicate key '{normalized_key}' found in CSV file {file_path} "
                    f"at rows {key_to_row_index[normalized_key]} and {i}. "
                    f"Only the last occurrence will be used.",
                    UserWarning
                )
        
        key_to_row_index[normalized_key] = i
        normalized_to_original[normalized_key] = original_key
    
    # Normalize translation keys and create a mapping
    normalized_translations = {}
    translation_key_mapping = {}  # Map normalized key back to original key in translations
    
    for original_key, value in translations.items():
        normalized_key = _normalize_key(original_key)
        if normalized_key:
            normalized_translations[normalized_key] = value
            translation_key_mapping[normalized_key] = original_key
    
    # Validate that translation keys match file keys
    unmatched_translation_keys = []
    for normalized_key in normalized_translations.keys():
        if normalized_key not in key_to_row_index:
            unmatched_translation_keys.append(translation_key_mapping.get(normalized_key, normalized_key))
    
    if unmatched_translation_keys:
        warnings.warn(
            f"Translation keys not found in CSV file {file_path}: {unmatched_translation_keys[:10]}{'...' if len(unmatched_translation_keys) > 10 else ''}. "
            f"These keys will be added as new rows.",
            UserWarning
        )
    
    # Update existing rows and track which keys we've updated
    updated_keys = set()
    skipped_keys = set()
    
    for normalized_key, value in normalized_translations.items():
        original_translation_key = translation_key_mapping.get(normalized_key, normalized_key)
        
        # Check if we should update this key
        if keys_to_update is not None:
            # Check both normalized and original key against keys_to_update
            if normalized_key not in keys_to_update and original_translation_key not in keys_to_update:
                skipped_keys.add(original_translation_key)
                continue
        
        if normalized_key in key_to_row_index:
            # Update existing row
            row_index = key_to_row_index[normalized_key]
            row = rows[row_index]
            
            # Validate that the key in the row matches (defensive check)
            row_key = _normalize_key(row[0] if len(row) > 0 else "")
            if row_key != normalized_key:
                warnings.warn(
                    f"Key mismatch at row {row_index} in {file_path}: "
                    f"expected '{normalized_key}', found '{row_key}'. Skipping update.",
                    UserWarning
                )
                continue
            
            # Ensure row has enough columns
            while len(row) <= language_index:
                row.append("")
            
            # Update the language column
            row[language_index] = value
            updated_keys.add(original_translation_key)
        else:
            # Add new row for this key
            new_row = [original_translation_key]  # Use original key from translations
            # Fill with empty values for all language columns
            for _ in language_columns:
                new_row.append("")
            # Set the target language value
            new_row[language_index] = value
            rows.append(new_row)
            updated_keys.add(original_translation_key)
    
    # Warn if keys_to_update was specified but some keys were skipped
    if keys_to_update and skipped_keys:
        warnings.warn(
            f"Skipped {len(skipped_keys)} translation keys not in keys_to_update set.",
            UserWarning
        )
    
    # Write back the updated CSV file
    os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
    
    with open(file_path, 'w', encoding=encoding, newline='') as f:
        writer = csv.writer(f, delimiter=delimiter)
        # Write header
        writer.writerow(headers)
        # Write all rows (preserving order)
        for row in rows[1:]:
            # Ensure row has correct number of columns
            while len(row) < len(headers):
                row.append("")
            # Trim row if it has too many columns (shouldn't happen, but be safe)
            if len(row) > len(headers):
                row = row[:len(headers)]
            writer.writerow(row)


def is_glossary_csv(file_path: str) -> bool:
    """
    Check if a CSV file is a glossary file (vs translation file).
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        True if the file appears to be a glossary file, False otherwise
    """
    delimiter = _get_delimiter(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            headers = next(reader)
            
            # Glossary files typically have "Record ID" as first column
            # Translation files typically have "key" as first column
            if headers and len(headers) > 0:
                first_header = headers[0].lower().strip()
                return first_header in ['record id', 'record_id', 'id']
    except (FileNotFoundError, UnicodeDecodeError, StopIteration):
        pass
    
    return False
