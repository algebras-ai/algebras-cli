"""
Add a new language to your application
"""

import os
import click
from colorama import Fore

from algebras.config import Config


def execute(language: str, config_file: str = None) -> None:
    """
    Add a new language to your application.
    
    Args:
        language: Language code to add (e.g., 'fr', 'es', 'de').
        config_file: Path to custom config file (optional)
    """
    # Validate language code
    language = language.lower()
    
    # Check if language code is valid (simplified check)
    if len(language) < 2:
        click.echo(f"{Fore.RED}Invalid language code. Please use a valid ISO language code (e.g., 'fr', 'es').\x1b[0m")
        return
    
    config = Config(config_file)
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return
    
    # Load configuration
    config.load()
    
    # Check for deprecated config format
    if config.check_deprecated_format():
        click.echo(f"{Fore.RED}🚨 ⚠️  WARNING: Your configuration uses the deprecated 'path_rules' format! ⚠️ 🚨{Fore.RESET}")
        click.echo(f"{Fore.RED}🔴 Please update to the new 'source_files' format.{Fore.RESET}")
        click.echo(f"{Fore.RED}📖 See documentation: https://github.com/algebras-ai/algebras-cli{Fore.RESET}")
    
    # Check if language already exists
    languages = config.get_languages()
    if language in languages:
        click.echo(f"{Fore.YELLOW}Language '{language}' is already configured.\x1b[0m")
        return
    
    # Add language
    click.echo(f"{Fore.GREEN}Adding language '{language}' to your project...\x1b[0m")
    config.add_language(language)
    
    click.echo(f"{Fore.GREEN}✓ Language '{language}' has been added to your project.\x1b[0m")
    click.echo(f"\nTo start translating, run: {Fore.BLUE}algebras translate\x1b[0m")
    click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m") 