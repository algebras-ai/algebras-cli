"""
Add one or more languages to your application
"""

from typing import Iterable, Union

import click
from colorama import Fore

from algebras.config import Config


def execute(languages: Union[str, Iterable[str]], config_file: str = None) -> None:
    """
    Add one or more languages to your application.

    Args:
        languages: A language code or a list of language codes to add (e.g., 'fr' or ['es', 'fr', 'de']).
        config_file: Path to custom config file (optional)
    """
    if isinstance(languages, str):
        languages = [languages]

    # Normalize and de-duplicate, preserving order
    requested = list(dict.fromkeys(language.lower() for language in languages))

    # Validate every code before touching the config, so a typo adds nothing
    invalid = [language for language in requested if len(language) < 2]
    if invalid:
        click.echo(f"{Fore.RED}Invalid language code. Please use a valid ISO language code (e.g., 'fr', 'es').\x1b[0m")
        if len(requested) > 1:
            click.echo(f"{Fore.RED}Invalid: {', '.join(repr(language) for language in invalid)}. No languages were added.\x1b[0m")
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

    existing = config.get_languages()
    added = []
    for language in requested:
        if language in existing:
            click.echo(f"{Fore.YELLOW}Language '{language}' is already configured.\x1b[0m")
            continue

        click.echo(f"{Fore.GREEN}Adding language '{language}' to your project...\x1b[0m")
        config.add_language(language)
        added.append(language)
        click.echo(f"{Fore.GREEN}✓ Language '{language}' has been added to your project.\x1b[0m")

    if not added:
        return

    click.echo(f"\nTo start translating, run: {Fore.BLUE}algebras translate\x1b[0m")
    click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m")
