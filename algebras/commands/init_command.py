"""
Initialize a new Algebras project
"""

import os
import click
from colorama import Fore

from algebras.config import Config


def execute(force: bool = False, verbose: bool = False) -> None:
    """
    Initialize a new Algebras project.
    
    Args:
        force: Force initialization even if a config file exists.
        verbose: Show detailed information about locale detection.
    """
    config = Config()
    
    if config.exists() and not force:
        click.echo(f"{Fore.YELLOW}Config file already exists. Use --force to overwrite.\x1b[0m")
        return
    
    click.echo(f"{Fore.GREEN}Initializing Algebras project...\x1b[0m")
    
    # Detect languages before creating config
    detected_languages = config.detect_languages_from_files(verbose=verbose)
    
    # Create config with detected languages
    config.create_default()
    
    click.echo(f"{Fore.GREEN}✓ Created configuration file: \x1b[0m{config.config_path}")
    
    # Load the config to get the detected languages
    config.load()
    languages = config.get_languages()
    
    if len(languages) > 1:
        click.echo(f"\nYour Algebras project has been initialized with the following languages: {', '.join(languages)}")
        if 'en' in languages:
            click.echo(f"Using English (en) as the source language.")
    else:
        click.echo(f"\nYour Algebras project has been initialized with English as the default language.")
    
    click.echo(f"To add more languages, run: {Fore.BLUE}algebras add <language>\x1b[0m")
    click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m") 