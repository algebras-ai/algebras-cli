"""
Gettext .po: placeholder syntax per entry, chosen from its `#,` flags.

| Flag                        | Syntaxes                         |
|-----------------------------|----------------------------------|
| c-format, objc-format,      | printf                           |
| php-format, javascript-...  |                                  |
| python-format               | python_percent + printf          |
| python-brace-format         | python_brace ({{ and }} literal) |
| qt-format, kde-format       | qt (%1 %2)                       |
| java-format, csharp-format  | icu_simple ({0}, {1,number})     |
| ruby-format                 | ruby                             |
| no-<lang>-format            | removes that family              |
| none of the above           | heuristic: printf + python_percent |

Why a per-entry profile here and a per-file one for translation: the translator resolves one
profile per file (profile_for_path), and one .po file mixes c-format, python-format and
python-brace-format entries. Translation therefore masks with the union PO_PROFILE (a value that
is not a placeholder for its entry is masked and put back unchanged, which is harmless), while
everything that decides whether a value is *accepted* uses the entry's own profile:

- the write gate in po_handler (check_value): a failing value is written as an empty msgstr,
  so gettext falls back to the source text;
- `algebras placeholders` (check_file, registered via register_file_check) and its in-place
  fix writer (write_fixes).

Plural entries: every msgstr[N] is checked against the plural text (msgid_plural, or the source
file's plural msgstr). A form that the target's Plural-Forms maps to a single count (n = 1 in
German, 0 / 1 / 2 in Arabic) may leave out the count, as msgfmt allows.

A `config placeholders:` override for the source file replaces the flag-based choice.
"""

import re
from functools import lru_cache
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from algebras.services.placeholders.engine import Problem, count_drop_allowed, extract, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import KeyPath, register_fix_writer
from algebras.services.placeholders.profiles import PlaceholderProfile, profile_for_path, register_profile
from algebras.services.placeholders.syntaxes import SYNTAXES, Syntax

# Python str.format fields: {} {0} {name} {0.attr} {name[key]} {0!r} {0:>10} {0:{width}}.
# "{{" and "}}" are matched too, so they consume their braces ("{{name}}" is literal text, not a
# field), and are then dropped from the placeholders via the profile's literal_values.
PYTHON_BRACE = Syntax(
    name="python_brace",
    kind="named",
    pattern=re.compile(
        r"\{\{|\}\}"
        r"|\{(?:\d+|[A-Za-z_][A-Za-z0-9_]*)?(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\]{}]*\])*"
        r"(?:![rsa])?(?::(?:[^{}]|\{[^{}]*\})*)?\}"
    ),
    # A translated field name ("{имя}"), not inside doubled braces.
    lenient=re.compile(r"(?<!\{)\{\s*[^\W\d][\w.]*\s*\}(?!\})"),
)
SYNTAXES.setdefault(PYTHON_BRACE.name, PYTHON_BRACE)

_BRACE_LITERALS = frozenset({"{{", "}}"})

_FLAG_SYNTAXES: Dict[str, Tuple[str, ...]] = {
    "c": ("printf",),
    "objc": ("printf",),
    "php": ("printf",),
    "perl": ("printf",),
    "javascript": ("printf",),
    "java-printf": ("printf",),
    "awk": ("printf",),
    "gcc-internal": ("printf",),
    "gfc-internal": ("printf",),
    "python": ("python_percent", "printf"),
    "python-brace": ("python_brace",),
    "qt": ("qt",),
    "qt-plural": ("qt",),
    "kde": ("qt",),
    "kde-kuit": ("qt",),
    "java": ("icu_simple",),
    "csharp": ("icu_simple",),
    "ruby": ("ruby", "printf"),
}

# No (positive) flag: what xgettext's heuristic would mark: printf, plus Python named
# placeholders (Django projects).
_HEURISTIC = ("python_percent", "printf")

# Translation masks with all of them (see module docstring).
PO_PROFILE = PlaceholderProfile(
    name="po",
    syntax_names=("python_percent", "printf", "python_brace", "qt"),
    literal_values=_BRACE_LITERALS,
)

_FORMAT_FLAG = re.compile(r"^(no-)?(.+)-format$")


@lru_cache(maxsize=None)
def profile_for_flags(flags: Tuple[str, ...]) -> PlaceholderProfile:
    """The placeholder profile of one entry, from its `#,` flags."""
    positive: List[str] = []
    negated: set = set()
    for flag in flags:
        m = _FORMAT_FLAG.match(flag.strip())
        if not m:
            continue
        family = _FLAG_SYNTAXES.get(m.group(2))
        if m.group(1):
            negated.update(family or ())
        elif family:
            positive.extend(family)

    if positive:
        names = positive
    else:
        names = [n for n in _HEURISTIC if n not in negated]
    names = tuple(dict.fromkeys(names))  # unique, in order
    literals = _BRACE_LITERALS if "python_brace" in names else frozenset()
    return PlaceholderProfile(name=f"po:{'+'.join(names) or 'none'}", syntax_names=names, literal_values=literals)


def _entry_flags(entry: Dict[str, Any], source_entry: Optional[Dict[str, Any]] = None) -> Tuple[str, ...]:
    """The target entry's flags, or the source entry's when the target has no format flag."""
    own = tuple(entry.get("flags") or ())
    if any(_FORMAT_FLAG.match(f) for f in own) or not source_entry:
        return own
    return own + tuple(f for f in source_entry.get("flags") or () if _FORMAT_FLAG.match(f))


def entry_profile(
    entry: Dict[str, Any],
    source_entry: Optional[Dict[str, Any]] = None,
    override: Optional[PlaceholderProfile] = None,
) -> PlaceholderProfile:
    return override or profile_for_flags(_entry_flags(entry, source_entry))


