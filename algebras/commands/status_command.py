"""
Check the status of your translations
"""

import os
import click
import requests
from typing import Optional, Dict, List, Set, Tuple

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.lang_validator import read_language_file, extract_all_keys, get_key_value


def validate_languages_with_api(languages: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate language codes using the Algebras AI API.
    
    Args:
        languages: List of language codes to validate
        
    Returns:
        Tuple of (valid_languages, invalid_languages)
    """
    api_key = os.environ.get("ALGEBRAS_API_KEY")
    if not api_key:
        click.echo(click.style("Warning: ALGEBRAS_API_KEY not found. Skipping language validation.", fg='yellow'))
        return languages, []
    
    try:
        url = "https://platform.algebras.ai/api/v1/translation/languages"
        headers = {
            "accept": "application/json",
            "X-Api-Key": api_key
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            api_languages = response.json()
            # Extract language codes from API response
            if isinstance(api_languages, dict) and "data" in api_languages:
                valid_codes = set(api_languages["data"])
            elif isinstance(api_languages, list):
                valid_codes = set(api_languages)
            else:
                # If we can't parse the response, assume all languages are valid
                click.echo(click.style("Warning: Could not parse language validation response.", fg='yellow'))
                return languages, []
            
            valid_languages = [lang for lang in languages if lang in valid_codes]
            invalid_languages = [lang for lang in languages if lang not in valid_codes]
            
            return valid_languages, invalid_languages
        else:
            click.echo(click.style(f"Warning: Language validation API returned {response.status_code}. Continuing without validation.", fg='yellow'))
            return languages, []
            
    except Exception as e:
        click.echo(click.style(f"Warning: Failed to validate languages via API: {str(e)}. Continuing without validation.", fg='yellow'))
        return languages, []


def count_translated_keys(file_path: str) -> Tuple[int, int]:
    """
    Count translated keys (non-empty values) in a translation file.
    
    Args:
        file_path: Path to the translation file
        
    Returns:
        Tuple of (translated_keys_count, total_keys_count)
    """
    try:
        if not os.path.exists(file_path):
            return 0, 0
            
        data = read_language_file(file_path)
        
        # Handle flat dictionary formats (.po, .xml, .strings, .stringsdict) 
        # These formats return flat key-value dictionaries rather than nested structures
        if file_path.endswith(('.po', '.xml', '.strings', '.stringsdict')):
            total_keys = len(data)
            translated_count = 0
            for key, value in data.items():
                # Count as translated if value is not None, not empty string, and not just whitespace
                if value is not None and str(value).strip():
                    translated_count += 1
            return translated_count, total_keys
        else:
            # Handle nested formats (JSON, YAML, TS)
            all_keys = extract_all_keys(data)
            translated_count = 0
            for key in all_keys:
                value = get_key_value(data, key)
                # Count as translated if value is not None, not empty string, and not just whitespace
                if value is not None and str(value).strip():
                    translated_count += 1
            return translated_count, len(all_keys)
        
    except Exception as e:
        click.echo(click.style(f"Warning: Could not parse file {file_path}: {str(e)}", fg='yellow'))
        return 0, 0


def execute(language: Optional[str] = None) -> None:
    """
    Check the status of your translations.
    
    Args:
        language: Language to check (if None, check all languages)
    """
    config = Config()
    
    if not config.exists():
        click.echo(click.style("No Algebras configuration found. Run 'algebras init' first.", fg='red'))
        return
    
    # Load configuration
    config.load()
    
    # Get languages
    all_languages = config.get_languages()
    
    # Validate languages with API
    valid_languages, invalid_languages = validate_languages_with_api(all_languages)
    
    # Show warnings for invalid language codes
    if invalid_languages:
        click.echo(click.style(f"Warning: Invalid language codes detected: {', '.join(invalid_languages)}", fg='yellow'))
        click.echo(click.style("These may not be supported by the translation service.", fg='yellow'))
    
    # Filter languages if specified
    if language:
        if language not in all_languages:
            click.echo(click.style(f"Language '{language}' is not configured in your project.", fg='red'))
            return
        languages = [language]
    else:
        languages = all_languages
    
    # Get source language
    source_language = config.get_source_language()
    
    # Scan for files
    try:
        scanner = FileScanner()
        files_by_language = scanner.group_files_by_language()
        
        # Get source files
        source_files = files_by_language.get(source_language, [])
        if not source_files:
            click.echo(click.style(f"No source files found for language '{source_language}'.", fg='yellow'))
            return
        
        # Print status header
        click.echo(f"\n{click.style('Translation Status', fg='blue')}")
        click.echo(click.style('=' * 80, fg='blue'))
        click.echo(f"Source language: {source_language} ({len(source_files)} files)")
        click.echo(f"Source files: {source_files}")
        click.echo(click.style('-' * 80, fg='blue'))
        
        # Calculate expected file count for each language
        expected_file_counts = {lang: len(source_files) for lang in languages}
        
        # Count source keys for comparison
        source_key_counts = {}
        total_source_keys = 0
        for source_file in source_files:
            try:
                total_keys, key_count = count_translated_keys(source_file)
                source_key_counts[source_file] = key_count
                total_source_keys += key_count
            except Exception as e:
                click.echo(click.style(f"Warning: Could not count keys in source file {source_file}: {str(e)}", fg='yellow'))
                source_key_counts[source_file] = 0
        
        # Print status for each language
        for lang in languages:
            if lang == source_language:
                continue
            
            lang_files = files_by_language.get(lang, [])
            file_count = len(lang_files)
            
            # Calculate file percentage
            if expected_file_counts[lang] > 0:
                file_percentage = (file_count / expected_file_counts[lang]) * 100
            else:
                file_percentage = 0
            
            # Count translated keys
            total_translated_keys = 0
            total_expected_keys = 0
            
            for lang_file in lang_files:
                # Find corresponding source file to get expected key count
                source_file = None
                lang_basename = os.path.basename(lang_file)
                lang_dirname = os.path.dirname(lang_file)
                
                # Remove language suffix to find base filename
                if "." in lang_basename:
                    name_parts = lang_basename.split(".")
                    ext = name_parts.pop()
                    base = ".".join(name_parts)
                    
                    # Replace language marker with source language marker
                    if f".{lang}" in base:
                        base_source = base.replace(f".{lang}", f".{source_language}")
                    elif f"-{lang}" in base:
                        base_source = base.replace(f"-{lang}", f"-{source_language}")
                    elif f"_{lang}" in base:
                        base_source = base.replace(f"_{lang}", f"_{source_language}")
                    else:
                        # Remove language suffix
                        base_source = base.replace(f".{lang}", "")
                    
                    source_basename = f"{base_source}.{ext}"
                else:
                    source_basename = lang_basename.replace(f".{lang}", "")
                
                potential_source_file = os.path.join(lang_dirname, source_basename)
                if not potential_source_file in source_files:
                    source_file = potential_source_file
                    expected_keys = source_key_counts.get(source_file, 0)
                    total_expected_keys += expected_keys
                    
                    # Count translated keys in target file
                    translated_keys, _ = count_translated_keys(lang_file)
                    total_translated_keys += translated_keys
            
            # Use total source keys if we couldn't match files properly
            if total_expected_keys == 0:
                total_expected_keys = total_source_keys
            
            # Calculate key percentage
            if total_expected_keys > 0:
                key_percentage = (total_translated_keys / total_expected_keys) * 100
            else:
                key_percentage = 0
            
            # Set color based on key completion percentage (prioritize keys over files)
            if key_percentage >= 90:
                color = 'green'
            elif key_percentage >= 50:
                color = 'yellow'
            else:
                color = 'red'
            
            # Print status with both key and file counts
            click.echo(f"{lang}: {click.style(f'{total_translated_keys}/{total_expected_keys} keys ({key_percentage:.1f}%) in {file_count}/{expected_file_counts[lang]} files ({file_percentage:.1f}%)', fg=color)}")
            
            # Check for outdated files
            outdated_count = 0
            for lang_file in lang_files:
                # Find corresponding source file
                source_file = None
                lang_basename = os.path.basename(lang_file)
                lang_dirname = os.path.dirname(lang_file)
                
                # Remove language suffix to find base filename
                if "." in lang_basename:
                    name_parts = lang_basename.split(".")
                    ext = name_parts.pop()
                    base = ".".join(name_parts)
                    
                    # Replace language marker with source language marker
                    if f".{lang}" in base:
                        base_source = base.replace(f".{lang}", f".{source_language}")
                    elif f"-{lang}" in base:
                        base_source = base.replace(f"-{lang}", f"-{source_language}")
                    elif f"_{lang}" in base:
                        base_source = base.replace(f"_{lang}", f"_{source_language}")
                    else:
                        # Remove language suffix
                        base_source = base.replace(f".{lang}", "")
                    
                    source_basename = f"{base_source}.{ext}"
                else:
                    source_basename = lang_basename.replace(f".{lang}", "")
                
                potential_source_file = os.path.join(lang_dirname, source_basename)
                
                if potential_source_file in source_files:
                    source_file = potential_source_file
                    
                    # Check if file is outdated
                    source_mtime = os.path.getmtime(source_file)
                    lang_mtime = os.path.getmtime(lang_file)
                    
                    if lang_mtime < source_mtime:
                        outdated_count += 1
            
            # Print outdated file count
            if outdated_count > 0:
                click.echo(f"  {click.style(f'Warning: {outdated_count} files are outdated', fg='yellow')}")
        
        click.echo(click.style('-' * 80, fg='blue'))
        
        # Print summary
        if len(languages) > 1:
            click.echo(f"\n{click.style('Summary:', fg='green')}")
            click.echo(f"- To add a new language: {click.style('algebras add <language>', fg='blue')}")
            click.echo(f"- To translate your application: {click.style('algebras translate', fg='blue')}")
            click.echo(f"- To update outdated translations: {click.style('algebras update', fg='blue')}")
            click.echo(f"- To review translations: {click.style('algebras review', fg='blue')}")
    
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg='red')) 