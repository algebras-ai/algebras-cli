"""
Healthcheck command for validating translation quality
"""

import os
import json
import click
from colorama import Fore
from typing import Optional, Dict, Iterator, List, Tuple, Set
from collections import defaultdict

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.lang_validator import (
    align_target_data,
    extract_all_keys,
    get_key_value,
    read_language_file,
)
from algebras.utils.html_handler import read_html_file
from algebras.utils.translation_validator import validate_translation, placeholder_issues, Issue
from algebras.utils.path_utils import resolve_destination_path
from algebras.services.placeholders import profile_for_path


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
    
    # Show which languages will be checked
    if verbose:
        click.echo(f"\n{Fore.BLUE}Will check {len(languages_to_check)} language(s): {', '.join(languages_to_check)}{Fore.RESET}")
    
    # Scan for files
    try:
        scanner = FileScanner(config=config)
        files_by_language = scanner.group_files_by_language()
        
        if not files_by_language.get(source_language, []) and not scanner.multi_language_files():
            click.echo(click.style(f"No source files found for language '{source_language}'.", fg='yellow'))
            return 0
        
        # Collect all issues
        all_issues = []
        files_checked = 0
        keys_checked = 0
        keys_with_errors = set()
        keys_with_warnings = set()
        
        # Check each target language
        for target_lang in languages_to_check:
            if verbose:
                click.echo(f"\n{Fore.BLUE}Checking language: {target_lang}{Fore.RESET}")
            else:
                # Always show which language is being processed
                click.echo(f"{Fore.BLUE}Checking language: {target_lang}...{Fore.RESET}", nl=False)
            
            lang_files_checked = 0
            lang_keys_checked = 0

            for source_file, target_file in iter_file_pairs(
                config, source_language, target_lang, files_by_language, verbose
            ):
                # Validate file pair
                file_issues, file_keys, file_keys_with_errors, file_keys_with_warnings = validate_file_pair(
                    source_file, target_file, source_language, target_lang, config, verbose
                )
                all_issues.extend(file_issues)
                keys_checked += file_keys
                lang_keys_checked += file_keys
                keys_with_errors.update(file_keys_with_errors)
                keys_with_warnings.update(file_keys_with_warnings)
                if file_keys > 0:
                    files_checked += 1
                    lang_files_checked += 1

            # Show progress for each language
            if not verbose:
                click.echo(f" {lang_files_checked} files, {lang_keys_checked} keys")
        
        # Calculate keys that are okay (no errors or warnings)
        # A key can have both errors and warnings, so we need to account for the intersection
        keys_with_issues = len(keys_with_errors | keys_with_warnings)  # Union: keys with errors OR warnings
        keys_ok = keys_checked - keys_with_issues
        
        # Generate report
        if output_format == 'json':
            print_json_report(all_issues, files_checked, keys_checked, keys_ok, len(keys_with_errors), len(keys_with_warnings))
        else:
            print_console_report(all_issues, files_checked, keys_checked, keys_ok, len(keys_with_errors), len(keys_with_warnings), verbose)
        
        # Return exit code based on errors
        error_count = sum(1 for issue in all_issues if issue.severity == 'error')
        return 1 if error_count > 0 else 0
        
    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg='red'))
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def iter_file_pairs(
    config: Config,
    source_language: str,
    target_lang: str,
    files_by_language: Dict[str, List[str]],
    verbose: bool = False,
) -> Iterator[Tuple[str, str]]:
    """(source file, target file) pairs for one target language that both exist on disk."""
    source_files_config = config.get_source_files()
    if source_files_config:
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
            yield source_file, target_file
    else:
        source_files = files_by_language.get(source_language, [])
        for target_file in files_by_language.get(target_lang, []):
            source_file = find_source_file(target_file, source_files, source_language, target_lang)
            if source_file:
                yield source_file, target_file
        # Multi-language CSV / TSV: the same file is source and target (one column per language).
        from algebras.services.file_scanner import has_language_column

        for csv_file in FileScanner(config=config).multi_language_files():
            if has_language_column(csv_file, target_lang, config):
                yield csv_file, csv_file


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
        # Windows: scanned paths use backslashes (locales\ru\common.json)
        (f"{os.sep}{target_language}{os.sep}", f"{os.sep}{source_language}{os.sep}"),
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

    # Java resource bundles: messages_ru.properties falls back to the base bundle messages.properties
    suffix = f"_{target_language}.properties"
    if target_file.endswith(suffix):
        base = target_file[: -len(suffix)] + ".properties"
        if base in source_files or os.path.isfile(base):
            return base
    
    return None


