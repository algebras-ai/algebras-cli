"""
Healthcheck command for validating translation quality
"""

import os
import json
import click
from colorama import Fore
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.lang_validator import read_language_file, extract_all_keys, get_key_value
from algebras.utils.html_handler import read_html_file
from algebras.utils.translation_validator import validate_translation, Issue
from algebras.utils.path_utils import resolve_destination_path


def execute(language: Optional[str] = None, output_format: str = 'console', 
            verbose: bool = False, config_file: str = None) -> int:
    """
    Execute healthcheck command to validate translations.
    
    Args:
        language: Language to check (if None, check all languages)
        output_format: Output format ('console' or 'json')
        verbose: Show detailed information
        config_file: Path to custom config file (optional)
        
    Returns:
        Exit code (0 if no errors, 1 if errors found)
    """
    config = Config(config_file)
    
    if not config.exists():
        click.echo(click.style("No Algebras configuration found. Run 'algebras init' first.", fg='red'))
        return 1
    
    # Load configuration
    config.load()
    
    # Get source language
    source_language = config.get_source_language()
    
    # Get languages to check
    all_languages = config.get_languages()
    if language:
        if language not in all_languages:
            click.echo(click.style(f"Language '{language}' is not configured in your project.", fg='red'))
            return 1
        languages_to_check = [language]
    else:
        languages_to_check = [lang for lang in all_languages if lang != source_language]
    
    if not languages_to_check:
        click.echo(click.style("No target languages to check.", fg='yellow'))
        return 0
    
    # Scan for files
    try:
        scanner = FileScanner(config=config)
        files_by_language = scanner.group_files_by_language()
        
        # Get source files
        source_files = files_by_language.get(source_language, [])
        if not source_files:
            click.echo(click.style(f"No source files found for language '{source_language}'.", fg='yellow'))
            return 0
        
        # Collect all issues
        all_issues = []
        files_checked = 0
        keys_checked = 0
        
        # Check each target language
        for target_lang in languages_to_check:
            if verbose:
                click.echo(f"\n{Fore.BLUE}Checking language: {target_lang}{Fore.RESET}")
            
            # Get target files
            target_files = files_by_language.get(target_lang, [])
            
            # Match source files with target files
            source_files_config = config.get_source_files()
            
            if source_files_config:
                # Use source_files configuration
                for source_file, source_config in source_files_config.items():
                    if not os.path.isfile(source_file):
                        continue
                    
                    destination_pattern = source_config.get("destination_path", "")
                    if not destination_pattern:
                        continue
                    
                    target_file = resolve_destination_path(destination_pattern, target_lang, config)
                    
                    if not os.path.isfile(target_file):
                        if verbose:
                            click.echo(f"  {Fore.YELLOW}Skipping {source_file} - target file not found: {target_file}{Fore.RESET}")
                        continue
                    
                    # Validate file pair
                    file_issues, file_keys = validate_file_pair(
                        source_file, target_file, source_language, target_lang, config, verbose
                    )
                    all_issues.extend(file_issues)
                    keys_checked += file_keys
                    if file_keys > 0:
                        files_checked += 1
            else:
                # Fallback to filename-based matching
                for target_file in target_files:
                    # Find corresponding source file
                    source_file = find_source_file(target_file, source_files, source_language, target_lang)
                    if not source_file:
                        continue
                    
                    # Validate file pair
                    file_issues, file_keys = validate_file_pair(
                        source_file, target_file, source_language, target_lang, config, verbose
                    )
                    all_issues.extend(file_issues)
                    keys_checked += file_keys
                    if file_keys > 0:
                        files_checked += 1
        
        # Generate report
        if output_format == 'json':
            print_json_report(all_issues, files_checked, keys_checked)
        else:
            print_console_report(all_issues, files_checked, keys_checked, verbose)
        
        # Return exit code based on errors
        error_count = sum(1 for issue in all_issues if issue.severity == 'error')
        return 1 if error_count > 0 else 0
        
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg='red'))
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def find_source_file(target_file: str, source_files: List[str], 
                    source_language: str, target_language: str) -> Optional[str]:
    """Find corresponding source file for a target file."""
    target_basename = os.path.basename(target_file)
    target_dirname = os.path.dirname(target_file)
    
    # Try to find source file by replacing language markers
    patterns = [
        (f".{target_language}.", f".{source_language}."),
        (f"-{target_language}.", f"-{source_language}."),
        (f"_{target_language}.", f"_{source_language}."),
        (f"/{target_language}/", f"/{source_language}/"),
    ]
    
    for target_pattern, source_pattern in patterns:
        if target_pattern in target_file:
            potential_source = target_file.replace(target_pattern, source_pattern)
            if potential_source in source_files:
                return potential_source
    
    # Try directory-based matching (e.g., values-es -> values)
    if target_file.endswith('.xml'):
        parts = target_file.split(os.path.sep)
        for i, part in enumerate(parts):
            if part.startswith('values-') and part != 'values':
                # Replace with 'values'
                potential_parts = parts.copy()
                potential_parts[i] = 'values'
                potential_source = os.path.sep.join(potential_parts)
                if potential_source in source_files:
                    return potential_source
    
    return None


