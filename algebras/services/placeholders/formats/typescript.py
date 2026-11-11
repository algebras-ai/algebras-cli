"""
TypeScript translation modules (.ts): `export const en = { key: '…', other: `…${expr}…` }`.

Like JSON, a TS module has no placeholder syntax of its own; the i18n library decides. The profile
is detected from the source module's values (i18next {{name}}, ICU {name}, printf %s, markup tags),
unless pinned in the config. Template literal substitutions (`Hi ${user.name}`) are JavaScript
expressions the app evaluates: they are masked as one token each (js_template) and must come back
byte-identical.

The writers (algebras/utils/ts_handler.py) escape every value for its literal's quote style, so a
translated apostrophe in a '…' value or a backtick / "${" in a `…` value cannot break the module or
add a substitution.

`algebras placeholders` checks every value like the default check, plus `ts_unparseable`: a target
module that does not parse. If it only breaks because of unescaped quotes inside values (an
apostrophe in 'Don't'), each such value is found by a lenient parse and reported with
ts_unparseable; its fix is the value written again with correct escaping (and placeholder repair
when needed). A module that cannot be read at all is reported once, without a fix.
"""

from typing import Any, Dict, Iterator, List, Optional, Tuple

from algebras.services.placeholders.engine import Problem, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import KeyPath, register_fix_writer
from algebras.services.placeholders.profiles import (
    GENERIC_PROFILE,
    PlaceholderProfile,
    detect_profile,
    profile_for_path,
    register_profile_resolver,
)

_EXTENSIONS = [".ts"]

# More specific syntaxes first: {{name}} is i18next, not ICU {name} in braces; ${x} is a template
# substitution, not "$" + ICU {x}.
TS_CANDIDATES = ("i18next", "xml_tag", "js_template", "icu_simple", "printf")

UNPARSEABLE = "ts_unparseable"
FILE_KEY = "(file)"


def _strings(data: Any) -> Iterator[str]:
    if isinstance(data, dict):
        for value in data.values():
            yield from _strings(value)
    elif isinstance(data, list):
        for value in data:
            yield from _strings(value)
    elif isinstance(data, str):
        yield data


def resolve_profile(file_path: str, config=None) -> PlaceholderProfile:
    from algebras.utils.ts_handler import read_ts_document

    try:
        doc = read_ts_document(file_path)
    except (OSError, ValueError):
        return GENERIC_PROFILE
    return detect_profile(_strings(doc.data), TS_CANDIDATES, "ts")


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def _get(data: Any, path: KeyPath) -> Any:
    for part in path:
        if isinstance(data, dict) and part in data:
            data = data[part]
        elif isinstance(data, list) and part.isdigit() and int(part) < len(data):
            data = data[int(part)]
        else:
            return None
    return data


def _source_strings(data: Any, prefix: KeyPath = ()) -> Iterator[Tuple[KeyPath, str]]:
    if isinstance(data, dict):
        for key, value in data.items():
            yield from _source_strings(value, prefix + (str(key),))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _source_strings(value, prefix + (str(index),))
    elif isinstance(data, str) and prefix:
        yield prefix, data


def repair_value(source: str, target: str, profile: PlaceholderProfile, drop_allowed=frozenset()) -> Optional[str]:
    fixed = repair(source, target, profile, drop_allowed)
    if fixed is None or verify(source, fixed, profile, drop_allowed):
        return None
    return fixed


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    from algebras.services.placeholders.plurals import drop_allowed_for_key
    from algebras.utils.ts_handler import TSParseError, read_ts_document

    source = read_ts_document(source_file)  # an unreadable source is skipped by the command
    profile = profile_for_path(source_file, config)

    try:
        target = read_ts_document(target_file)
        broken = {}
    except TSParseError as strict_error:
        try:
            target = read_ts_document(target_file, lenient=True)
        except TSParseError:
            return [
                Finding(
                    key=FILE_KEY,
                    source="",
                    target="",
                    problems=[Problem(UNPARSEABLE, "", f"The module does not parse: {strict_error}")],
                    path=(FILE_KEY,),
                )
            ]
        broken = target.recovered

    findings: List[Finding] = []
    for path, source_text in _source_strings(source.data):
        target_text = _get(target.data, path)
        if not isinstance(target_text, str) or (not target_text.strip() and path not in broken):
            continue  # untranslated: 'status' reports it
        key = ".".join(path)
        drop = drop_allowed_for_key(key, source_text, target_language, profile)
        problems = verify(source_text, target_text, profile, drop)
        fixed = repair_value(source_text, target_text, profile, drop) if problems else None
        if path in broken:
            quote = target.literals[path].quote
            problems = [
                Problem(UNPARSEABLE, quote, f"Unescaped {quote} inside the value breaks the module")
            ] + problems
            if fixed is None and len(problems) == 1:
                fixed = target_text  # only the escaping was wrong: write the same text, escaped
        if problems:
            findings.append(
                Finding(key=key, source=source_text, target=target_text, problems=problems, path=path, fixed=fixed)
            )

    # Broken values the source does not have: still report them, the module must parse.
    for path in broken:
        if _get(source.data, path) is None:
            text = _get(target.data, path)
            findings.append(
                Finding(
                    key=".".join(path),
                    source="",
                    target=text,
                    problems=[Problem(UNPARSEABLE, "", "Unescaped quote inside the value breaks the module")],
                    path=path,
                    fixed=text,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Fix writer
# ---------------------------------------------------------------------------


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: str = None, config=None) -> None:
    """
    Replace only the fixed values' literals, each escaped for its own quote style; the rest of the
    module stays byte-for-byte. Values with unescaped quotes are located by a lenient parse. The
    result must parse, or nothing is written.
    """
    from algebras.utils.ts_handler import TSParseError, _write_checked, parse_ts_module, replace_literals

    with open(target_file, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    try:
        doc = parse_ts_module(text)
    except TSParseError:
        doc = parse_ts_module(text, lenient=True)
    missing = [p for p in fixes if tuple(p) not in doc.literals]
    if missing:
        raise ValueError(f"Could not find {', '.join('.'.join(p) for p in missing)} in {target_file}")
    _write_checked(target_file, replace_literals(text, doc.literals, {tuple(p): v for p, v in fixes.items()}))


register_profile_resolver(_EXTENSIONS, resolve_profile)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
