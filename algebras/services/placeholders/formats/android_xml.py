"""
Android string resources (res/values*/**.xml).

- printf: Java Formatter specifiers (%s, %1$d, %.2f, %tY, %n, %%).
- android_xliff_g: an <xliff:g> element with its content is one atomic token, so the model never
  sees (and cannot translate) "%1$s" or the example text inside it.
- xml_tag: other inline markup (<b>, <i>, <a href>, <annotation>) as separate open/close tokens;
  the text between them is translated.
- android_escape: \\uXXXX, and \\@ / \\? escapes.

Strings marked formatted="false" use the profile without printf (their % signs are literal).
Placeholder fixes are written in place, changing only the fixed strings or plural items.
"""

import re
from typing import Dict, List

from algebras.services.placeholders.engine import repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.profiles import PlaceholderProfile, profile_for_path, register_profile
from algebras.services.placeholders.syntaxes import SYNTAXES, Syntax

ANDROID_XLIFF_G = Syntax(
    name="android_xliff_g",
    kind="atomic",
    pattern=re.compile(r"<xliff:g\b[^<>]*?/>|<xliff:g\b[^<>]*>.*?</xliff:g\s*>", re.DOTALL),
)

ANDROID_ESCAPE = Syntax(
    name="android_escape",
    kind="escape",
    pattern=re.compile(r"\\u[0-9A-Fa-f]{4}|\\[@?]"),
)

for _syntax in (ANDROID_XLIFF_G, ANDROID_ESCAPE):
    SYNTAXES.setdefault(_syntax.name, _syntax)

ANDROID_PROFILE = PlaceholderProfile(
    name="android",
    syntax_names=("android_xliff_g", "printf", "xml_tag", "android_escape"),
)


def _unformatted(profile: PlaceholderProfile) -> PlaceholderProfile:
    return PlaceholderProfile(
        name=f"{profile.name}:unformatted",
        syntax_names=tuple(n for n in profile.syntax_names if n != "printf"),
        literal_values=profile.literal_values,
    )


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """
    Placeholder findings for a target strings file.

    Like the default key-by-key check, plus:
    - strings with formatted="false" are checked without printf (their % signs are literal);
    - every target plural item is checked against the text it is translated from: the source
      'other' for forms the source lacks (ru few/many) and for multi-count forms whose source
      text has no count placeholder (en one = "One point" -> ru one = "%1$d очко");
    - a translated <plurals> that lacks a CLDR form the target language needs is `missing_form`
      (not fixable in place; --retranslate regenerates the group with every form).
    """
    from algebras.services.placeholders.plurals import drop_allowed_for_key, missing_form_problem
    from algebras.utils.android_plurals import PLURALS_SUFFIX, plural_source_text
    from algebras.utils.plural_rules import get_plural_categories
    from algebras.utils.android_xml_handler import read_android_string_attributes, read_android_xml_file

    source = read_android_xml_file(source_file)
    target = read_android_xml_file(target_file)
    file_profile = profile_for_path(source_file, config)
    attributes = read_android_string_attributes(source_file)

    def profile_for(path):
        formatted = (attributes.get(path, {}).get("formatted") or "").strip().lower()
        return _unformatted(file_profile) if formatted == "false" else file_profile

    pairs = []  # (key path, source text, target text)
    missing_forms: List[Finding] = []
    for key, value in source.items():
        if isinstance(value, dict) and key.endswith(PLURALS_SUFFIX):
            target_dict = target.get(key)
            if not isinstance(target_dict, dict):
                continue
            for form, target_text in target_dict.items():
                source_text = plural_source_text(value, form, target_language)
                if source_text is not None:
                    pairs.append(((key, form), source_text, target_text))
            present = [f for f, t in target_dict.items() if isinstance(t, str) and t.strip()]
            if present:
                for form in get_plural_categories(target_language):
                    if form not in present:
                        missing_forms.append(
                            Finding(
                                key=f"{key}.{form}",
                                source=plural_source_text(value, form, target_language) or "",
                                target="",
                                problems=[missing_form_problem(form, target_language)],
                                path=(key, form),
                            )
                        )
        elif isinstance(value, str):
            pairs.append(((key,), value, target.get(key)))

    findings: List[Finding] = []
    for path, source_text, target_text in pairs:
        if not isinstance(target_text, str) or not target_text.strip():
            continue  # untranslated: 'status' reports it
        key = ".".join(path)
        profile = profile_for(path)
        drop = drop_allowed_for_key(key, source_text, target_language, profile)
        problems = verify(source_text, target_text, profile, drop)
        if problems:
            findings.append(
                Finding(
                    key=key,
                    source=source_text,
                    target=target_text,
                    problems=problems,
                    path=path,
                    fixed=repair(source_text, target_text, profile, drop),
                )
            )
    return findings + missing_forms


def write_fixes(target_file: str, fixes: Dict[tuple, str], language: str = None, config=None) -> None:
    from algebras.utils.android_xml_handler import update_android_xml_values

    not_found = update_android_xml_values(target_file, fixes)
    if not_found:
        raise ValueError(
            f"Could not find {', '.join('.'.join(p) for p in not_found)} in {target_file}"
        )


register_profile([".xml"], ANDROID_PROFILE)
register_file_check([".xml"], check_file)
register_fix_writer([".xml"], write_fixes)
