"""
Review your translations
"""

import os
import json
import yaml
import click
from colorama import Fore
from typing import Optional, Dict, Any

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.android_xml_handler import read_android_xml_file
from algebras.utils.ios_strings_handler import read_ios_strings_file
from algebras.utils.po_handler import read_po_file


def execute(language: Optional[str] = None, config_file: str = None) -> None:
    """
    Review your translations.
    
    Args:
        language: Language to review (if None, prompt for language)
        config_file: Path to custom config file (optional)
    """
    config = Config(config_file)
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.{Fore.RESET}")
        return
    
    # Load configuration
    config.load()
    
    # Check for deprecated config format
    if config.check_deprecated_format():
        click.echo(f"{Fore.RED}🚨 ⚠️  WARNING: Your configuration uses the deprecated 'path_rules' format! ⚠️ 🚨{Fore.RESET}")
        click.echo(f"{Fore.RED}🔴 Please update to the new 'source_files' format.{Fore.RESET}")
        click.echo(f"{Fore.RED}📖 See documentation: https://github.com/algebras-ai/algebras-cli{Fore.RESET}")
    
    # Get languages
    all_languages = config.get_languages()
    
    # Get source language
    source_language = all_languages[0]
    
    # Determine target language
    if language:
        if language not in all_languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.{Fore.RESET}")
            return
        target_language = language
    else:
        # Skip the source language
        target_languages = [lang for lang in all_languages if lang != source_language]
        
        if not target_languages:
            click.echo(f"{Fore.YELLOW}No target languages configured. Add languages with 'algebras add <language>'.{Fore.RESET}")
            return
        
        # Prompt for language if not specified
        if len(target_languages) == 1:
            target_language = target_languages[0]
        else:
            click.echo(f"{Fore.BLUE}Available languages:{Fore.RESET}")
            for i, lang in enumerate(target_languages, 1):
                click.echo(f"{i}. {lang}")
            
            selection = click.prompt("Select a language to review", type=int, default=1)
            if selection < 1 or selection > len(target_languages):
                click.echo(f"{Fore.RED}Invalid selection.{Fore.RESET}")
                return
            
            target_language = target_languages[selection - 1]
    
    # Scan for files
    try:
        scanner = FileScanner(config=config)
        files_by_language = scanner.group_files_by_language()
        
        # Get source files and target files
        source_files = files_by_language.get(source_language, [])
        target_files = files_by_language.get(target_language, [])
        
        if not source_files:
            click.echo(f"{Fore.YELLOW}No source files found for language '{source_language}'.{Fore.RESET}")
            return
        
        if not target_files:
            click.echo(f"{Fore.YELLOW}No files found for language '{target_language}'. Try translating first.{Fore.RESET}")
            return
        
        # For each target file, find the corresponding source file
        matched_files = []
        
        for target_file in target_files:
            target_basename = os.path.basename(target_file)
            target_dirname = os.path.dirname(target_file)
            
            # Find base filename
            if "." in target_basename:
                name_parts = target_basename.split(".")
                ext = name_parts.pop()
                base = ".".join(name_parts)
                
                # Special case for files named directly with language code (e.g., 'ca.json', 'en.json')
                if base == target_language and ext in ["json", "yaml", "yml"]:
                    source_basename = f"{source_language}.{ext}"
                    potential_source_file = os.path.join(target_dirname, source_basename)
                    if potential_source_file in source_files:
                        matched_files.append((potential_source_file, target_file))
                        continue
                
                # Replace target language marker with source language marker
                if f".{target_language}" in base:
                    base_source = base.replace(f".{target_language}", f".{source_language}")
                elif f"-{target_language}" in base:
                    base_source = base.replace(f"-{target_language}", f"-{source_language}")
                elif f"_{target_language}" in base:
                    base_source = base.replace(f"_{target_language}", f"_{source_language}")
                else:
                    # Remove language suffix and add source language
                    base_source = base.replace(f".{target_language}", "")
                    if source_language != "en":  # Assuming English is implicit if no marker
                        base_source = f"{base_source}.{source_language}"
                
                source_basename = f"{base_source}.{ext}"
            else:
                source_basename = target_basename.replace(f".{target_language}", "")
                if source_language != "en":
                    source_basename = f"{source_basename}.{source_language}"
            
            potential_source_file = os.path.join(target_dirname, source_basename)
            
            if potential_source_file in source_files:
                matched_files.append((potential_source_file, target_file))
        
        if not matched_files:
            click.echo(f"{Fore.YELLOW}No matching file pairs found for review.{Fore.RESET}")
            return
        
        # Review each file pair
        for source_file, target_file in matched_files:
            click.echo(f"\n{Fore.GREEN}Reviewing {os.path.basename(target_file)}{Fore.RESET}")
            
            # Load file contents
            if source_file.endswith(".json"):
                with open(source_file, "r", encoding="utf-8") as f:
                    source_content = json.load(f)
                with open(target_file, "r", encoding="utf-8") as f:
                    target_content = json.load(f)
                
                # Review content
                review_content(source_content, target_content, source_language, target_language)
            
            elif source_file.endswith((".yaml", ".yml")):
                with open(source_file, "r", encoding="utf-8") as f:
                    source_content = yaml.safe_load(f)
                with open(target_file, "r", encoding="utf-8") as f:
                    target_content = yaml.safe_load(f)
                
                # Review content
                review_content(source_content, target_content, source_language, target_language)
            
            elif source_file.endswith(".xml"):
                source_content = read_android_xml_file(source_file)
                target_content = read_android_xml_file(target_file)
                
                # Review content
                review_content(source_content, target_content, source_language, target_language)
            
            elif source_file.endswith(".strings"):
                source_content = read_ios_strings_file(source_file)
                target_content = read_ios_strings_file(target_file)
                
                # Review content
                review_content(source_content, target_content, source_language, target_language)
            
            elif source_file.endswith(".po"):
                source_content = read_po_file(source_file)
                target_content = read_po_file(target_file)
                
                # Review content
                review_content(source_content, target_content, source_language, target_language)
            
            else:
                click.echo(f"{Fore.YELLOW}Unsupported file format: {source_file}{Fore.RESET}")
                continue
        
        click.echo(f"\n{Fore.GREEN}Review completed.{Fore.RESET}")
    
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")


