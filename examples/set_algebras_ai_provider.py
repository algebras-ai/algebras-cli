#!/usr/bin/env python3
"""
Script to set algebras-ai as the default provider
"""

import os
import click
from colorama import init, Fore

from algebras.config import Config

# Initialize colorama
init()

def main():
    """
    Set algebras-ai as the default provider
    """
    # Make sure ALGEBRAS_API_KEY environment variable is set
    if not os.environ.get("ALGEBRAS_API_KEY"):
        click.echo(f"{Fore.RED}Error: ALGEBRAS_API_KEY environment variable not set")
        click.echo(f"Please set it with: export ALGEBRAS_API_KEY=your_api_key{Fore.RESET}")
        return
    
    # Create a sample configuration
    config = Config()
    
    # Create a new configuration if it doesn't exist
    if not config.exists():
        config.create_default()
        click.echo(f"{Fore.GREEN}Created default configuration{Fore.RESET}")
    
    # Update the configuration to use Algebras AI provider
    config.load()
    if "api" not in config.data:
        config.data["api"] = {}
    
    config.data["api"]["provider"] = "algebras-ai"
    config.save()
    
    click.echo(f"{Fore.GREEN}✓ Set Algebras AI as the default translation provider in configuration{Fore.RESET}")
    click.echo(f"\nNow you can run translations using the Algebras AI provider:")
    click.echo(f"{Fore.BLUE}  algebras translate{Fore.RESET}")

if __name__ == "__main__":
    main() 