"""
Check that translations keep their placeholders, and fix them.

    algebras placeholders [-l LANG ...] [--fix] [--retranslate] [--dry-run] [--format console|json]

Exit codes: 0 = no issues (or all fixed), 1 = issues found (check only), 2 = issues left after fixing.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import click
from colorama import Fore

from algebras.commands.healthcheck_command import iter_file_pairs
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.services.placeholders import profile_for_path, repair, verify
from algebras.services.placeholders.file_checks import get_file_check
from algebras.services.placeholders.fix_writers import get_fix_writer
from algebras.services.placeholders.plurals import drop_allowed_for_key
from algebras.utils.lang_validator import read_language_file

KeyPath = Tuple[str, ...]

_FIXABLE_CODES = {"missing", "extra", "corrupted", "count_mismatch", "reordered", "tags_unbalanced"}


@dataclass
class KeyIssue:
    language: str
    source_file: str
    target_file: str
    key: str
    source: str
    target: str
    problems: List[Dict[str, str]]
    path: KeyPath = field(default=(), repr=False)
    fixed: Optional[str] = None
    status: str = "open"  # open | fixed | unresolved | unsupported


def iter_strings(data: Any, prefix: KeyPath = ()) -> Iterator[Tuple[KeyPath, str]]:
    """(key path, value) for every string in a parsed language file, plural dicts included."""
    if isinstance(data, dict):
        for key, value in data.items():
            yield from iter_strings(value, prefix + (str(key),))
    elif isinstance(data, str) and prefix:
        yield prefix, data


def _get(data: Any, path: KeyPath) -> Any:
    for part in path:
        if not isinstance(data, dict) or part not in data:
            return None
        data = data[part]
    return data


def check_file_pair(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config: Config,
) -> List[KeyIssue]:
    file_check = get_file_check(source_file)
    if file_check is not None:
        # The format compares its files itself (e.g. .stringsdict plural forms and metadata).
        return [
            KeyIssue(
                language=target_language,
                source_file=source_file,
                target_file=target_file,
                key=f.key,
                source=f.source,
                target=f.target,
                problems=[{"code": p.code, "placeholder": p.placeholder, "message": p.message} for p in f.problems],
                path=f.path or (f.key,),
                fixed=f.fixed,
            )
            for f in file_check(source_file, target_file, source_language, target_language, config)
        ]

    multi_language = source_file.endswith((".csv", ".tsv"))
    source_data = read_language_file(source_file, source_language if multi_language else None, config)
    target_data = read_language_file(target_file, target_language if multi_language else None, config)
    profile = profile_for_path(source_file, config)

    issues: List[KeyIssue] = []
    for path, source in iter_strings(source_data):
        target = _get(target_data, path)
        if not isinstance(target, str) or not target.strip():
            continue  # untranslated: 'status' reports it
        key = ".".join(path)
        drop = drop_allowed_for_key(key, source, target_language, profile)
        problems = verify(source, target, profile, drop)
        if not problems:
            continue
        issues.append(
            KeyIssue(
                language=target_language,
                source_file=source_file,
                target_file=target_file,
                key=key,
                source=source,
                target=target,
                problems=[{"code": p.code, "placeholder": p.placeholder, "message": p.message} for p in problems],
                path=path,
                fixed=repair(source, target, profile, drop),
            )
        )
    return issues


def _force_key(path: KeyPath, source_data_top: Dict[str, Any]) -> str:
    # Plural groups stored under one top-level key (Android "name.__plurals__") are retranslated whole.
    if len(path) == 2 and isinstance(source_data_top.get(path[0]), dict):
        return path[0]
    return ".".join(path)


def execute(
    languages: Optional[Sequence[str]] = None,
    fix: bool = False,
    retranslate: bool = False,
    dry_run: bool = False,
    output_format: str = "console",
    config_file: Optional[str] = None,
) -> int:
    config = Config(config_file)
    if not config.exists():
        click.echo(click.style("No Algebras configuration found. Run 'algebras init' first.", fg="red"))
        return 1
    config.load()

    source_language = config.get_source_language()
    all_languages = config.get_languages()
    if languages:
        unknown = [l for l in languages if l not in all_languages]
        if unknown:
            click.echo(click.style(f"Language(s) not configured in your project: {', '.join(unknown)}", fg="red"))
            return 1
        target_languages = list(languages)
    else:
        target_languages = [l for l in all_languages if l != source_language]

    files_by_language = FileScanner(config=config).group_files_by_language()
    console = output_format != "json"

    all_issues: List[KeyIssue] = []
    skipped: List[Tuple[str, str]] = []
    files_checked = 0
    for language in target_languages:
        for source_file, target_file in iter_file_pairs(config, source_language, language, files_by_language):
            try:
                issues = check_file_pair(source_file, target_file, source_language, language, config)
            except Exception as e:  # unreadable or unsupported format
                skipped.append((target_file, str(e)))
                continue
            files_checked += 1
            all_issues.extend(issues)

    if fix and all_issues:
        _apply_fixes(all_issues, dry_run, config, console)
        if retranslate and not dry_run:
            _retranslate(all_issues, source_language, config, config_file, console)

    if console:
        _print_console(all_issues, files_checked, skipped, fix, dry_run)
    else:
        click.echo(
            json.dumps(
                {
                    "files_checked": files_checked,
                    "skipped": [{"file": f, "reason": r} for f, r in skipped],
                    "issues": [
                        {k: v for k, v in asdict(i).items() if k != "path"} for i in all_issues
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if not all_issues:
        return 0
    if not fix or dry_run:
        return 1
    return 0 if all(i.status == "fixed" for i in all_issues) else 2


def _apply_fixes(issues: List[KeyIssue], dry_run: bool, config: Config, console: bool) -> None:
    by_file: Dict[Tuple[str, str], List[KeyIssue]] = {}
    for issue in issues:
        by_file.setdefault((issue.target_file, issue.language), []).append(issue)

    for (target_file, language), file_issues in by_file.items():
        fixable = [i for i in file_issues if i.fixed is not None]
        writer = get_fix_writer(target_file)
        if dry_run:
            if console and fixable:
                note = "" if writer else f" {Fore.YELLOW}(writing fixes is not supported for this format yet){Fore.RESET}"
                click.echo(f"\n{Fore.BLUE}Would fix {len(fixable)} value(s) in {target_file}:{Fore.RESET}{note}")
                for i in fixable:
                    click.echo(f"  {i.key}")
                    click.echo(f"    {Fore.RED}- {i.target}{Fore.RESET}")
                    click.echo(f"    {Fore.GREEN}+ {i.fixed}{Fore.RESET}")
            continue
        for i in file_issues:
            if i.fixed is None:
                i.status = "unresolved"
        if not fixable:
            continue
        if writer is None:
            for i in fixable:
                i.status = "unsupported"
            continue
        writer(target_file, {i.path: i.fixed for i in fixable}, language, config)
        for i in fixable:
            i.status = "fixed"


def _retranslate(
    issues: List[KeyIssue], source_language: str, config: Config, config_file: Optional[str], console: bool
) -> None:
    from algebras.commands import translate_command

    keys_by_language: Dict[str, set] = {}
    for issue in issues:
        if issue.status == "fixed":
            continue
        source_data = read_language_file(
            issue.source_file,
            source_language if issue.source_file.endswith((".csv", ".tsv")) else None,
            config,
        )
        keys_by_language.setdefault(issue.language, set()).add(
            _force_key(issue.path, source_data if isinstance(source_data, dict) else {})
        )

    for language, keys in keys_by_language.items():
        if console:
            click.echo(f"\n{Fore.BLUE}Retranslating {len(keys)} key(s) for {language}...{Fore.RESET}")
        translate_command.execute(language=language, force=",".join(sorted(keys)), config_file=config_file)

    # Re-check the retranslated keys.
    for issue in issues:
        if issue.status == "fixed" or issue.language not in keys_by_language:
            continue
        try:
            rechecked = check_file_pair(issue.source_file, issue.target_file, source_language, issue.language, config)
        except Exception:
            continue
        if not any(r.key == issue.key for r in rechecked):
            issue.status = "fixed"


def _print_console(
    issues: List[KeyIssue], files_checked: int, skipped: List[Tuple[str, str]], fix: bool, dry_run: bool
) -> None:
    for target_file, reason in skipped:
        click.echo(f"{Fore.YELLOW}Skipped {target_file}: {reason}{Fore.RESET}")

    current_file = None
    for issue in issues:
        if issue.target_file != current_file:
            current_file = issue.target_file
            click.echo(f"\n{Fore.BLUE}{issue.target_file}{Fore.RESET} ({issue.language})")
        status = "" if issue.status == "open" else f" [{issue.status}]"
        click.echo(f"  {Fore.YELLOW}{issue.key}{Fore.RESET}{status}")
        for p in issue.problems:
            click.echo(f"    - {p['code']}: {p['message']}")
        click.echo(f"    source: {issue.source}")
        click.echo(f"    target: {issue.target}")
        if issue.fixed is not None and issue.status == "open":
            click.echo(f"    {Fore.GREEN}auto-fix: {issue.fixed}{Fore.RESET}")

    fixable = sum(1 for i in issues if i.fixed is not None)
    click.echo(
        f"\nChecked {files_checked} file(s): {len(issues)} value(s) with placeholder issues"
        + (f", {fixable} fixable without retranslation" if issues else "")
    )
    if issues and fix and not dry_run:
        counts: Dict[str, int] = {}
        for i in issues:
            counts[i.status] = counts.get(i.status, 0) + 1
        click.echo("  " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        if counts.get("unsupported"):
            click.echo(
                f"  {Fore.YELLOW}Automatic fixing is not available for some file formats yet.{Fore.RESET}"
            )
        if counts.get("unresolved"):
            click.echo("  Run with --retranslate to retranslate the values that could not be fixed.")
    elif issues and not fix:
        click.echo("Run 'algebras placeholders --fix' to repair them (add --dry-run to preview).")