def validate_file_pair(source_file: str, target_file: str, source_language: str,
                       target_language: str, config: Config, verbose: bool) -> Tuple[List[Issue], int, Set[str], Set[str]]:
    """
    Validate a pair of source and target files.

    Placeholders are checked by the format's registered file check when it has one (the check
    'algebras placeholders' runs: per-entry PO syntax from `#,` flags, .properties MessageFormat
    rules, .stringsdict metadata ...), so both commands report the same placeholder findings.
    Formatting, numbers, tags and tokens are checked per key for every format.

    Returns:
        Tuple of (list of issues, number of keys checked, keys with errors, keys with warnings)
    """
    issues: List[Issue] = []
    checked_keys: Set[str] = set()
    keys_with_errors: Set[str] = set()
    keys_with_warnings: Set[str] = set()
    if source_file.endswith('.xlsx'):
        from algebras.utils.xlsx_handler import is_glossary_xlsx

        if is_glossary_xlsx(source_file):
            return issues, 0, keys_with_errors, keys_with_warnings  # a glossary, not translations
    profile = profile_for_path(source_file, config)
    is_xliff = target_file.endswith(('.xlf', '.xliff'))

    def _record(key: str, key_issues: List[Issue]) -> None:
        issues.extend(key_issues)
        checked_keys.add(key)
        if any(i.severity == 'error' for i in key_issues):
            keys_with_errors.add(key)
        if any(i.severity == 'warning' for i in key_issues):
            keys_with_warnings.add(key)

    try:
        file_issues = _file_check_issues(source_file, target_file, source_language, target_language, config)
        check_placeholder_syntax = file_issues is None
        for key, key_issues in (file_issues or {}).items():
            _record(key, key_issues)

        def _check(key: str, source_value, target_value) -> None:
            # Only check translated (non-empty) string values
            if not isinstance(source_value, str) or not isinstance(target_value, str):
                return
            if not target_value or not target_value.strip():
                return
            _record(
                key,
                validate_translation(
                    source_value, target_value, key, is_xliff=is_xliff, profile=profile,
                    check_placeholder_syntax=check_placeholder_syntax,
                ),
            )

        # Read files based on format
        if source_file.endswith('.html'):
            source_data = read_html_file(source_file)
            target_data = read_html_file(target_file)
            for key in source_data:
                if key in target_data:
                    _check(key, source_data.get(key, ''), target_data.get(key, ''))
        else:
            # For CSV/TSV files, pass language parameters
            source_lang = source_language if source_file.endswith(('.csv', '.tsv', '.xlsx')) else None
            target_lang = target_language if target_file.endswith(('.csv', '.tsv', '.xlsx')) else None
            
            source_data = read_language_file(source_file, source_lang, config)
            target_data = read_language_file(target_file, target_lang, config)
            # Rails-style YAML: compare under each file's own root key (en.greeting ~ ru.greeting)
            target_data = align_target_data(
                source_file, source_data, target_data, source_language, target_language, config
            )
            
            # Handle flat dictionary formats
            if target_file.endswith(('.po', '.xml', '.strings', '.stringsdict', '.xlf', '.xliff', '.csv', '.tsv', '.arb', '.properties', '.xlsx')):
                for key in source_data:
                    if key in target_data:
                        _check(key, source_data.get(key, ''), target_data.get(key, ''))
            else:
                # Handle nested formats (JSON, YAML, TS)
                target_keys = extract_all_keys(target_data)
                for key in extract_all_keys(source_data):
                    if key in target_keys:
                        _check(key, get_key_value(source_data, key), get_key_value(target_data, key))
        
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
    
    return issues, len(checked_keys), keys_with_errors, keys_with_warnings


def _file_check_issues(
    source_file: str, target_file: str, source_language: str, target_language: str, config: Config
) -> Optional[Dict[str, List[Issue]]]:
    """
    Placeholder issues by key from the format's registered file check, or None when the format
    has none (or it cannot read the files): then placeholders are checked per key as before.
    """
    from algebras.services.placeholders.file_checks import get_file_check

    file_check = get_file_check(source_file)
    if file_check is None:
        return None
    try:
        findings = file_check(source_file, target_file, source_language, target_language, config)
    except Exception:
        return None
    by_key: Dict[str, List[Issue]] = {}
    for finding in findings:
        # The key path names the value the way the per-key checks do (Finding.key may be a
        # display name, e.g. "greet [Strings!C2]" for .xlsx).
        key = ".".join(finding.path) if finding.path else finding.key
        key_issues = placeholder_issues(finding.problems, key)
        if key_issues:
            by_key.setdefault(key, []).extend(key_issues)
    return by_key