def validate_file_pair(source_file: str, target_file: str, source_language: str,
                       target_language: str, config: Config, verbose: bool) -> Tuple[List[Issue], int]:
    """
    Validate a pair of source and target files.
    
    Returns:
        Tuple of (list of issues, number of keys checked)
    """
    issues = []
    keys_checked = 0
    
    try:
        # Read files based on format
        if source_file.endswith('.html'):
            source_data = read_html_file(source_file)
            target_data = read_html_file(target_file)
            source_keys = set(source_data.keys())
            target_keys = set(target_data.keys())
            
            # Check all keys that exist in both and are translated
            for key in source_keys:
                if key in target_keys:
                    source_value = source_data.get(key, '')
                    target_value = target_data.get(key, '')
                    
                    # Only check if target is translated (non-empty)
                    if target_value and target_value.strip():
                        key_issues = validate_translation(source_value, target_value, key)
                        issues.extend(key_issues)
                        keys_checked += 1
        else:
            # For CSV/TSV files, pass language parameters
            source_lang = source_language if source_file.endswith(('.csv', '.tsv')) else None
            target_lang = target_language if target_file.endswith(('.csv', '.tsv')) else None
            
            source_data = read_language_file(source_file, source_lang, config)
            target_data = read_language_file(target_file, target_lang, config)
            
            # Handle flat dictionary formats
            if target_file.endswith(('.po', '.xml', '.strings', '.stringsdict', '.xlf', '.xliff', '.csv', '.tsv')):
                source_keys = set(source_data.keys())
                target_keys = set(target_data.keys())
                
                # Check all keys that exist in both and are translated
                for key in source_keys:
                    if key in target_keys:
                        source_value = source_data.get(key, '')
                        target_value = target_data.get(key, '')
                        
                        # Only check if target is translated (non-empty)
                        if target_value and target_value.strip():
                            key_issues = validate_translation(source_value, target_value, key)
                            issues.extend(key_issues)
                            keys_checked += 1
            else:
                # Handle nested formats (JSON, YAML, TS)
                source_keys = extract_all_keys(source_data)
                target_keys = extract_all_keys(target_data)
                
                # Check all keys that exist in both and are translated
                for key in source_keys:
                    if key in target_keys:
                        source_value = get_key_value(source_data, key)
                        target_value = get_key_value(target_data, key)
                        
                        # Only check string values that are translated
                        if isinstance(source_value, str) and isinstance(target_value, str):
                            if target_value and target_value.strip():
                                key_issues = validate_translation(source_value, target_value, key)
                                issues.extend(key_issues)
                                keys_checked += 1
        
        # Add file context to issues
        for issue in issues:
            if not hasattr(issue, 'file_path'):
                issue.file_path = target_file
                issue.source_file = source_file
                issue.language = target_language
        
    except Exception as e:
        if verbose:
            click.echo(f"  {Fore.RED}Error validating {target_file}: {str(e)}{Fore.RESET}")
        # Add error issue
        error_issue = Issue('error', 'system', f'Failed to validate file: {str(e)}', None)
        error_issue.file_path = target_file
        error_issue.source_file = source_file
        error_issue.language = target_language
        issues.append(error_issue)
    
    return issues, keys_checked


