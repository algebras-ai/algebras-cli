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
from algebras.utils.i18n_detector import detect_framework
from algebras.utils.string_extractor import extract_strings_to_file
from algebras.utils.source_replacer import replace_strings_in_file


def execute(input_patterns: Optional[List[str]] = None, ignore_patterns: Optional[List[str]] = None,
            verbose: bool = False, config_file: Optional[str] = None, extract: bool = False,
            output: Optional[str] = None, key_prefix: Optional[str] = None, framework: Optional[str] = None,
            dry_run: bool = False, key_strategy: str = 'file-based') -> None:
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
        # Debug: Show all files found
        for file_path, issues in files.items():
            click.echo(f"{Fore.BLUE}  File: {file_path}, Issues: {len(issues)}{Fore.RESET}")
    
    if not success and "error" in message.lower():
        # This is an error, not just issues found
        click.echo(f"{Fore.RED}{message}{Fore.RESET}")
        sys.exit(1)
    
    # Display results - ALWAYS show files if they exist, regardless of success status
    if files:
        total_issues = sum(len(issues) for issues in files.values())
        click.echo(f"\n{Fore.RED}{message}{Fore.RESET}")
        click.echo(f"{Fore.YELLOW}Found {total_issues} hardcoded strings in {len(files)} files{Fore.RESET}\n")
        
        # Print detailed report - show EVERY string found (no deduplication, no filtering)
        issue_count = 0
        for file_path, issues in files.items():
            # Get relative path for cleaner display
            try:
                rel_path = os.path.relpath(file_path)
            except ValueError:
                rel_path = file_path
            
            click.echo(f"{Fore.YELLOW}{rel_path} ({len(issues)} issues){Fore.RESET}")
            # Show EVERY SINGLE ISSUE - no filtering, no skipping
            for issue in issues:
                issue_count += 1
                text = issue.get('text', '')
                line = issue.get('line', 0)
                # Show EVERY string individually (including duplicates, empty strings, everything)
                if not text:
                    text = "(empty string)"
                click.echo(f"  {issue_count}. Line {line}: {Fore.RED}Error:{Fore.RESET} Found hardcoded string: \"{text}\"")
        
        # Also print a summary list of all unique strings found (in verbose mode)
        if verbose:
            click.echo(f"\n{Fore.BLUE}Summary of all unique hardcoded strings found:{Fore.RESET}")
            all_strings = []
            for file_path, issues in files.items():
                for issue in issues:
                    text = issue.get('text', '')
                    if text and text not in all_strings:
                        all_strings.append(text)
            for i, text in enumerate(all_strings, 1):
                click.echo(f"  {i}. \"{text}\"")
        
        click.echo("")  # Empty line for spacing
        
        # Extract and replace if requested
        if extract:
            if verbose:
                click.echo(f"\n{Fore.BLUE}Extracting strings to translation file...{Fore.RESET}")
            
            # Get source language from config
            source_language = config.get_source_language() if config.exists() else 'en'
            
            # Get configuration
            extract_output = output or (config.get_setting('parse.extract.output') if config.exists() else None)
            extract_key_prefix = key_prefix or (config.get_setting('parse.extract.keyPrefix', '') if config.exists() else '')
            extract_key_strategy = key_strategy or (config.get_setting('parse.extract.keyStrategy', 'file-based') if config.exists() else 'file-based')
            
            # Detect or use specified framework
            from algebras.utils.i18n_detector import get_framework_config
            
            if framework:
                detected_framework = framework
                framework_config = get_framework_config(framework)
            else:
                detected_framework, framework_config = detect_framework(os.getcwd())
                if not detected_framework:
                    # Try config
                    detected_framework = config.get_setting('parse.extract.i18nFramework') if config.exists() else None
                    if detected_framework:
                        framework_config = get_framework_config(detected_framework)
                    else:
                        click.echo(f"{Fore.YELLOW}Warning: Could not auto-detect i18n framework. Using generic 't' function.{Fore.RESET}")
                        detected_framework = 'generic'
                        framework_config = get_framework_config('generic')
            
            if verbose:
                click.echo(f"{Fore.BLUE}Using framework: {detected_framework}{Fore.RESET}")
            
            # Extract strings to translation file
            try:
                key_mapping, translation_file = extract_strings_to_file(
                    files,
                    extract_output,
                    source_language,
                    extract_key_prefix,
                    extract_key_strategy,
                    os.getcwd(),
                    dry_run
                )
                
                if dry_run:
                    click.echo(f"{Fore.YELLOW}DRY RUN: Would create/update translation file: {translation_file}{Fore.RESET}")
                    click.echo(f"{Fore.YELLOW}DRY RUN: Would generate {len(key_mapping)} translation keys{Fore.RESET}")
                else:
                    click.echo(f"{Fore.GREEN}✓ Extracted {len(key_mapping)} strings to {translation_file}{Fore.RESET}")
                
                # Replace strings in source files
                if not dry_run:
                    if verbose:
                        click.echo(f"{Fore.BLUE}Replacing strings in source files...{Fore.RESET}")
                    
                    # Group replacements by file
                    replacements_by_file = {}
                    for (file_path, line_num, text), key in key_mapping.items():
                        if file_path not in replacements_by_file:
                            replacements_by_file[file_path] = []
                        replacements_by_file[file_path].append((line_num, text, key))
                    
                    # Replace in each file
                    files_modified = 0
                    for file_path, replacements in replacements_by_file.items():
                        try:
                            modified_content, has_changes = replace_strings_in_file(
                                file_path,
                                replacements,
                                detected_framework,
                                framework_config,
                                dry_run
                            )
                            if has_changes:
                                files_modified += 1
                                if verbose:
                                    click.echo(f"  {Fore.GREEN}✓ Modified {file_path}{Fore.RESET}")
                        except Exception as e:
                            click.echo(f"  {Fore.RED}Error replacing strings in {file_path}: {str(e)}{Fore.RESET}")
                    
                    if files_modified > 0:
                        click.echo(f"\n{Fore.GREEN}✓ Modified {files_modified} source files{Fore.RESET}")
                    else:
                        click.echo(f"\n{Fore.YELLOW}No files were modified{Fore.RESET}")
                
            except Exception as e:
                click.echo(f"{Fore.RED}Error during extraction: {str(e)}{Fore.RESET}")
                if verbose:
                    import traceback
                    traceback.print_exc()
        
        sys.exit(1)
    else:
        click.echo(f"{Fore.GREEN}{message}{Fore.RESET}")
        sys.exit(0)

