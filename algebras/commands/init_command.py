"""
Initialize a new Algebras project
"""

import os
import click
from colorama import Fore

from algebras.config import Config


def execute(force: bool = False, verbose: bool = False, provider: str = None, config_file: str = None) -> None:
    """
    Initialize a new Algebras project.
    
    Args:
        force: Force initialization even if a config file exists.
        verbose: Show detailed information about locale detection.
        provider: Set the default provider (e.g., 'algebras-ai')
        config_file: Path to custom config file (optional)
    """
    config = Config(config_file)
    
    if config.exists() and not force:
        click.echo(f"{Fore.YELLOW}Config file already exists. Use --force to overwrite.\x1b[0m")
        return
    
    click.echo(f"{Fore.GREEN}Initializing Algebras project...\x1b[0m")
    
    # Detect languages before creating config
    detected_languages = config.detect_languages_from_files(verbose=verbose)
    
    # Check for required environment variables
    # Since algebras-ai is now the default provider, check for its API key
    if not os.environ.get("ALGEBRAS_API_KEY") and (provider is None or provider == "algebras-ai"):
        click.echo(f"{Fore.YELLOW}Warning: ALGEBRAS_API_KEY environment variable is not set.\x1b[0m")
        click.echo(f"Set it with: export ALGEBRAS_API_KEY=your_api_key")
    
    # Create config with detected languages
    config.create_default()
    
    # Set the provider if specified
    if provider:
        config.load()
        if "api" not in config.data:
            config.data["api"] = {}
        
        if provider not in ["algebras-ai"]:
            click.echo(f"{Fore.RED}Invalid provider '{provider}'. Using default 'algebras-ai' instead.\x1b[0m")
        else:
            config.data["api"]["provider"] = provider
            
            # Check for required environment variables based on provider
            if provider == "algebras-ai" and not os.environ.get("ALGEBRAS_API_KEY"):
                click.echo(f"{Fore.YELLOW}Warning: ALGEBRAS_API_KEY environment variable is not set.\x1b[0m")
                click.echo(f"Set it with: export ALGEBRAS_API_KEY=your_api_key")
                
            click.echo(f"{Fore.GREEN}Using '{provider}' as the default provider.\x1b[0m")
        
        config.save()
    
    click.echo(f"{Fore.GREEN}✓ Created configuration file: \x1b[0m{config.config_path}")
    
    # Load the config to get the detected languages
    config.load()
    languages = config.get_languages()
    provider_name = config.data.get("api", {}).get("provider", "algebras-ai")
    
    if len(languages) > 1:
        click.echo(f"\nYour Algebras project has been initialized with the following languages: {', '.join(languages)}")
        if 'en' in languages:
            click.echo(f"Using English (en) as the source language.")
    else:
        click.echo(f"\nYour Algebras project has been initialized with English as the default language.")
    
    click.echo(f"Using {provider_name} as the translation provider.")
    click.echo(f"To add more languages, run: {Fore.BLUE}algebras add <language>\x1b[0m")
    click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m") 