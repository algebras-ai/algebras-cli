"""
Update your translations
"""

import os
import click
import sys
from colorama import Fore
from typing import Optional, Dict, List, Tuple, Set

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.commands import translate_command
from algebras.utils.lang_validator import validate_language_files, find_outdated_keys
from algebras.utils.git_utils import (
    is_git_available,
    is_git_repository,
    compare_key_modifications,
    get_key_commit_info
)


def execute(language: Optional[str] = None, only_missing: bool = True, skip_git_validation: bool = False, ui_safe: bool = False, verbose: bool = False) -> None:
    """
    Update your translations.
    
    Args:
        language: Language to update (if None, update all languages)
        only_missing: If True, only missing keys will be translated (default: True)
        skip_git_validation: If True, git validation will be skipped even if git is available (default: False)
        ui_safe: If True, ensure translations will not be longer than original text (default: False)
        verbose: If True, show detailed logs of the update process (default: False)
    """
    config = Config()
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return
    
    # Load configuration
    config.load()
    if verbose:
        click.echo(f"{Fore.BLUE}Loaded configuration: {config.config_path}\x1b[0m")
    
    # Get languages
    all_languages = config.get_languages()
    if verbose:
        click.echo(f"{Fore.BLUE}Available languages: {', '.join(all_languages)}\x1b[0m")
    
    # Filter languages if specified
    if language:
        if language not in all_languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.\x1b[0m")
            return
        languages = [language]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected language: {language}\x1b[0m")
    else:
        # Skip the source language
        source_lang = config.get_source_language()
        languages = [lang for lang in all_languages if lang != source_lang]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected languages: {', '.join(languages)}\x1b[0m")
    
    if not languages:
        click.echo(f"{Fore.YELLOW}No target languages configured. Add languages with 'algebras add <language>'.\x1b[0m")
        return
    
    # Get source language
    source_language = config.get_source_language()
    if verbose:
        click.echo(f"{Fore.BLUE}Source language: {source_language}\x1b[0m")
    
    # Check if git is available for outdated key detection
    git_available = is_git_available() and not skip_git_validation
    if git_available:
        click.echo(f"{Fore.BLUE}Using git for key validation. This may take some time...\x1b[0m")
    else:
        click.echo(f"{Fore.YELLOW}Git is not available. Skipping detection of updated keys.\x1b[0m")
    
    # Scan for files
    try:
        if verbose:
            click.echo(f"{Fore.BLUE}Scanning for translation files...\x1b[0m")
        
        scanner = FileScanner()
        files_by_language = scanner.group_files_by_language()
        
        if verbose:
            click.echo(f"{Fore.BLUE}Found files by language: {files_by_language}\x1b[0m")
        else:
            print(f"files_by_language: {files_by_language}")
            
        # Get source files
        source_files = files_by_language.get(source_language, [])
        
        if verbose:
            click.echo(f"{Fore.BLUE}Source files ({len(source_files)}):\x1b[0m")
            for src_file in source_files:
                click.echo(f"  - {src_file}")
        else:
            print(f"source_files: {source_files}")
            
        if not source_files:
            click.echo(f"{Fore.YELLOW}No source files found for language '{source_language}'.\x1b[0m")
            return
        
        # Find outdated files and files with missing keys
        outdated_by_language = {}
        missing_keys_by_language = {}
        outdated_keys_by_language = {}
        
        for lang in languages:
            if verbose:
                click.echo(f"\n{Fore.BLUE}Processing language: {lang}\x1b[0m")
                
            lang_files = files_by_language.get(lang, [])
            
            if verbose:
                click.echo(f"{Fore.BLUE}Found {len(lang_files)} files for language '{lang}':\x1b[0m")
                for lang_file in lang_files:
                    click.echo(f"  - {lang_file}")
                    
            outdated_files = []
            missing_keys_files = []
            outdated_keys_files = []
            
            for lang_file in lang_files:
                if verbose:
                    click.echo(f"\n{Fore.BLUE}Analyzing file: {lang_file}\x1b[0m")
                    
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
                
                if verbose:
                    if source_file:
                        click.echo(f"{Fore.BLUE}Matched with source file: {source_file}\x1b[0m")
                
                if source_file:
                    # Check if file is outdated based on modification time
                    source_mtime = os.path.getmtime(source_file)
                    lang_mtime = os.path.getmtime(lang_file)
                    
                    if lang_mtime < source_mtime:
                        if verbose:
                            click.echo(f"{Fore.YELLOW}File is outdated based on modification time\x1b[0m")
                            click.echo(f"  Source modified: {source_mtime}")
                            click.echo(f"  Target modified: {lang_mtime}")
                        outdated_files.append((lang_file, source_file))
                    elif verbose:
                        click.echo(f"{Fore.GREEN}File is up to date based on modification time\x1b[0m")
                    
                    # Check if all keys from source language exist in target language
                    if verbose:
                        click.echo(f"{Fore.BLUE}Validating language file for missing keys...\x1b[0m")
                    is_valid, missing_keys = validate_language_files(source_file, lang_file)
                    if not is_valid:
                        if verbose:
                            click.echo(f"{Fore.YELLOW}Found {len(missing_keys)} missing keys\x1b[0m")
                        missing_keys_files.append((lang_file, missing_keys, source_file))
                    elif verbose:
                        click.echo(f"{Fore.GREEN}All keys present\x1b[0m")
                    
                    # Check for outdated keys using git history if available
                    if git_available and is_git_repository(os.path.dirname(source_file)):
                        if verbose:
                            click.echo(f"{Fore.BLUE}Checking for outdated keys using git history...\x1b[0m")
                        has_outdated_keys, outdated_keys = find_outdated_keys(source_file, lang_file)
                        if has_outdated_keys:
                            if verbose:
                                click.echo(f"{Fore.YELLOW}Found {len(outdated_keys)} outdated keys based on git history\x1b[0m")
                            outdated_keys_files.append((lang_file, outdated_keys, source_file))
                        elif verbose:
                            click.echo(f"{Fore.GREEN}No outdated keys found\x1b[0m")
            
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
            
            if verbose:
                click.echo(f"{Fore.BLUE}Files that need updating:\x1b[0m")
                for file_path in files_to_update:
                    click.echo(f"  - {file_path}")
            
            # For outdated files based on modification time, call translate_command for each file
            for file_path, source_file in outdated_files:
                click.echo(f"  {Fore.YELLOW}File {os.path.basename(file_path)} is outdated (modification time):{Fore.RESET}")
                translate_command.execute(
                    lang, 
                    force=True, 
                    only_missing=True,
                    outdated_files=[(file_path, source_file)],
                    ui_safe=ui_safe,
                    verbose=verbose
                )

            # For files with missing keys, call translate_command for each file
            for file_path, missing_keys, source_file in missing_keys_files:
                if missing_keys:
                    click.echo(f"  {Fore.YELLOW}File {os.path.basename(file_path)} is missing {len(missing_keys)} keys:{Fore.RESET}")
                    for key in list(missing_keys)[:5]:
                        click.echo(f"    - {key}")
                    if len(missing_keys) > 5:
                        click.echo(f"    - ... and {len(missing_keys) - 5} more")
                    translate_command.execute(
                        lang,
                        force=True,
                        only_missing=True,
                        missing_keys_files=[(file_path, missing_keys, source_file)],
                        ui_safe=ui_safe,
                        verbose=verbose
                    )

            # For files with outdated keys, call translate_command for each file
            for file_path, outdated_keys, source_file in outdated_keys_files:
                if outdated_keys:
                    click.echo(f"  {Fore.YELLOW}File {os.path.basename(file_path)} has {len(outdated_keys)} outdated keys (git history):{Fore.RESET}")
                    translate_command.execute(
                        lang,
                        force=True,
                        only_missing=True,
                        outdated_keys_files=[(file_path, outdated_keys, source_file)],
                        ui_safe=ui_safe,
                        verbose=verbose
                    )
        
        click.echo(f"\n{Fore.GREEN}Update completed.\x1b[0m")
        click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m")
    
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}\x1b[0m")
        if verbose:
            import traceback
            click.echo(f"{Fore.RED}Traceback:\x1b[0m")
            click.echo(traceback.format_exc())

def execute_ci(language: Optional[str] = None, verbose: bool = False) -> int:
    """
    Run CI checks for translations without performing translation.
    Always uses git validation for key changes.
    
    Args:
        language: Language to check (if None, check all languages)
        verbose: If True, show detailed logs of the check process
        
    Returns:
        int: 0 if all checks pass, -1 if any errors are found
    """
    config = Config()
    errors_found = False
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return -1
    
    # Load configuration
    config.load()
    if verbose:
        click.echo(f"{Fore.BLUE}Loaded configuration: {config.config_path}\x1b[0m")
    
    # Get languages
    all_languages = config.get_languages()
    if verbose:
        click.echo(f"{Fore.BLUE}Available languages: {', '.join(all_languages)}\x1b[0m")
    
    # Filter languages if specified
    if language:
        if language not in all_languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.\x1b[0m")
            return -1
        languages = [language]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected language: {language}\x1b[0m")
    else:
        # Skip the source language
        source_lang = config.get_source_language()
        languages = [lang for lang in all_languages if lang != source_lang]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected languages: {', '.join(languages)}\x1b[0m")
    
    if not languages:
        click.echo(f"{Fore.YELLOW}No target languages configured. Add languages with 'algebras add <language>'.\x1b[0m")
        return -1
    
    # Get source language
    source_language = config.get_source_language()
    if verbose:
        click.echo(f"{Fore.BLUE}Source language: {source_language}\x1b[0m")
    
    # Check if git is available for outdated key detection
    git_available = is_git_available()
    if not git_available:
        click.echo(f"{Fore.RED}Git is required for CI checks but is not available.\x1b[0m")
        return -1
        
    click.echo(f"{Fore.BLUE}Running CI checks using git for key validation...\x1b[0m")
    
    # Scan for files
    try:
        if verbose:
            click.echo(f"{Fore.BLUE}Scanning for translation files...\x1b[0m")
            
        scanner = FileScanner()
        files_by_language = scanner.group_files_by_language()
        
        if verbose:
            click.echo(f"{Fore.BLUE}Found files by language: {files_by_language}\x1b[0m")
        
        # Get source files
        source_files = files_by_language.get(source_language, [])
        
        if verbose:
            click.echo(f"{Fore.BLUE}Source files ({len(source_files)}):\x1b[0m")
            for src_file in source_files:
                click.echo(f"  - {src_file}")
        
        if not source_files:
            click.echo(f"{Fore.RED}No source files found for language '{source_language}'.\x1b[0m")
            return -1
        
        # Find outdated files and files with missing keys
        missing_keys_by_language = {}
        outdated_keys_by_language = {}
        
        for lang in languages:
            if verbose:
                click.echo(f"\n{Fore.BLUE}Processing language: {lang}\x1b[0m")
                
            lang_files = files_by_language.get(lang, [])
            
            if verbose:
                click.echo(f"{Fore.BLUE}Found {len(lang_files)} files for language '{lang}':\x1b[0m")
                for lang_file in lang_files:
                    click.echo(f"  - {lang_file}")
                    
            missing_keys_files = []
            outdated_keys_files = []
            
            for lang_file in lang_files:
                if verbose:
                    click.echo(f"\n{Fore.BLUE}Analyzing file: {lang_file}\x1b[0m")
                    
                # Find corresponding source file
                source_file = None
                lang_basename = os.path.basename(lang_file)
                if verbose:
                    click.echo(f"lang_basename: {lang_basename}")
                lang_dirname = os.path.dirname(lang_file)
                if verbose:
                    click.echo(f"lang_dirname: {lang_dirname}")

                # Check for language in path first
                if f"/{lang}/" in lang_file or f"\\{lang}\\" in lang_file:
                    potential_source_file = lang_file.replace(f"/{lang}/", f"/{source_language}/").replace(f"\\{lang}\\", f"\\{source_language}\\")
                    if potential_source_file in source_files:
                        source_file = potential_source_file
                
                # Handle simple case where filename is just "language.json"
                elif lang_basename == f"{lang}.json" and f"{source_language}.json" in [os.path.basename(f) for f in source_files]:
                    source_basename = f"{source_language}.json"
                    
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
                
                if verbose:
                    if source_file:
                        click.echo(f"{Fore.BLUE}Matched with source file: {source_file}\x1b[0m")
                
                if source_file:
                    # Check if all keys from source language exist in target language
                    is_valid, missing_keys = validate_language_files(source_file, lang_file)
                    if not is_valid:
                        if verbose:
                            click.echo(f"{Fore.YELLOW}Found {len(missing_keys)} missing keys\x1b[0m")
                        missing_keys_files.append((lang_file, missing_keys, source_file))
                    elif verbose:
                        click.echo(f"{Fore.GREEN}All keys present\x1b[0m")
                    
                    # Check for outdated keys using git history
                    if is_git_repository(os.path.dirname(source_file)):
                        if verbose:
                            click.echo(f"{Fore.BLUE}Checking for outdated keys using git history...\x1b[0m")
                        has_outdated_keys, outdated_keys = find_outdated_keys(source_file, lang_file)
                        if has_outdated_keys:
                            if verbose:
                                click.echo(f"{Fore.YELLOW}Found {len(outdated_keys)} outdated keys based on git history\x1b[0m")
                            outdated_keys_files.append((lang_file, outdated_keys, source_file))
                        elif verbose:
                            click.echo(f"{Fore.GREEN}No outdated keys found\x1b[0m")
                elif verbose:
                    click.echo(f"{Fore.YELLOW}No matching source file found\x1b[0m")
            missing_keys_by_language[lang] = missing_keys_files
            outdated_keys_by_language[lang] = outdated_keys_files
        
        # Count outdated and missing keys files
        total_missing_keys = sum(len(files) for files in missing_keys_by_language.values())
        total_outdated_keys = sum(len(files) for files in outdated_keys_by_language.values())
        
        if total_missing_keys == 0 and total_outdated_keys == 0:
            click.echo(f"{Fore.GREEN}CI Check: All translations are up to date and complete.\x1b[0m")
            return 0
        
        # Print detailed errors for CI
        errors_found = False
        click.echo(f"{Fore.RED}CI Check: Found issues with translations:\x1b[0m")
        
        for lang in languages:
            missing_keys_files = missing_keys_by_language[lang]
            outdated_keys_files = outdated_keys_by_language[lang]
            
            if not missing_keys_files and not outdated_keys_files:
                click.echo(f"{Fore.GREEN}Language '{lang}': No issues found.\x1b[0m")
                continue
            
            if missing_keys_files or outdated_keys_files:
                errors_found = True
                
            if missing_keys_files:
                click.echo(f"\n{Fore.RED}Language '{lang}': Found {len(missing_keys_files)} files with missing keys:\x1b[0m")
                for file_path, missing_keys, source_file in missing_keys_files:
                    click.echo(f"  {Fore.RED}File: {file_path}\x1b[0m")
                    click.echo(f"  {Fore.RED}Missing {len(missing_keys)} keys from source: {source_file}\x1b[0m")
                    # Print all missing keys
                    for key in sorted(missing_keys):
                        click.echo(f"    - {key}")
            
            if outdated_keys_files:
                click.echo(f"\n{Fore.RED}Language '{lang}': Found {len(outdated_keys_files)} files with outdated keys (based on git history):\x1b[0m")
                for file_path, outdated_keys, source_file in outdated_keys_files:
                    click.echo(f"  {Fore.RED}File: {file_path}\x1b[0m")
                    click.echo(f"  {Fore.RED}Outdated {len(outdated_keys)} keys from source: {source_file}\x1b[0m")
                    
                    # Add a separator for better readability
                    click.echo(f"  {Fore.YELLOW}{'-' * 40}\x1b[0m")
                    
                    # Print all outdated keys with their details in a more organized format
                    for key in sorted(outdated_keys):
                        is_outdated, source_date, target_date = compare_key_modifications(source_file, file_path, key)
                        if is_outdated:
                            source_commit, source_author = get_key_commit_info(source_file, key)
                            target_commit, target_author = get_key_commit_info(file_path, key)
                            
                            click.echo(f"  {Fore.BLUE}Key: {key}\x1b[0m")
                            click.echo(f"    {Fore.GREEN}Source:{Fore.RESET}")
                            click.echo(f"      Last modified: {source_date}")
                            if source_commit and source_author:
                                click.echo(f"      Commit: {source_commit[:8]} by {source_author}")
                            click.echo(f"    {Fore.GREEN}Target:{Fore.RESET}")
                            click.echo(f"      Last modified: {target_date}")
                            if target_commit and target_author:
                                click.echo(f"      Commit: {target_commit[:8]} by {target_author}")
                            click.echo(f"  {Fore.YELLOW}{'-' * 40}\x1b[0m")
        
        return -1 if errors_found else 0
    
    except Exception as e:
        click.echo(f"{Fore.RED}CI Check Error: {str(e)}\x1b[0m")
        if verbose:
            import traceback
            click.echo(f"{Fore.RED}Traceback:\x1b[0m")
            click.echo(traceback.format_exc())
        return -1 