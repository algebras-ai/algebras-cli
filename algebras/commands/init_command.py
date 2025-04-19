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
        click.echo(f"{Fore.YELLOW}Config file already exists. Use --force to overwrite.{Fore.RESET}")
        return
    
    click.echo(f"{Fore.GREEN}Initializing Algebras project...{Fore.RESET}")
    
    config.create_default()
    
    click.echo(f"{Fore.GREEN}✓ Created configuration file: {Fore.RESET}{config.config_path}")
    click.echo(f"\nYour Algebras project has been initialized with English as the default language.")
    click.echo(f"To add more languages, run: {Fore.BLUE}algebras add <language>{Fore.RESET}")
    click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status{Fore.RESET}") 