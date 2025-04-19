"""
Update your translations
"""

import os
import click
from colorama import Fore
from typing import Optional, Dict, List

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.commands import translate_command


def execute(language: Optional[str] = None) -> None:
    """
    Update your translations.
    
    Args:
        language: Language to update (if None, update all languages)
    """
    config = Config()
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.{Fore.RESET}")
        return
    
    # Load configuration
    config.load()
    
    # Get languages
    all_languages = config.get_languages()
    
    # Filter languages if specified
    if language:
        if language not in all_languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.{Fore.RESET}")
            return
        languages = [language]
    else:
        # Skip the first language (source language)
        languages = all_languages[1:]
    
    if not languages:
        click.echo(f"{Fore.YELLOW}No target languages configured. Add languages with 'algebras add <language>'.{Fore.RESET}")
        return
    
    # Get source language
    source_language = all_languages[0]
    
    # Scan for files
    try:
        scanner = FileScanner()
        files_by_language = scanner.group_files_by_language()
        
        # Get source files
        source_files = files_by_language.get(source_language, [])
        if not source_files:
            click.echo(f"{Fore.YELLOW}No source files found for language '{source_language}'.{Fore.RESET}")
            return
        
        # Find outdated files
        outdated_by_language = {}
        
        for lang in languages:
            lang_files = files_by_language.get(lang, [])
            outdated_files = []
            
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
                        outdated_files.append(lang_file)
            
            outdated_by_language[lang] = outdated_files
        
        # Print summary
        total_outdated = sum(len(files) for files in outdated_by_language.values())
        if total_outdated == 0:
            click.echo(f"{Fore.GREEN}All translations are up to date.{Fore.RESET}")
            return
        
        click.echo(f"{Fore.YELLOW}Found {total_outdated} outdated translations.{Fore.RESET}")
        
        # Update outdated files
        for lang in languages:
            outdated_files = outdated_by_language[lang]
            if not outdated_files:
                continue
                
            click.echo(f"\n{Fore.BLUE}Updating {len(outdated_files)} files for language '{lang}'...{Fore.RESET}")
            
            # Use translate command with force option to update files
            translate_command.execute(lang, force=True)
        
        click.echo(f"\n{Fore.GREEN}Update completed.{Fore.RESET}")
        click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status{Fore.RESET}")
    
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}") 