def print_console_report(issues: List[Issue], files_checked: int, keys_checked: int, verbose: bool):
    """Print console-formatted report."""
    if not issues:
        click.echo(f"\n{Fore.GREEN}✓ All translations passed validation!{Fore.RESET}")
        click.echo(f"  Files checked: {files_checked}")
        click.echo(f"  Keys checked: {keys_checked}")
        return
    
    # Group issues by severity
    errors = [i for i in issues if i.severity == 'error']
    warnings = [i for i in issues if i.severity == 'warning']
    
    # Group by file
    issues_by_file = defaultdict(list)
    for issue in issues:
        file_path = getattr(issue, 'file_path', 'unknown')
        issues_by_file[file_path].append(issue)
    
    # Print header
    click.echo(f"\n{Fore.RED}Translation Healthcheck Report{Fore.RESET}")
    click.echo("=" * 80)
    click.echo(f"Files checked: {files_checked}")
    click.echo(f"Keys checked: {keys_checked}")
    click.echo(f"{Fore.RED}Errors: {len(errors)}{Fore.RESET}")
    click.echo(f"{Fore.YELLOW}Warnings: {len(warnings)}{Fore.RESET}")
    click.echo("=" * 80)
    
    # Print issues grouped by file
    for file_path, file_issues in sorted(issues_by_file.items()):
        language = getattr(file_issues[0], 'language', 'unknown')
        click.echo(f"\n{Fore.CYAN}{file_path} ({language}){Fore.RESET}")
        click.echo("-" * 80)
        
        # Group by category
        issues_by_category = defaultdict(list)
        for issue in file_issues:
            issues_by_category[issue.category].append(issue)
        
        for category in sorted(issues_by_category.keys()):
            category_issues = issues_by_category[category]
            category_name = category.replace('_', ' ').title()
            click.echo(f"\n  {Fore.MAGENTA}{category_name}:{Fore.RESET}")
            
            for issue in category_issues:
                severity_color = Fore.RED if issue.severity == 'error' else Fore.YELLOW
                severity_symbol = '✗' if issue.severity == 'error' else '⚠'
                key_info = f" [{issue.key}]" if issue.key else ""
                click.echo(f"    {severity_color}{severity_symbol}{Fore.RESET} {issue.message}{key_info}")
    
    # Print summary
    click.echo("\n" + "=" * 80)
    if errors:
        click.echo(f"{Fore.RED}✗ Found {len(errors)} error(s) that need to be fixed{Fore.RESET}")
    if warnings:
        click.echo(f"{Fore.YELLOW}⚠ Found {len(warnings)} warning(s){Fore.RESET}")
    if not errors and not warnings:
        click.echo(f"{Fore.GREEN}✓ No issues found{Fore.RESET}")


def print_json_report(issues: List[Issue], files_checked: int, keys_checked: int):
    """Print JSON-formatted report."""
    # Group issues by file
    issues_by_file = defaultdict(list)
    for issue in issues:
        file_path = getattr(issue, 'file_path', 'unknown')
        issues_by_file[file_path].append(issue)
    
    # Build report structure
    report = {
        'summary': {
            'files_checked': files_checked,
            'keys_checked': keys_checked,
            'total_issues': len(issues),
            'errors': sum(1 for i in issues if i.severity == 'error'),
            'warnings': sum(1 for i in issues if i.severity == 'warning')
        },
        'files': []
    }
    
    for file_path, file_issues in sorted(issues_by_file.items()):
        language = getattr(file_issues[0], 'language', 'unknown')
        file_report = {
            'file': file_path,
            'language': language,
            'issues': []
        }
        
        for issue in file_issues:
            file_report['issues'].append({
                'severity': issue.severity,
                'category': issue.category,
                'message': issue.message,
                'key': issue.key
            })
        
        report['files'].append(file_report)
    
    print(json.dumps(report, indent=2, ensure_ascii=False))

