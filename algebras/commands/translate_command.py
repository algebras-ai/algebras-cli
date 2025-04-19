"""
Translate your application
"""

import os
import json
import yaml
import click
from colorama import Fore
from typing import Dict, Any, Optional

from algebras.config import Config
from algebras.services.translator import Translator
from algebras.services.file_scanner import FileScanner
from algebras.utils.path_utils import determine_target_path


def execute(language: Optional[str] = None, force: bool = False) -> None:
    """
    Translate your application.
    
    Args:
        language: Language to translate (if None, translate all languages)
        force: Force translation even if files are up to date
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
        # Skip the first language (source language)
        target_languages = languages[1:]
    
    # Get source language
    source_language = languages[0]
    
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
        
        # Initialize translator
        translator = Translator()
        
        # Translate each target language
        for target_lang in target_languages:
            click.echo(f"\n{Fore.BLUE}Translating to {target_lang}...\x1b[0m")
            
            # Get existing files for this language
            existing_files = files_by_language.get(target_lang, [])
            existing_file_basenames = [os.path.basename(f) for f in existing_files]
            
            # Process each source file
            for source_file in source_files:
                source_basename = os.path.basename(source_file)
                source_dirname = os.path.dirname(source_file)
                
                # Determine target filename
                if "." in source_basename:
                    name_parts = source_basename.split(".")
                    ext = name_parts.pop()
                    base = ".".join(name_parts)
                    
                    # Check if the base already contains language marker
                    if f".{source_language}" in base or f"-{source_language}" in base or f"_{source_language}" in base:
                        base = base.replace(f".{source_language}", "")
                        base = base.replace(f"-{source_language}", "")
                        base = base.replace(f"_{source_language}", "")
                    
                    target_basename = f"{base}.{ext}"
                else:
                    target_basename = source_basename
                
                # Determine the target directory path
                target_dirname = os.path.dirname(determine_target_path(source_file, source_language, target_lang))
                os.makedirs(target_dirname, exist_ok=True)
                
                target_file = os.path.join(target_dirname, target_basename)
                
                # Check if target file already exists and is up to date
                if not force and os.path.exists(target_file):
                    source_mtime = os.path.getmtime(source_file)
                    target_mtime = os.path.getmtime(target_file)
                    
                    if target_mtime > source_mtime:
                        click.echo(f"  {Fore.YELLOW}Skipping {target_basename} (already up to date)\x1b[0m")
                        continue
                
                # Translate the file
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