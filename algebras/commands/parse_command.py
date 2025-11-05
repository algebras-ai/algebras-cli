"""
Parse codebase for hardcoded strings in JS/TS projects
"""

import os
import sys
import click
from colorama import Fore
from typing import Optional, List

from algebras.config import Config
from algebras.utils.js_ts_parser import parse_files, check_nodejs_available, check_dependencies_installed


def execute(input_patterns: Optional[List[str]] = None, ignore_patterns: Optional[List[str]] = None,
            verbose: bool = False, config_file: Optional[str] = None) -> None:
    """
    Parse codebase for hardcoded strings in JS/TS projects.
    
    Args:
        input_patterns: Glob patterns for source files to analyze
        ignore_patterns: Glob patterns for files/directories to ignore
        verbose: Show detailed output
        config_file: Path to custom config file (optional)
    """
    config = Config(config_file)
    
    # Check Node.js availability
    if not check_nodejs_available():
        click.echo(f"{Fore.RED}Error: Node.js is not available.{Fore.RESET}")
        click.echo(f"{Fore.YELLOW}Please install Node.js to use the parse command.{Fore.RESET}")
        click.echo(f"{Fore.BLUE}Visit: https://nodejs.org/{Fore.RESET}")
        sys.exit(1)
    
    if not check_dependencies_installed():
        click.echo(f"{Fore.RED}Error: Node.js dependencies are not installed.{Fore.RESET}")
        click.echo(f"{Fore.YELLOW}Please run: npm install (in algebras/utils/ directory){Fore.RESET}")
        sys.exit(1)
    
    # Load configuration if available
    parse_config = {}
    if config.exists():
        try:
            config.load()
            # Get parse configuration with defaults
            parse_config = {
                'extract': {
                    'transComponents': config.get_setting('parse.transComponents', ['Trans']),
                    'ignoredTags': config.get_setting('parse.ignoredTags', ['script', 'style', 'code']),
                    'ignoredAttributes': config.get_setting('parse.ignoredAttributes', [
                        'className', 'key', 'id', 'style', 'href', 'i18nKey', 
                        'defaults', 'type', 'target'
                    ])
                }
            }
            if verbose:
                click.echo(f"{Fore.BLUE}Loaded configuration from {config.config_path}{Fore.RESET}")
        except Exception as e:
            if verbose:
                click.echo(f"{Fore.YELLOW}Warning: Could not load config: {str(e)}{Fore.RESET}")
    
    # Get input patterns from config or CLI
    if not input_patterns:  # Empty list or None
        if config.exists():
            input_patterns = config.get_setting('parse.input', ['src/**/*.{js,jsx,ts,tsx}'])
        else:
            input_patterns = ['src/**/*.{js,jsx,ts,tsx}']
    
    # Get ignore patterns from config or CLI
    if not ignore_patterns:  # Empty list or None
        if config.exists():
            ignore_patterns = config.get_setting('parse.ignore', ['node_modules/**'])
        else:
            ignore_patterns = ['node_modules/**']
    
    if verbose:
        click.echo(f"{Fore.BLUE}Input patterns: {input_patterns}{Fore.RESET}")
        click.echo(f"{Fore.BLUE}Ignore patterns: {ignore_patterns}{Fore.RESET}")
    
    # Parse files
    if verbose:
        click.echo(f"{Fore.BLUE}Analyzing source files...{Fore.RESET}")
        click.echo(f"{Fore.BLUE}Calling Node.js parser with patterns: {input_patterns}{Fore.RESET}")
    
    success, message, files = parse_files(input_patterns, ignore_patterns, parse_config, verbose)
    
    if verbose:
        click.echo(f"{Fore.BLUE}Parser returned: success={success}, message={message}, files_count={len(files)}{Fore.RESET}")
    
    if not success and "error" in message.lower():
        # This is an error, not just issues found
        click.echo(f"{Fore.RED}{message}{Fore.RESET}")
        sys.exit(1)
    
    # Display results
    if files:
        total_issues = sum(len(issues) for issues in files.values())
        click.echo(f"\n{Fore.RED}{message}{Fore.RESET}")
        click.echo(f"{Fore.YELLOW}Found {total_issues} hardcoded strings in {len(files)} files{Fore.RESET}\n")
        
        # Print detailed report
        for file_path, issues in files.items():
            # Get relative path for cleaner display
            try:
                rel_path = os.path.relpath(file_path)
            except ValueError:
                rel_path = file_path
            
            click.echo(f"{Fore.YELLOW}{rel_path}{Fore.RESET}")
            for issue in issues:
                text = issue.get('text', '')
                line = issue.get('line', 0)
                click.echo(f"  {line}: {Fore.RED}Error:{Fore.RESET} Found hardcoded string: \"{text}\"")
        
        click.echo("")  # Empty line for spacing
        sys.exit(1)
    else:
        click.echo(f"{Fore.GREEN}{message}{Fore.RESET}")
        sys.exit(0)