def review_content(source: Dict[str, Any], target: Dict[str, Any], source_lang: str, target_lang: str, path: str = "") -> None:
    """
    Recursively review and compare source and target content.
    
    Args:
        source: Source content
        target: Target content
        source_lang: Source language code
        target_lang: Target language code
        path: Current path in the nested structure
    """
    if not isinstance(source, dict) or not isinstance(target, dict):
        return
    
    # Check for missing keys
    source_keys = set(source.keys())
    target_keys = set(target.keys())
    
    missing_keys = source_keys - target_keys
    if missing_keys:
        click.echo(f"{Fore.RED}Missing keys in {target_lang}:{Fore.RESET}")
        for key in missing_keys:
            full_path = f"{path}.{key}" if path else key
            click.echo(f"  {full_path}")
    
    extra_keys = target_keys - source_keys
    if extra_keys:
        click.echo(f"{Fore.YELLOW}Extra keys in {target_lang}:{Fore.RESET}")
        for key in extra_keys:
            full_path = f"{path}.{key}" if path else key
            click.echo(f"  {full_path}")
    
    # Review common keys
    common_keys = source_keys.intersection(target_keys)
    for key in common_keys:
        full_path = f"{path}.{key}" if path else key
        source_value = source[key]
        target_value = target[key]
        
        if isinstance(source_value, dict) and isinstance(target_value, dict):
            # Recursively review nested dictionaries
            review_content(source_value, target_value, source_lang, target_lang, full_path)
        elif isinstance(source_value, str) and isinstance(target_value, str):
            # Check string length ratio (simple heuristic for potential issues)
            if len(source_value) > 10:  # Skip short strings
                ratio = len(target_value) / len(source_value)
                if ratio < 0.5 or ratio > 2.0:
                    click.echo(f"{Fore.YELLOW}Suspicious translation at {full_path}:{Fore.RESET}")
                    click.echo(f"  {source_lang}: {source_value}")
                    click.echo(f"  {target_lang}: {target_value}")
        elif type(source_value) != type(target_value):
            click.echo(f"{Fore.RED}Type mismatch at {full_path}:{Fore.RESET}")
            click.echo(f"  {source_lang} ({type(source_value).__name__}): {source_value}")
            click.echo(f"  {target_lang} ({type(target_value).__name__}): {target_value}") 