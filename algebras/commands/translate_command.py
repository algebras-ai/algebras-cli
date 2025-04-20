"""
Translate your application
"""

import os
import json
import yaml
import click
from colorama import Fore
from typing import Dict, Any, Optional, List, Tuple, Set

from algebras.config import Config
from algebras.services.translator import Translator
from algebras.services.file_scanner import FileScanner
from algebras.utils.path_utils import determine_target_path
from algebras.utils.lang_validator import validate_language_files, find_outdated_keys, extract_all_keys
from algebras.utils.git_utils import is_git_available, is_git_repository


def execute(language: Optional[str] = None, force: bool = False, only_missing: bool = False,
           outdated_files: List[Tuple[str, str]] = None, 
           missing_keys_files: List[Tuple[str, Set[str], str]] = None,
           outdated_keys_files: List[Tuple[str, Set[str], str]] = None) -> None:
    """
    Translate your application.
    
    Args:
        language: Language to translate (if None, translate all languages)
        force: Force translation even if files are up to date
        only_missing: Only translate keys that are missing in the target file
        outdated_files: List of tuples (target_file, source_file) that are outdated by modification time
        missing_keys_files: List of tuples (target_file, missing_keys, source_file)
        outdated_keys_files: List of tuples (target_file, outdated_keys, source_file)
    """
    config = Config()
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return
    
    # Load configuration
    config.load()
    
    # Get languages
    languages = config.get_languages()
    if len(languages) < 2:
        click.echo(f"{Fore.YELLOW}Only one language ({languages[0]}) is configured. Add more languages with 'algebras add <language>'.\x1b[0m")
        return
    
    # Filter languages if specified
    if language:
        if language not in languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.\x1b[0m")
            return
        target_languages = [language]
    else:
        # Skip the source language
        source_lang = config.get_source_language()
        target_languages = [lang for lang in languages if lang != source_lang]
    
    # Get source language
    source_language = config.get_source_language()
    
    # Initialize translator
    translator = Translator()
    
    # Initialize lists if they're None
    outdated_files = outdated_files or []
    missing_keys_files = missing_keys_files or []
    outdated_keys_files = outdated_keys_files or []
    
    # Check if we have specific files to update
    if outdated_files or missing_keys_files or outdated_keys_files:
        # Process the specific files that were passed in
        
        for target_lang in target_languages:
            # Process outdated files - find changed keys by comparing the content
            for target_file, source_file in outdated_files:
                click.echo(f"\n{Fore.BLUE}Processing outdated file {os.path.basename(target_file)} for language '{target_lang}'...{Fore.RESET}")
                
                try:
                    # Load both source and target files
                    if source_file.endswith(".json"):
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = json.load(f)
                        with open(target_file, "r", encoding="utf-8") as f:
                            target_content = json.load(f)
                    elif source_file.endswith((".yaml", ".yml")):
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = yaml.safe_load(f)
                        with open(target_file, "r", encoding="utf-8") as f:
                            target_content = yaml.safe_load(f)
                    
                    # Extract all keys from both files
                    source_keys = extract_all_keys(source_content)
                    target_keys = extract_all_keys(target_content)
                    
                    # Find keys that exist in both files - these are potentially outdated
                    common_keys = source_keys.intersection(target_keys)
                    
                    # Compare values to find potentially modified keys
                    modified_keys = []
                    for key in common_keys:
                        key_parts = key.split('.')
                        source_value = get_nested_value(source_content, key_parts)
                        target_value = get_nested_value(target_content, key_parts)
                        
                        # If values are different, consider this key outdated
                        if source_value != target_value and isinstance(source_value, str):
                            modified_keys.append(key)
                    
                    # Find keys only in source (missing keys)
                    missing_keys = source_keys - target_keys
                    
                    # Report what we found
                    if missing_keys:
                        click.echo(f"  {Fore.YELLOW}Found {len(missing_keys)} missing keys in {os.path.basename(target_file)}{Fore.RESET}")
                    
                    if modified_keys:
                        click.echo(f"  {Fore.YELLOW}Found {len(modified_keys)} potentially outdated keys in {os.path.basename(target_file)}{Fore.RESET}")
                        # Print up to 5 modified keys as examples
                        for key in modified_keys[:5]:
                            click.echo(f"    - {key}")
                        if len(modified_keys) > 5:
                            click.echo(f"    - ... and {len(modified_keys) - 5} more")
                    
                    # Translate missing keys
                    if missing_keys:
                        click.echo(f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys...{Fore.RESET}")
                        target_content = translator.translate_missing_keys(
                            source_content, 
                            target_content, 
                            list(missing_keys), 
                            target_lang
                        )
                    
                    # Translate modified keys
                    if modified_keys:
                        click.echo(f"  {Fore.GREEN}Translating {len(modified_keys)} outdated keys...{Fore.RESET}")
                        target_content = translator.translate_outdated_keys(
                            source_content,
                            target_content,
                            modified_keys,
                            target_lang
                        )
                    
                    # Save updated content if there were changes
                    if missing_keys or modified_keys:
                        if target_file.endswith(".json"):
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(target_content, f, ensure_ascii=False, indent=2)
                        elif target_file.endswith((".yaml", ".yml")):
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(target_content, f, default_flow_style=False, allow_unicode=True)
                        
                        updated_count = len(missing_keys) + len(modified_keys)
                        click.echo(f"  {Fore.GREEN}✓ Updated {updated_count} keys in {target_file}\x1b[0m")
                    else:
                        click.echo(f"  {Fore.GREEN}No keys need to be updated in {os.path.basename(target_file)}\x1b[0m")
                        
                except Exception as e:
                    click.echo(f"  {Fore.RED}Error processing outdated file {os.path.basename(target_file)}: {str(e)}\x1b[0m")
            
            # Process files with specific missing keys
            for target_file, missing_keys, source_file in missing_keys_files:
                if os.path.basename(target_file).startswith(target_lang):
                    click.echo(f"\n{Fore.BLUE}Processing file with missing keys {os.path.basename(target_file)}...{Fore.RESET}")
                    
                    try:
                        # Load both source and target files
                        if source_file.endswith(".json"):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = json.load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = json.load(f)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = yaml.safe_load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = yaml.safe_load(f)
                        
                        # Translate missing keys
                        if missing_keys:
                            click.echo(f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys...{Fore.RESET}")
                            target_content = translator.translate_missing_keys(
                                source_content, 
                                target_content, 
                                list(missing_keys), 
                                target_lang
                            )
                            
                            # Save updated content
                            if target_file.endswith(".json"):
                                with open(target_file, "w", encoding="utf-8") as f:
                                    json.dump(target_content, f, ensure_ascii=False, indent=2)
                            elif target_file.endswith((".yaml", ".yml")):
                                with open(target_file, "w", encoding="utf-8") as f:
                                    yaml.dump(target_content, f, default_flow_style=False, allow_unicode=True)
                            
                            click.echo(f"  {Fore.GREEN}✓ Updated {len(missing_keys)} keys in {target_file}\x1b[0m")
                    except Exception as e:
                        click.echo(f"  {Fore.RED}Error processing file with missing keys {os.path.basename(target_file)}: {str(e)}\x1b[0m")
            
            # Process files with outdated keys
            for target_file, outdated_keys, source_file in outdated_keys_files:
                if os.path.basename(target_file).startswith(target_lang):
                    click.echo(f"\n{Fore.BLUE}Processing file with outdated keys {os.path.basename(target_file)}...{Fore.RESET}")
                    
                    try:
                        # Load both source and target files
                        if source_file.endswith(".json"):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = json.load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = json.load(f)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = yaml.safe_load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = yaml.safe_load(f)
                        
                        # Translate outdated keys
                        if outdated_keys:
                            click.echo(f"  {Fore.GREEN}Translating {len(outdated_keys)} outdated keys...{Fore.RESET}")
                            target_content = translator.translate_outdated_keys(
                                source_content,
                                target_content,
                                list(outdated_keys),
                                target_lang
                            )
                            
                            # Save updated content
                            if target_file.endswith(".json"):
                                with open(target_file, "w", encoding="utf-8") as f:
                                    json.dump(target_content, f, ensure_ascii=False, indent=2)
                            elif target_file.endswith((".yaml", ".yml")):
                                with open(target_file, "w", encoding="utf-8") as f:
                                    yaml.dump(target_content, f, default_flow_style=False, allow_unicode=True)
                            
                            click.echo(f"  {Fore.GREEN}✓ Updated {len(outdated_keys)} keys in {target_file}\x1b[0m")
                    except Exception as e:
                        click.echo(f"  {Fore.RED}Error processing file with outdated keys {os.path.basename(target_file)}: {str(e)}\x1b[0m")
        
        click.echo(f"\n{Fore.GREEN}Translation completed.\x1b[0m")
        return
    
    # If no specific files were provided, scan and process all files
    # Scan for files
    try:
        scanner = FileScanner()
        files_by_language = scanner.group_files_by_language()
        
        # Get source files
        source_files = files_by_language.get(source_language, [])
        if not source_files:
            click.echo(f"{Fore.YELLOW}No source files found for language '{source_language}'.\x1b[0m")
            return
        
        click.echo(f"{Fore.GREEN}Found {len(source_files)} source files for language '{source_language}'.\x1b[0m")
        # Print verbose information about source files
        click.echo("\nSource files:")
        for idx, file_path in enumerate(source_files, 1):
            file_size = os.path.getsize(file_path)
            file_size_str = f"{file_size / 1024:.1f} KB" if file_size >= 1024 else f"{file_size} bytes"
            file_ext = os.path.splitext(file_path)[1]
            
            # Get relative path for cleaner display
            try:
                rel_path = os.path.relpath(file_path)
            except ValueError:
                rel_path = file_path
                
            click.echo(f"  {idx}. {Fore.CYAN}{rel_path}{Fore.RESET} ({file_size_str}, {file_ext})")
            
        click.echo("")  # Empty line for better readability
        
        # Check if git is available for outdated key detection
        git_available = is_git_available()
        
        # Translate each target language
        for target_lang in target_languages:
            click.echo(f"\n{Fore.BLUE}Translating to {target_lang}...\x1b[0m")
            
            # Get existing files for this language
            existing_files = files_by_language.get(target_lang, [])
            existing_file_basenames = [os.path.basename(f) for f in existing_files]
            existing_file_paths = {os.path.basename(f): f for f in existing_files}
            
            # Process each source file
            for source_file in source_files:
                source_basename = os.path.basename(source_file)
                source_dirname = os.path.dirname(source_file)
                source_ext = source_basename.split('.')[-1] if '.' in source_basename else ''
                
                # First, check if there's a direct corresponding file in the target language
                # Example: src/locales/en.json -> src/locales/es.json
                if source_basename == f"{source_language}.{source_ext}" and f"{target_lang}.{source_ext}" in existing_file_basenames:
                    target_file = existing_file_paths[f"{target_lang}.{source_ext}"]
                    target_basename = os.path.basename(target_file)
                    target_dirname = os.path.dirname(target_file)
                else:
                    # Determine target filename using the more complex logic
                    if "." in source_basename:
                        name_parts = source_basename.split(".")
                        ext = name_parts.pop()
                        base = ".".join(name_parts)
                        
                        # Special case for common localization pattern like "en.json", "es.json" in same directory
                        if source_basename == f"{source_language}.{ext}" and len(base) == len(source_language):
                            target_basename = f"{target_lang}.{ext}"
                        # Check if the base already contains language marker
                        elif f".{source_language}" in base or f"-{source_language}" in base or f"_{source_language}" in base:
                            base = base.replace(f".{source_language}", f".{target_lang}")
                            base = base.replace(f"-{source_language}", f"-{target_lang}")
                            base = base.replace(f"_{source_language}", f"_{target_lang}")
                            target_basename = f"{base}.{ext}"
                        else:
                            # If no language marker, add one with the target language
                            base = f"{base}.{target_lang}"
                            target_basename = f"{base}.{ext}"
                    else:
                        target_basename = f"{source_basename}.{target_lang}"
                    
                    # Check if target file exists in the list of already existing files for this language
                    if target_basename in existing_file_basenames:
                        target_file = existing_file_paths[target_basename]
                        target_dirname = os.path.dirname(target_file)
                    else:
                        # Determine the target directory path
                        target_dirname = os.path.dirname(determine_target_path(source_file, source_language, target_lang))
                        target_file = os.path.join(target_dirname, target_basename)
                
                os.makedirs(target_dirname, exist_ok=True)
                
                # Log the file paths for debugging
                print(f"  Source file: {source_file}")
                print(f"  Target file: {target_file}")
                
                # Check if target file already exists and is up to date
                if not force and os.path.exists(target_file):
                    source_mtime = os.path.getmtime(source_file)
                    target_mtime = os.path.getmtime(target_file)
                    
                    if target_mtime > source_mtime and not only_missing:
                        click.echo(f"  {Fore.YELLOW}Skipping {target_basename} (already up to date)\x1b[0m")
                        continue
                
                # Handle the translation based on mode (full or missing keys only)
                if only_missing and os.path.exists(target_file):
                    # Check which keys are missing in the target file
                    is_valid, missing_keys = validate_language_files(source_file, target_file)
                    
                    # Check if there are outdated keys
                    has_outdated_keys = False
                    outdated_keys = set()
                    if git_available and is_git_repository(os.path.dirname(source_file)):
                        has_outdated_keys, outdated_keys = find_outdated_keys(source_file, target_file)
                    
                    if not missing_keys and not has_outdated_keys:
                        click.echo(f"  {Fore.GREEN}No missing keys in {target_basename}. Nothing to translate.\x1b[0m")
                        continue
                    
                    if missing_keys:
                        click.echo(f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys in {target_basename}...\x1b[0m")
                    
                    try:
                        # Load both source and target files
                        if source_file.endswith(".json"):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = json.load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = json.load(f)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = yaml.safe_load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = yaml.safe_load(f)
                                
                        # Translate the missing keys
                        if missing_keys:
                            translated_content = translator.translate_missing_keys(
                                source_content, 
                                target_content, 
                                list(missing_keys), 
                                target_lang
                            )
                        else:
                            translated_content = target_content
                            
                        # Translate outdated keys if needed
                        if has_outdated_keys and not only_missing:
                            click.echo(f"  {Fore.GREEN}Translating {len(outdated_keys)} outdated keys in {target_basename}...\x1b[0m")
                            translated_content = translator.translate_outdated_keys(
                                source_content,
                                translated_content,
                                list(outdated_keys),
                                target_lang
                            )
                        
                        # Save updated content
                        if source_file.endswith(".json"):
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(translated_content, f, ensure_ascii=False, indent=2)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(translated_content, f, default_flow_style=False, allow_unicode=True)
                        
                        updated_count = len(missing_keys) + (len(outdated_keys) if has_outdated_keys and not only_missing else 0)
                        click.echo(f"  {Fore.GREEN}✓ Updated {updated_count} keys in {target_file}\x1b[0m")
                    except Exception as e:
                        click.echo(f"  {Fore.RED}Error translating keys in {source_basename}: {str(e)}\x1b[0m")
                else:
                    # Translate the full file
                    click.echo(f"  {Fore.GREEN}Translating {source_basename} to {target_basename}...\x1b[0m")
                    try:
                        translated_content = translator.translate_file(source_file, target_lang)
                        
                        # Save translated content
                        if source_file.endswith(".json"):
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(translated_content, f, ensure_ascii=False, indent=2)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(translated_content, f, default_flow_style=False, allow_unicode=True)
                        
                        click.echo(f"  {Fore.GREEN}✓ Saved to {target_file}\x1b[0m")
                    except Exception as e:
                        click.echo(f"  {Fore.RED}Error translating {source_basename}: {str(e)}\x1b[0m")
        
        click.echo(f"\n{Fore.GREEN}Translation completed.\x1b[0m")
        click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m")
    
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}\x1b[0m")


def get_nested_value(data: Dict[str, Any], key_parts: List[str]) -> Any:
    """
    Get a value from a nested dictionary using a list of key parts.
    
    Args:
        data: Dictionary to get value from
        key_parts: List of key parts representing a dot-notation path
        
    Returns:
        Value at the specified path
    """
    current = data
    for part in key_parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current 