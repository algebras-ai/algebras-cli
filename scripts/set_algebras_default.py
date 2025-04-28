#!/usr/bin/env python3
"""
Script to set algebras-ai as the default provider globally
"""

import os
import sys
import subprocess
import click
from colorama import init, Fore

# Initialize colorama
init()

def main():
    """
    Set algebras-ai as the default provider globally
    """
    # Check if ALGEBRAS_API_KEY is set
    if not os.environ.get("ALGEBRAS_API_KEY"):
        click.echo(f"{Fore.RED}Error: ALGEBRAS_API_KEY environment variable is not set")
        click.echo(f"Please set it with: export ALGEBRAS_API_KEY=your_api_key{Fore.RESET}")
        sys.exit(1)
    
    try:
        # For existing configuration
        subprocess.run(
            ["algebras", "configure", "--provider", "algebras-ai"], 
            check=True
        )
        click.echo(f"{Fore.GREEN}✓ Successfully set algebras-ai as the default provider{Fore.RESET}")
    except subprocess.CalledProcessError:
        click.echo(f"{Fore.YELLOW}Warning: Could not configure existing project{Fore.RESET}")
    
    click.echo(f"\n{Fore.GREEN}For new projects, you can initialize with algebras-ai as the default provider:{Fore.RESET}")
    click.echo(f"{Fore.BLUE}  algebras init --provider algebras-ai{Fore.RESET}")

if __name__ == "__main__":
    main() 