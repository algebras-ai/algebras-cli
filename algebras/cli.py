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
from algebras.commands import configure_command, glossary_push_command

# Initialize colorama
init()

# Main CLI group
@click.group()
@click.option('-f', '--config-file', type=click.Path(exists=False), help='Path to custom config file (default: .algebras.config)')
@click.pass_context
@click.version_option()
def cli(ctx, config_file):
    """Algebras CLI - Powerful AI-driven localization tool for your applications."""
    # Ensure ctx.obj exists and is a dict
    ctx.ensure_object(dict)
    # Store the config file path in context
    ctx.obj['config_file'] = config_file


@cli.command("init")
@click.option("--force", is_flag=True, help="Force initialization even if a config file exists.")
@click.option("--verbose", is_flag=True, help="Show detailed information about locale detection.")
@click.option("--provider", help="Set the default provider (e.g., 'algebras-ai').")
@click.pass_context
def init(ctx, force, verbose, provider):
    """Initialize a new Algebras project."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    init_command.execute(force, verbose, provider, config_file)


@cli.command("add")
@click.argument("language", required=True)
@click.pass_context
def add(ctx, language):
    """Add a new language to your application."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    add_command.execute(language, config_file)


@cli.command("translate")
@click.option("--language", "-l", help="Translate only the specified language.")
@click.option("--force", is_flag=True, help="Force translation even if files are up to date.")
@click.option("--only-missing", is_flag=True, help="Only translate keys that are missing in the target files.")
@click.option("--ui-safe", is_flag=True, help="Ensure translations will not exceed the original text length.")
@click.option("--verbose", is_flag=True, help="Show detailed logs of the translation process.")
@click.option("--batch-size", type=int, help="Override the batch size for translation processing (default: 20).")
@click.option("--max-parallel-batches", type=int, help="Override the maximum number of parallel batches for translation processing (default: 5).")
@click.option("--glossary-id", help="Glossary ID to use for Algebras AI translations.")
@click.option("--prompt-file", help="Path to a file containing a custom prompt for translation.")
@click.option("--regenerate-from-scratch", is_flag=True, help="Regenerate files from scratch instead of updating in-place (default: update in-place when target file exists).")
@click.pass_context
def translate(ctx, language, force, only_missing, ui_safe, verbose, batch_size, max_parallel_batches, glossary_id, prompt_file, regenerate_from_scratch):
    """Translate your application."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    translate_command.execute(language, force, only_missing, ui_safe=ui_safe, verbose=verbose, batch_size=batch_size, max_parallel_batches=max_parallel_batches, glossary_id=glossary_id, prompt_file=prompt_file, regenerate_from_scratch=regenerate_from_scratch, config_file=config_file)


@cli.command("update")
@click.option("--language", "-l", help="Update only the specified language.")
@click.option("--full", is_flag=True, help="Translate the entire file, not just missing keys.")
@click.option("--only-missing", is_flag=True, help="Only translate keys that are missing in the target files.")
@click.option("--ui-safe", is_flag=True, help="Ensure translations will not exceed the original text length.")
@click.option("--verbose", is_flag=True, help="Show detailed logs of the update process.")
@click.pass_context
def update(ctx, language, full, only_missing, ui_safe, verbose):
    """Update your translations."""
    # If both flags are provided, --only-missing takes precedence
    # If neither flag is provided, only_missing defaults to True (current behavior)
    only_missing_value = only_missing if only_missing else not full
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    update_command.execute(language, only_missing_value, skip_git_validation=only_missing, ui_safe=ui_safe, verbose=verbose, config_file=config_file)


@cli.command("ci")
@click.option("--language", "-l", help="Check only the specified language.")
@click.option("--verbose", is_flag=True, help="Show detailed logs of the check process.")
@click.option("--only-missing", is_flag=True, help="Only check for missing keys, ignore git validation for outdated keys.")
@click.pass_context
def ci(ctx, language, verbose, only_missing):
    """Run CI checks for translations (no translation, always uses git validation)."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    exit_code = update_command.execute_ci(language, verbose=verbose, only_missing=only_missing, config_file=config_file)
    sys.exit(exit_code)


@cli.command("review")
@click.option("--language", "-l", help="Review only the specified language.")
@click.pass_context
def review(ctx, language):
    """Review your translations."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    review_command.execute(language, config_file)


@cli.command("status")
@click.option("--language", "-l", help="Show status only for the specified language.")
@click.pass_context
def status(ctx, language):
    """Check the status of your translations."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    status_command.execute(language, config_file)


@cli.command("configure")
@click.option("--provider", help="Set the API provider (e.g., 'algebras-ai').")
@click.option("--model", help="Set the model for the provider (only applicable for some providers).")
@click.option("--path-rules", help="Set the path rules for file patterns to process (comma separated list or glob patterns).")
@click.option("--batch-size", type=int, help="Set the batch size for translation processing (default: 20).")
@click.option("--max-parallel-batches", type=int, help="Set the maximum number of parallel batches for translation processing (default: 5).")
@click.option("--glossary-id", help="Set the glossary ID for Algebras AI translations.")
@click.option("--prompt", help="Set a default prompt for translations.")
@click.option("--normalize-strings", type=bool, help="Enable/disable string normalization (removes escaped characters like \\').")
@click.pass_context
def configure(ctx, provider, model, path_rules, batch_size, max_parallel_batches, glossary_id, prompt, normalize_strings):
    """Configure your Algebras project settings."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    configure_command.execute(provider, model, path_rules, batch_size, max_parallel_batches, glossary_id, prompt, normalize_strings, config_file)


@cli.group("glossary")
def glossary():
    """Manage glossaries for translation."""
    pass


@glossary.command("push")
@click.argument("file", type=click.Path(exists=True))
@click.option("--name", required=True, help="Name of the glossary to create")
@click.option("--batch-size", default=100, type=int, help="Number of terms to upload per batch (default: 100)")
@click.option("--debug", is_flag=True, help="Enable debug mode to log all requests before sending")
@click.option("--rows-ids", help="Comma-separated list of row IDs (Record ID column) to include")
@click.option("--max-length", type=int, help="Maximum allowed length for a term; longer terms are skipped")
@click.pass_context
def glossary_push(ctx, file, name, batch_size, debug, rows_ids, max_length):
    """Upload glossary terms from CSV or XLSX file."""
    config_file = ctx.obj.get('config_file') if ctx.obj else None
    glossary_push_command.execute(file, name, batch_size=batch_size, debug=debug, rows_ids=rows_ids, max_length=max_length, config_file=config_file)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main() 