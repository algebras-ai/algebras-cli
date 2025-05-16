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
from algebras.commands import configure_command

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
@click.option("--verbose", is_flag=True, help="Show detailed information about locale detection.")
@click.option("--provider", help="Set the default provider (e.g., 'openai', 'algebras-ai').")
def init(force, verbose, provider):
    """Initialize a new Algebras project."""
    init_command.execute(force, verbose, provider)


@cli.command("add")
@click.argument("language", required=True)
def add(language):
    """Add a new language to your application."""
    add_command.execute(language)


@cli.command("translate")
@click.option("--language", "-l", help="Translate only the specified language.")
@click.option("--force", is_flag=True, help="Force translation even if files are up to date.")
@click.option("--only-missing", is_flag=True, help="Only translate keys that are missing in the target files.")
@click.option("--ui-safe", is_flag=True, help="Ensure translations will not exceed the original text length.")
@click.option("--verbose", is_flag=True, help="Show detailed logs of the translation process.")
def translate(language, force, only_missing, ui_safe, verbose):
    """Translate your application."""
    translate_command.execute(language, force, only_missing, ui_safe=ui_safe, verbose=verbose)


@cli.command("update")
@click.option("--language", "-l", help="Update only the specified language.")
@click.option("--full", is_flag=True, help="Translate the entire file, not just missing keys.")
@click.option("--only-missing", is_flag=True, help="Only translate keys that are missing in the target files.")
@click.option("--ui-safe", is_flag=True, help="Ensure translations will not exceed the original text length.")
@click.option("--verbose", is_flag=True, help="Show detailed logs of the update process.")
def update(language, full, only_missing, ui_safe, verbose):
    """Update your translations."""
    # If both flags are provided, --only-missing takes precedence
    # If neither flag is provided, only_missing defaults to True (current behavior)
    only_missing_value = only_missing if only_missing else not full
    update_command.execute(language, only_missing_value, skip_git_validation=only_missing, ui_safe=ui_safe, verbose=verbose)


@cli.command("ci")
@click.option("--language", "-l", help="Check only the specified language.")
@click.option("--verbose", is_flag=True, help="Show detailed logs of the check process.")
@click.option("--only-missed-keys", is_flag=True, help="Only check for missing keys, ignore git validation for outdated keys.")
def ci(language, verbose, only_missed_keys):
    """Run CI checks for translations (no translation, always uses git validation)."""
    exit_code = update_command.execute_ci(language, verbose=verbose, only_missed_keys=only_missed_keys)
    sys.exit(exit_code)


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


@cli.command("configure")
@click.option("--provider", help="Set the API provider (e.g., 'openai', 'algebras-ai').")
@click.option("--model", help="Set the model for the provider (only applicable for some providers).")
@click.option("--path-rules", help="Set the path rules for file patterns to process (comma separated list or glob patterns).")
def configure(provider, model, path_rules):
    """Configure your Algebras project settings."""
    configure_command.execute(provider, model, path_rules)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main() 