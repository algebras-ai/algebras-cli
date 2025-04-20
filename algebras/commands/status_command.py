"""
Check the status of your translations
"""

import os
import click
from typing import Optional, Dict, List

from algebras.config import Config
from algebras.services.file_scanner import FileScanner


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
        click.echo(click.style('-' * 80, fg='blue'))
        
        # Calculate expected file count for each language
        expected_file_counts = {lang: len(source_files) for lang in languages}
        
        # Print status for each language
        for lang in languages:
            if lang == source_language:
                continue
            
            lang_files = files_by_language.get(lang, [])
            file_count = len(lang_files)
            
            # Calculate percentage
            if expected_file_counts[lang] > 0:
                percentage = (file_count / expected_file_counts[lang]) * 100
            else:
                percentage = 0
            
            # Set color based on completion percentage
            if percentage >= 90:
                color = 'green'
            elif percentage >= 50:
                color = 'yellow'
            else:
                color = 'red'
            
            # Print status
            click.echo(f"{lang}: {click.style(f'{file_count}/{expected_file_counts[lang]} files ({percentage:.1f}%)', fg=color)}")
            
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