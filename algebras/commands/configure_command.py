"""
Configure settings for your Algebras project
"""

import os
import click
from colorama import Fore

from algebras.config import Config


def execute(provider: str = None, model: str = None) -> None:
    """
    Configure your Algebras project settings.
    
    Args:
        provider: Set the API provider (e.g., 'openai', 'algebras-ai')
        model: Set the model for the provider (only applicable for some providers)
    """
    config = Config()
    
    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return
    
    # Load configuration
    config.load()
    
    # Initialize API configuration if it doesn't exist
    if "api" not in config.data:
        config.data["api"] = {}
    
    # Get current provider
    current_provider = config.data["api"].get("provider", "algebras-ai")
    
    # Handle provider change
    if provider:
        # Validate provider
        if provider not in ["openai", "algebras-ai"]:
            click.echo(f"{Fore.RED}Invalid provider. Supported providers are 'openai' and 'algebras-ai'.\x1b[0m")
            return
        
        # Check for required environment variables based on provider
        if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
            click.echo(f"{Fore.YELLOW}Warning: OPENAI_API_KEY environment variable is not set.\x1b[0m")
            click.echo(f"Set it with: export OPENAI_API_KEY=your_api_key")
        
        if provider == "algebras-ai" and not os.environ.get("ALGEBRAS_API_KEY"):
            click.echo(f"{Fore.YELLOW}Warning: ALGEBRAS_API_KEY environment variable is not set.\x1b[0m")
            click.echo(f"Set it with: export ALGEBRAS_API_KEY=your_api_key")
        
        # Update provider
        config.data["api"]["provider"] = provider
        click.echo(f"{Fore.GREEN}Provider set to '{provider}'.\x1b[0m")
    
    # Handle model change
    if model:
        config.data["api"]["model"] = model
        click.echo(f"{Fore.GREEN}Model set to '{model}'.\x1b[0m")
    
    # If no arguments provided, show current configuration
    if not provider and not model:
        click.echo(f"\nCurrent configuration:")
        click.echo(f"  Provider: {Fore.BLUE}{current_provider}\x1b[0m")
        click.echo(f"  Model: {Fore.BLUE}{config.data['api'].get('model', 'Not set')}\x1b[0m")
        
        click.echo(f"\nTo change the provider, run: {Fore.BLUE}algebras configure --provider <provider>\x1b[0m")
        click.echo(f"To change the model, run: {Fore.BLUE}algebras configure --model <model>\x1b[0m")
        return
    
    # Save configuration
    config.save() 