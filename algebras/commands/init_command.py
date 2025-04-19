"""
Initialize a new Algebras project
"""

import os
import click
from colorama import Fore

from algebras.config import Config


def execute(force: bool = False) -> None:
    """
    Initialize a new Algebras project.
    
    Args:
        force: Force initialization even if a config file exists.
    """
    config = Config()
    
    if config.exists() and not force:
        click.echo(f"{Fore.YELLOW}Config file already exists. Use --force to overwrite.\x1b[0m")
        return
    
    click.echo(f"{Fore.GREEN}Initializing Algebras project...\x1b[0m")
    
    config.create_default()
    
    click.echo(f"{Fore.GREEN}✓ Created configuration file: \x1b[0m{config.config_path}")
    click.echo(f"\nYour Algebras project has been initialized with English as the default language.")
    click.echo(f"To add more languages, run: {Fore.BLUE}algebras add <language>\x1b[0m")
    click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m") 