def single_count_drop(source: str, profile: PlaceholderProfile) -> FrozenSet[str]:
    """
    What a form used for a single count may leave out: the integer count (%d, %1$d) and, as msgfmt
    allows, named Python placeholders (%(counter)s, {count}), which do not shift other arguments.
    """
    named = {p.raw for p in extract(source, profile) if p.syntax in ("python_percent", "python_brace")}
    return count_drop_allowed(source, profile) | frozenset(named)


def reference_text(
    entry: Dict[str, Any],
    index: Optional[int],
    source_entry: Optional[Dict[str, Any]] = None,
) -> str:
    """
    The text a value is checked against. Singular: the source file's msgstr when filled in
    (msgid-as-key catalogs: msgid "welcome_title" / msgstr "Welcome, %(name)s"), else msgid.
    Plural forms: the plural text (source plural msgstr, else msgid_plural).
    """
    from algebras.utils.po_handler import source_plural_texts

    if index is None:
        if source_entry and isinstance(source_entry.get("msgstr"), str) and source_entry["msgstr"].strip():
            return source_entry["msgstr"]
        return entry.get("msgid") or ""
    base = source_entry if source_entry and source_entry.get("msgid_plural") is not None else {
        "msgid": entry.get("msgid"),
        "msgid_plural": entry.get("msgid_plural"),
    }
    return source_plural_texts(base)[1]


def check_value(
    entry: Dict[str, Any],
    index: Optional[int],
    value: str,
    source_entry: Optional[Dict[str, Any]] = None,
    plural_forms: Optional[Tuple[int, str]] = None,
    override: Optional[PlaceholderProfile] = None,
) -> Tuple[str, List[Problem]]:
    """(reference text, problems) for a msgstr (index None) or msgstr[index] value."""
    source, problems, _profile, _drop = _evaluate(entry, index, value, source_entry, plural_forms, override)
    return source, problems


def _evaluate(entry, index, value, source_entry, plural_forms, override):
    from algebras.utils.po_handler import plural_index_samples

    profile = entry_profile(entry, source_entry, override)
    source = reference_text(entry, index, source_entry)
    drop: FrozenSet[str] = frozenset()
    if index is not None and plural_forms:
        samples = plural_index_samples(*plural_forms)
        if index < len(samples) and len(samples[index]) == 1:
            drop = single_count_drop(source, profile)
    problems = _named_mismatch(verify(source, value, profile, drop))
    return source, problems, profile, drop


def _named_mismatch(problems: Sequence[Problem]) -> List[Problem]:
    """A missing %(name)s plus an unknown %(other)s is one problem: the name was changed."""
    is_named = lambda p: p.placeholder.startswith("%(")  # noqa: E731
    missing = [p for p in problems if p.code == "missing" and is_named(p)]
    extra = [p for p in problems if p.code == "extra" and is_named(p)]
    if not missing or not extra:
        return list(problems)
    pairs = list(zip(missing, extra))
    paired = {id(p) for pair in pairs for p in pair}
    result = [p for p in problems if id(p) not in paired]
    for m, e in pairs:
        result.append(
            Problem(
                "python_named_mismatch",
                e.placeholder,
                f"Placeholder name changed: {e.placeholder} should be {m.placeholder}",
            )
        )
    return result


def _config_override(source_file: str, config) -> Optional[PlaceholderProfile]:
    profile = profile_for_path(source_file, config)
    return profile if profile.name.startswith("config:") else None


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """Placeholder findings for every translated msgstr / msgstr[N] of a target .po file."""
    from algebras.utils.po_handler import (
        entry_key,
        file_plural_forms,
        plural_forms_for_language,
        plural_key,
        read_po_entries,
    )

    # Keyed like read_po_file: (msgctxt, msgid), so "Open" (verb) and "Open" (adjective) are
    # checked against their own source entries.
    source_by_key = {entry_key(e): e for e in read_po_entries(source_file) if e.get("msgid")}
    target_entries = read_po_entries(target_file)
    plural_forms = file_plural_forms(target_entries) or plural_forms_for_language(target_language)
    override = _config_override(source_file, config)

    findings: List[Finding] = []
    for entry in target_entries:
        if not entry.get("msgid"):
            continue
        base = entry_key(entry)
        source_entry = source_by_key.get(base)
        if entry.get("msgid_plural") is not None:
            values = [(i, v, plural_key(base, i)) for i, v in sorted((entry.get("msgstr_plural") or {}).items())]
        else:
            values = [(None, entry.get("msgstr"), base)]
        for index, value, key in values:
            if not isinstance(value, str) or not value.strip():
                continue  # untranslated: 'status' reports it
            source, problems, profile, drop = _evaluate(entry, index, value, source_entry, plural_forms, override)
            if problems:
                findings.append(
                    Finding(
                        key=key,
                        source=source,
                        target=value,
                        problems=problems,
                        path=(key,),
                        fixed=repair(source, value, profile, drop),
                    )
                )
    return findings


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: Optional[str] = None, config=None) -> None:
    """
    Write fixed values in place: only the fixed entries are re-serialized, every other line stays
    as it is. With the `po.mark_fuzzy` setting, fixed entries also get the fuzzy flag.
    """
    from algebras.utils.po_handler import update_po_values

    mark_fuzzy = False
    if config is not None:
        try:
            mark_fuzzy = bool(config.get_setting("po.mark_fuzzy", False))
        except Exception:
            mark_fuzzy = False
    not_found = update_po_values(target_file, {path[0]: value for path, value in fixes.items()}, mark_fuzzy)
    if not_found:
        raise ValueError(f"Could not find {', '.join(not_found)} in {target_file}")


register_profile([".po", ".pot"], PO_PROFILE)
register_file_check([".po"], check_file)
register_fix_writer([".po"], write_fixes)
