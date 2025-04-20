"""
Update your translations
"""

import os
import click
from colorama import Fore
from typing import Optional, Dict, List, Tuple, Set

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.commands import translate_command
from algebras.utils.lang_validator import validate_language_files, find_outdated_keys
from algebras.utils.git_utils import is_git_available, is_git_repository


def execute(language: Optional[str] = None, only_missing: bool = True, skip_git_validation: bool = False) -> None:
    """
    Update your translations.
    
    Args:
        language: Language to update (if None, update all languages)
        only_missing: If True, only missing keys will be translated (default: True)
        skip_git_validation: If True, git validation will be skipped even if git is available (default: False)
    """
    config = Config()
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return
    
    # Load configuration
    config.load()
    
    # Get languages
    all_languages = config.get_languages()
    
    # Filter languages if specified
    if language:
        if language not in all_languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.\x1b[0m")
            return
        languages = [language]
    else:
        # Skip the source language
        source_lang = config.get_source_language()
        languages = [lang for lang in all_languages if lang != source_lang]
    
    if not languages:
        click.echo(f"{Fore.YELLOW}No target languages configured. Add languages with 'algebras add <language>'.\x1b[0m")
        return
    
    # Get source language
    source_language = config.get_source_language()
    
    # Check if git is available for outdated key detection
    git_available = is_git_available() and not skip_git_validation
    if git_available:
        click.echo(f"{Fore.BLUE}Using git for key validation. This may take some time...\x1b[0m")
    else:
        click.echo(f"{Fore.YELLOW}Git is not available. Skipping detection of updated keys.\x1b[0m")
    
    # Scan for files
    try:
        scanner = FileScanner()
        files_by_language = scanner.group_files_by_language()
        print(f"files_by_language: {files_by_language}")
        # Get source files
        source_files = files_by_language.get(source_language, [])
        print(f"source_files: {source_files}")
        if not source_files:
            click.echo(f"{Fore.YELLOW}No source files found for language '{source_language}'.\x1b[0m")
            return
        
        # Find outdated files and files with missing keys
        outdated_by_language = {}
        missing_keys_by_language = {}
        outdated_keys_by_language = {}
        
        for lang in languages:
            lang_files = files_by_language.get(lang, [])
            outdated_files = []
            missing_keys_files = []
            outdated_keys_files = []
            
            for lang_file in lang_files:
                # Find corresponding source file
                source_file = None
                lang_basename = os.path.basename(lang_file)
                lang_dirname = os.path.dirname(lang_file)
                
                # Handle simple case where filename is just "language.json"
                if lang_basename == f"{lang}.json" and f"{source_language}.json" in [os.path.basename(f) for f in source_files]:
                    source_basename = f"{source_language}.json"
                    potential_source_file = os.path.join(lang_dirname, source_basename)
                    
                    # Find the exact source file path
                    for src_file in source_files:
                        if os.path.basename(src_file) == source_basename:
                            source_file = src_file
                            break
                # More complex cases with language suffixes
                elif "." in lang_basename:
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
                    potential_source_file = os.path.join(lang_dirname, source_basename)
                    
                    if potential_source_file in source_files:
                        source_file = potential_source_file
                else:
                    source_basename = lang_basename.replace(f".{lang}", "")
                    potential_source_file = os.path.join(lang_dirname, source_basename)
                    
                    if potential_source_file in source_files:
                        source_file = potential_source_file
                
                print(f"lang_file: {lang_file}, source_file: {source_file}")
                
                if source_file:
                    # Check if file is outdated based on modification time
                    source_mtime = os.path.getmtime(source_file)
                    lang_mtime = os.path.getmtime(lang_file)
                    
                    if lang_mtime < source_mtime:
                        outdated_files.append((lang_file, source_file))
                    
                    # Check if all keys from source language exist in target language
                    is_valid, missing_keys = validate_language_files(source_file, lang_file)
                    if not is_valid:
                        missing_keys_files.append((lang_file, missing_keys, source_file))
                    
                    # Check for outdated keys using git history if available
                    if git_available and is_git_repository(os.path.dirname(source_file)):
                        has_outdated_keys, outdated_keys = find_outdated_keys(source_file, lang_file)
                        if has_outdated_keys:
                            outdated_keys_files.append((lang_file, outdated_keys, source_file))
            
            outdated_by_language[lang] = outdated_files
            missing_keys_by_language[lang] = missing_keys_files
            outdated_keys_by_language[lang] = outdated_keys_files
        
        # Count outdated and missing keys files
        total_outdated = sum(len(files) for files in outdated_by_language.values())
        total_missing_keys = sum(len(files) for files in missing_keys_by_language.values())
        total_outdated_keys = sum(len(files) for files in outdated_keys_by_language.values())
        
        if total_outdated == 0 and total_missing_keys == 0 and total_outdated_keys == 0:
            click.echo(f"{Fore.GREEN}All translations are up to date and complete.\x1b[0m")
            return
        
        # Print summary
        if total_outdated > 0:
            click.echo(f"{Fore.YELLOW}Found {total_outdated} outdated translations (file modification time).\x1b[0m")
        
        if total_missing_keys > 0:
            click.echo(f"{Fore.YELLOW}Found {total_missing_keys} translations with missing keys.\x1b[0m")
            
        if total_outdated_keys > 0:
            click.echo(f"{Fore.YELLOW}Found {total_outdated_keys} translations with outdated keys (based on git history).\x1b[0m")
        
        # Update outdated files and files with missing keys
        for lang in languages:
            outdated_files = outdated_by_language[lang]
            missing_keys_files = missing_keys_by_language[lang]
            outdated_keys_files = outdated_keys_by_language[lang]
            
            # Get unique files that need updating (either outdated, missing keys, or outdated keys)
            files_to_update = set()
            for file_path, _ in outdated_files:
                files_to_update.add(file_path)
            for file_path, _, _ in missing_keys_files:
                files_to_update.add(file_path)
            for file_path, _, _ in outdated_keys_files:
                files_to_update.add(file_path)
            
            if not files_to_update:
                click.echo(f"\n{Fore.GREEN}Language '{lang}' is up to date and complete.\x1b[0m")
                continue
            
            click.echo(f"\n{Fore.BLUE}Updating {len(files_to_update)} files for language '{lang}'...{Fore.RESET}")
            
            # For files with missing keys, print the missing keys
            for file_path, missing_keys, _ in missing_keys_files:
                if missing_keys:
                    click.echo(f"  {Fore.YELLOW}File {os.path.basename(file_path)} is missing {len(missing_keys)} keys:{Fore.RESET}")
                    # Print up to 5 missing keys as examples
                    for key in list(missing_keys)[:5]:
                        click.echo(f"    - {key}")
                    if len(missing_keys) > 5:
                        click.echo(f"    - ... and {len(missing_keys) - 5} more")
            
            # For files with outdated keys, print the outdated keys
            for file_path, outdated_keys, _ in outdated_keys_files:
                if outdated_keys:
                    click.echo(f"  {Fore.YELLOW}File {os.path.basename(file_path)} has {len(outdated_keys)} outdated keys (git history):{Fore.RESET}")
                    # Print up to 5 outdated keys as examples
                    for key in list(outdated_keys)[:5]:
                        click.echo(f"    - {key}")
                    if len(outdated_keys) > 5:
                        click.echo(f"    - ... and {len(outdated_keys) - 5} more")
            
            # For outdated files based on modification time, extract potentially outdated keys
            # by comparing the content of both files
            for file_path, source_file in outdated_files:
                click.echo(f"  {Fore.YELLOW}File {os.path.basename(file_path)} is outdated (modification time):{Fore.RESET}")
                
                # Pass this information to the translate command
                # We'll handle the extraction of potentially outdated keys there
                translate_command.execute(
                    lang, 
                    force=True, 
                    only_missing=True,
                    outdated_files=[(file_path, source_file)]
                )
                
            # For files with missing or outdated keys (from git), call translate command
            # only for those specific keys
            if missing_keys_files or outdated_keys_files:
                translate_command.execute(
                    lang, 
                    force=True, 
                    only_missing=True,
                    missing_keys_files=missing_keys_files,
                    outdated_keys_files=outdated_keys_files
                )
        
        click.echo(f"\n{Fore.GREEN}Update completed.\x1b[0m")
        click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m")
    
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}\x1b[0m") 