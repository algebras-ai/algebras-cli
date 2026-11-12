"""
iOS .stringsdict: placeholder profile, file check and in-place fix writer.

- Plural forms (zero/one/…/other) hold printf placeholders (%d, %ld, %@, %1$@).
- NSStringLocalizedFormatKey holds variable references (%#@items@) that name the plural dicts;
  a translated or damaged reference breaks the plural lookup.
- NSStringFormatSpecTypeKey / NSStringFormatValueTypeKey are metadata: never translated, and they
  must equal the source's.
"""

from typing import Dict, List, Optional

import click

from algebras.services.placeholders.engine import Problem, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import KeyPath, register_fix_writer
from algebras.services.placeholders.profiles import PlaceholderProfile, register_profile

# objc_variable first: "%#@items@" is one placeholder, not "%#@" plus text.
IOS_STRINGSDICT_PROFILE = PlaceholderProfile(name="ios_stringsdict", syntax_names=("objc_variable", "printf"))

_EXTENSIONS = [".stringsdict"]


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """Placeholder findings for a target .stringsdict: plural forms, missing CLDR forms, metadata."""
    from algebras.services.placeholders.plurals import drop_allowed_for_key
    from algebras.utils.ios_stringsdict_handler import (
        FORMAT_KEY,
        PLURAL_FORMS,
        TYPE_KEYS,
        _is_plural_rule_dict,
        find_plural_rule_dicts,
        fixed_format_key,
        format_key_problems,
        missing_plural_forms,
        plural_form_problems,
        plural_source_text,
        read_ios_stringsdict_file,
    )

    source_raw = read_ios_stringsdict_file(source_file)
    target_raw = read_ios_stringsdict_file(target_file)
    profile = IOS_STRINGSDICT_PROFILE
    findings: List[Finding] = []

    # Plural forms, including the ones the target language needs but the source lacks.
    target_plurals = dict(find_plural_rule_dicts(target_raw))
    for key, source_dict in find_plural_rule_dicts(source_raw):
        target_dict = target_plurals.get(key)
        if target_dict is None:
            continue  # untranslated entry: 'status' reports it
        for form in PLURAL_FORMS:
            target = target_dict.get(form)
            if not isinstance(target, str) or not target.strip():
                continue
            source, problems = plural_form_problems(source_dict, form, target, target_language)
            if problems:
                drop = drop_allowed_for_key(f"{key}.{form}", source, target_language, profile)
                findings.append(
                    Finding(f"{key}.{form}", source, target, problems, fixed=repair(source, target, profile, drop))
                )
        missing = missing_plural_forms(target_dict, target_language)
        for form in missing:
            findings.append(
                Finding(
                    f"{key}.{form}",
                    plural_source_text(source_dict, form, target_language) or "",
                    "",
                    [Problem("missing_form", form, f"{key}: missing plural forms {', '.join(missing)}")],
                )
            )

    # Format keys, type keys and any plain strings, walked alongside the source.
    def _walk(source: Dict, target: Dict, prefix: str, in_plural: bool) -> None:
        for name, source_value in source.items():
            key = f"{prefix}.{name}" if prefix else name
            target_value = target.get(name)
            if name in TYPE_KEYS and isinstance(source_value, str):
                if target_value == source_value:
                    continue
                if isinstance(target_value, str):
                    problem = Problem(
                        "type_key_mismatch",
                        target_value,
                        f"{name} is '{target_value}', source has '{source_value}' (metadata, never translated)",
                    )
                    findings.append(Finding(key, source_value, target_value, [problem], fixed=source_value))
                else:
                    problem = Problem("missing", source_value, f"{name} is missing (source has '{source_value}')")
                    findings.append(Finding(key, source_value, "", [problem]))
            elif name == FORMAT_KEY and isinstance(source_value, str) and isinstance(target_value, str):
                problems = format_key_problems(source_value, target_value)
                if problems:
                    findings.append(
                        Finding(key, source_value, target_value, problems, fixed=fixed_format_key(source_value, target_value))
                    )
            elif isinstance(source_value, dict) and isinstance(target_value, dict):
                _walk(source_value, target_value, key, _is_plural_rule_dict(source_value))
            elif (
                not in_plural
                and not name.startswith("NSString")
                and isinstance(source_value, str)
                and isinstance(target_value, str)
                and target_value.strip()
            ):
                problems = verify(source_value, target_value, profile)
                if problems:
                    findings.append(
                        Finding(key, source_value, target_value, problems, fixed=repair(source_value, target_value, profile))
                    )

    _walk(source_raw, target_raw, "", False)
    return findings


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: Optional[str] = None, config=None) -> None:
    """Write fixed values (plural forms or metadata) in place; the rest of the file stays as it is."""
    from algebras.utils.ios_stringsdict_handler import write_stringsdict_fixes

    not_found = write_stringsdict_fixes(target_file, {".".join(path): value for path, value in fixes.items()})
    for key in not_found:
        click.echo(f"  Could not find '{key}' in {target_file}; not fixed")


register_profile(_EXTENSIONS, IOS_STRINGSDICT_PROFILE)
register_fix_writer(_EXTENSIONS, write_fixes)
register_file_check(_EXTENSIONS, check_file)