def print_console_report(issues: List[Issue], files_checked: int, keys_checked: int, 
                        keys_ok: int, keys_with_errors_count: int, keys_with_warnings_count: int, verbose: bool):
    """Print console-formatted report."""
    if not issues:
        click.echo(f"\n{Fore.GREEN}✓ All translations passed validation!{Fore.RESET}")
        click.echo(f"  Files checked: {files_checked}")
        click.echo(f"  Keys checked: {keys_checked}")
        click.echo(f"  {Fore.GREEN}Keys OK: {keys_ok}{Fore.RESET}")
        return
    
    # Group issues by severity
    errors = [i for i in issues if i.severity == 'error']
    warnings = [i for i in issues if i.severity == 'warning']
    
    # Group by file and language (for multi-language files like TSV/CSV)
    issues_by_file_and_lang = defaultdict(list)
    for issue in issues:
        file_path = getattr(issue, 'file_path', 'unknown')
        language = getattr(issue, 'language', 'unknown')
        # Use tuple of (file_path, language) as key
        issues_by_file_and_lang[(file_path, language)].append(issue)
    
    # Print header
    click.echo(f"\n{Fore.RED}Translation Healthcheck Report{Fore.RESET}")
    click.echo("=" * 80)
    click.echo(f"Files checked: {files_checked}")
    click.echo(f"Keys checked: {keys_checked}")
    click.echo(f"  {Fore.GREEN}Keys OK: {keys_ok}{Fore.RESET}")
    click.echo(f"  {Fore.RED}Keys with errors: {keys_with_errors_count}{Fore.RESET}")
    click.echo(f"  {Fore.YELLOW}Keys with warnings: {keys_with_warnings_count}{Fore.RESET}")
    click.echo(f"{Fore.RED}Total errors: {len(errors)}{Fore.RESET}")
    click.echo(f"{Fore.YELLOW}Total warnings: {len(warnings)}{Fore.RESET}")
    click.echo("=" * 80)
    
    # Print issues grouped by file and language
    for (file_path, language), file_issues in sorted(issues_by_file_and_lang.items()):
        click.echo(f"\n{Fore.CYAN}{file_path} ({language}){Fore.RESET}")
        click.echo("-" * 80)
        
        # Group by category, then by key
        issues_by_category = defaultdict(lambda: defaultdict(list))
        for issue in file_issues:
            key = issue.key if issue.key else '(no key)'
            issues_by_category[issue.category][key].append(issue)
        
        for category in sorted(issues_by_category.keys()):
            category_issues_by_key = issues_by_category[category]
            category_name = category.replace('_', ' ').title()
            click.echo(f"\n  {Fore.MAGENTA}{category_name}:{Fore.RESET}")
            
            # Sort keys for consistent output
            for key in sorted(category_issues_by_key.keys()):
                key_issues = category_issues_by_key[key]
                # Show key if it exists
                if key != '(no key)':
                    click.echo(f"    {Fore.WHITE}Key: {key}{Fore.RESET}")
                
                # Show all issues for this key
                for issue in key_issues:
                    severity_color = Fore.RED if issue.severity == 'error' else Fore.YELLOW
                    severity_symbol = '✗' if issue.severity == 'error' else '⚠'
                    indent = "      " if key != '(no key)' else "    "
                    click.echo(f"{indent}{severity_color}{severity_symbol}{Fore.RESET} {issue.message}")
    
    # Print summary
    click.echo("\n" + "=" * 80)
    if errors:
        click.echo(f"{Fore.RED}✗ Found {len(errors)} error(s) that need to be fixed{Fore.RESET}")
    if warnings:
        click.echo(f"{Fore.YELLOW}⚠ Found {len(warnings)} warning(s){Fore.RESET}")
    if not errors and not warnings:
        click.echo(f"{Fore.GREEN}✓ No issues found{Fore.RESET}")
    
    # Print summary at the end for easy reference
    click.echo("\n" + "=" * 80)
    click.echo(f"{Fore.CYAN}Summary{Fore.RESET}")
    click.echo("=" * 80)
    click.echo(f"Files checked: {files_checked}")
    click.echo(f"Keys checked: {keys_checked}")
    click.echo(f"  {Fore.GREEN}Keys OK: {keys_ok}{Fore.RESET}")
    click.echo(f"  {Fore.RED}Keys with errors: {keys_with_errors_count}{Fore.RESET}")
    click.echo(f"  {Fore.YELLOW}Keys with warnings: {keys_with_warnings_count}{Fore.RESET}")
    click.echo(f"{Fore.RED}Total errors: {len(errors)}{Fore.RESET}")
    click.echo(f"{Fore.YELLOW}Total warnings: {len(warnings)}{Fore.RESET}")
    click.echo("=" * 80)


def print_json_report(issues: List[Issue], files_checked: int, keys_checked: int,
                     keys_ok: int, keys_with_errors_count: int, keys_with_warnings_count: int):
    """Print JSON-formatted report."""
    # Group issues by file and language (for multi-language files like TSV/CSV)
    issues_by_file_and_lang = defaultdict(list)
    for issue in issues:
        file_path = getattr(issue, 'file_path', 'unknown')
        language = getattr(issue, 'language', 'unknown')
        # Use tuple of (file_path, language) as key
        issues_by_file_and_lang[(file_path, language)].append(issue)
    
    # Build report structure
    report = {
        'summary': {
            'files_checked': files_checked,
            'keys_checked': keys_checked,
            'keys_ok': keys_ok,
            'keys_with_errors': keys_with_errors_count,
            'keys_with_warnings': keys_with_warnings_count,
            'total_issues': len(issues),
            'errors': sum(1 for i in issues if i.severity == 'error'),
            'warnings': sum(1 for i in issues if i.severity == 'warning')
        },
        'files': []
    }
    
    for (file_path, language), file_issues in sorted(issues_by_file_and_lang.items()):
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

