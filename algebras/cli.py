"""
Command-line interface for Algebras
"""

import os
import sys
import click
from colorama import init, Fore

from algebras.config import Config
from algebras.commands import init_command, add_command
from algebras.commands import translate_command, update_command
from algebras.commands import review_command, status_command

# Initialize colorama
init()

# Main CLI group
@click.group()
@click.version_option()
def cli():
    """Algebras CLI - Powerful AI-driven localization tool for your applications."""
    pass


@cli.command("init")
@click.option("--force", is_flag=True, help="Force initialization even if a config file exists.")
def init(force):
    """Initialize a new Algebras project."""
    init_command.execute(force)


@cli.command("add")
@click.argument("language", required=True)
def add(language):
    """Add a new language to your application."""
    add_command.execute(language)


@cli.command("translate")
@click.option("--language", "-l", help="Translate only the specified language.")
@click.option("--force", is_flag=True, help="Force translation even if files are up to date.")
@click.option("--only-missing", is_flag=True, help="Only translate keys that are missing in the target files.")
def translate(language, force, only_missing):
    """Translate your application."""
    translate_command.execute(language, force, only_missing)


@cli.command("update")
@click.option("--language", "-l", help="Update only the specified language.")
@click.option("--full", is_flag=True, help="Translate the entire file, not just missing keys.")
@click.option("--use-git", is_flag=True, help="Use git for key validation (slower but more thorough).")
def update(language, full, use_git):
    """Update your translations."""
    only_missing = not full
    update_command.execute(language, only_missing, not use_git)


@cli.command("review")
@click.option("--language", "-l", help="Review only the specified language.")
def review(language):
    """Review your translations."""
    review_command.execute(language)


@cli.command("status")
@click.option("--language", "-l", help="Show status only for the specified language.")
def status(language):
    """Check the status of your translations."""
    status_command.execute(language)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main() 