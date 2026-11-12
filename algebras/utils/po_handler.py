"""
.po (gettext) localization file handler

Reading returns a flat {key: text} dictionary:

- a singular entry is keyed by its msgid, or by "<msgctxt>\x04<msgid>" when it has a msgctxt
  (entry_key / split_entry_key; gettext joins them the same way in compiled catalogs), so the same
  msgid under two contexts ("Open" the verb and "Open" the adjective) is two keys;
- a plural entry (msgid_plural + msgstr[N]) contributes one key per form, "<entry key>::msgstr[N]"
  (see plural_key / split_plural_key). Form N means what the file's Plural-Forms header says,
  so a Russian target has msgstr[0..2] while the English source has msgstr[0..1];
  expand_plural_source maps the source onto the target's forms.

Writing keeps the file layout: entries that did not change are copied byte-for-byte (comments,
`#,` flags, line wrapping), changed entries are re-serialized in place, and new entries are
appended. Before a translated value is written it goes through the placeholder gate
(algebras.services.placeholders.formats.po): a value whose placeholders do not match its msgid
for the entry's `#,` flags is written as an empty msgstr, so gettext falls back to the source.
"""

import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Plural keys and Plural-Forms
# ---------------------------------------------------------------------------

_PLURAL_KEY_RE = re.compile(r"^(.*)::msgstr\[(\d+)\]$", re.DOTALL)
CONTEXT_SEPARATOR = "\x04"  # EOT, as in gettext's compiled catalogs; never part of a msgid


def entry_key(entry: Dict[str, Any]) -> str:
    """Key of an entry: its msgid, prefixed with "<msgctxt>\x04" when it has a msgctxt."""
    msgid = entry.get("msgid") or ""
    msgctxt = entry.get("msgctxt")
    return f"{msgctxt}{CONTEXT_SEPARATOR}{msgid}" if msgctxt else msgid


def split_entry_key(key: str) -> Tuple[Optional[str], str]:
    """(msgctxt or None, msgid) for an entry key (without a plural suffix)."""
    if CONTEXT_SEPARATOR in key:
        msgctxt, msgid = key.split(CONTEXT_SEPARATOR, 1)
        return msgctxt, msgid
    return None, key


def display_key(key: str) -> str:
    """A key for messages: "msgid" or "msgid [msgctxt: ...]"."""
    split = split_plural_key(key)
    base, suffix = (split[0], f"::msgstr[{split[1]}]") if split else (key, "")
    msgctxt, msgid = split_entry_key(base)
    return f"{msgid}{suffix}" + (f" [msgctxt: {msgctxt}]" if msgctxt is not None else "")
_DEFAULT_PLURAL_FORMS = (2, "(n != 1)")
_SAMPLE_RANGE = 1001


def plural_key(msgid: str, index: int) -> str:
    """Flat key of one plural form: "<entry key>::msgstr[<index>]"."""
    return f"{msgid}::msgstr[{index}]"


def split_plural_key(key: str) -> Optional[Tuple[str, int]]:
    """(msgid, index) for a plural-form key, None for a singular key."""
    if not isinstance(key, str):
        return None
    m = _PLURAL_KEY_RE.match(key)
    return (m.group(1), int(m.group(2))) if m else None


def parse_plural_forms(header: str) -> Optional[Tuple[int, str]]:
    """(nplurals, plural expression) from a header msgstr, or None."""
    m = re.search(r"^Plural-Forms:\s*(.*)$", header or "", re.MULTILINE | re.IGNORECASE)
    if not m:
        return None
    value = m.group(1)
    n = re.search(r"nplurals\s*=\s*(\d+)", value)
    expr = re.search(r"plural\s*=\s*(.+?)\s*;?\s*$", value)
    if not n or not expr:
        return None
    return int(n.group(1)), expr.group(1).strip().rstrip(";").strip()


def plural_forms_for_language(language: Optional[str]) -> Tuple[int, str]:
    """Standard gettext Plural-Forms for a language (Babel's table), English-like if unknown."""
    if not language:
        return _DEFAULT_PLURAL_FORMS
    try:
        from babel.messages.plurals import get_plural

        plural = get_plural(language.replace("-", "_"))
        return plural.num_plurals, plural.plural_expr
    except Exception:
        return _DEFAULT_PLURAL_FORMS


@lru_cache(maxsize=None)
def plural_index_samples(nplurals: int, expr: str) -> Tuple[Tuple[int, ...], ...]:
    """For each msgstr index, the counts 0..1000 that select it."""
    import gettext

    samples: List[List[int]] = [[] for _ in range(max(nplurals, 1))]
    try:
        func = gettext.c2py(expr)
    except Exception:
        func = gettext.c2py(_DEFAULT_PLURAL_FORMS[1])
    for n in range(_SAMPLE_RANGE):
        try:
            index = int(func(n))
        except Exception:
            continue
        if 0 <= index < len(samples):
            samples[index].append(n)
    return tuple(tuple(s) for s in samples)


def covers_single_count(samples: Tuple[int, ...]) -> bool:
    return len(samples) == 1


def describe_counts(samples: Tuple[int, ...], limit: int = 8) -> str:
    shown = ", ".join(str(n) for n in samples[:limit])
    return shown + ("…" if len(samples) > limit else "")


def file_plural_forms(entries: List[Dict[str, Any]]) -> Optional[Tuple[int, str]]:
    header = next((e for e in entries if _is_header(e)), None)
    return parse_plural_forms(header["msgstr"]) if header else None


def read_po_plural_forms(file_path: str) -> Optional[Tuple[int, str]]:
    if not file_path or not os.path.exists(file_path):
        return None
    return file_plural_forms(read_po_entries(file_path))


def source_plural_texts(entry: Dict[str, Any], source_forms: Optional[Tuple[int, str]] = None) -> Tuple[str, str]:
    """
    (singular text, plural text) a plural entry is translated from: the source file's msgstr for
    one / for most counts when filled in, otherwise msgid / msgid_plural.
    """
    msgid = entry.get("msgid") or ""
    msgid_plural = entry.get("msgid_plural") or msgid
    forms = entry.get("msgstr_plural") or {}
    nplurals, expr = source_forms or _DEFAULT_PLURAL_FORMS
    samples = plural_index_samples(nplurals, expr)
    singular_index = next((i for i, s in enumerate(samples) if 1 in s), 0)
    plural_index = max(range(len(samples)), key=lambda i: len(samples[i])) if samples else 0
    singular = forms.get(singular_index) or msgid
    plural = forms.get(plural_index) or msgid_plural
    return singular, plural


def expand_plural_source(
    source_file: str,
    source_data: Dict[str, Any],
    target_language: Optional[str],
    target_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Source data with each plural entry's keys replaced by the forms the target needs (the target
    file's Plural-Forms, else the target language's). A form that covers only n = 1 is translated
    from the singular text; every other form (several counts, or a single count other than 1) from
    the plural text, which carries the count placeholder the form needs.
    """
    entries = read_po_entries(source_file)
    plural_entries = [e for e in entries if e.get("msgid_plural") is not None and e.get("msgid")]
    if not plural_entries:
        return source_data
    target_forms = read_po_plural_forms(target_file) if target_file else None
    nplurals, expr = target_forms or plural_forms_for_language(target_language)
    samples = plural_index_samples(nplurals, expr)
    source_forms = file_plural_forms(entries)

    expanded = {k: v for k, v in source_data.items() if not split_plural_key(k)}
    for entry in plural_entries:
        singular, plural = source_plural_texts(entry, source_forms)
        for index in range(nplurals):
            expanded[plural_key(entry_key(entry), index)] = singular if samples[index] == (1,) else plural
    return expanded


def plural_index_categories(
    nplurals: int, expr: str, language: Optional[str]
) -> Tuple[Optional[str], ...]:
    """
    For each msgstr index, the CLDR category (one/few/many/other ...) of the counts it covers,
    or None when unknown or mixed (the counts fall into several categories, or none).
    """
    from algebras.utils.plural_rules import _plural_rule

    rule = _plural_rule(language) if language else None
    categories: List[Optional[str]] = []
    for counts in plural_index_samples(nplurals, expr):
        found = {rule(n) for n in counts} if rule is not None else set()
        categories.append(found.pop() if len(found) == 1 else None)
    return tuple(categories)


def plural_anchor_index(nplurals: int, expr: str, language: Optional[str]) -> int:
    """
    The msgstr index translated first and quoted to the other forms: the one form that maps to
    CLDR 'other', or the last form when the mapping is ambiguous (Russian: integers 5..20 are
    'many', so msgstr[2]).
    """
    categories = plural_index_categories(nplurals, expr, language)
    others = [i for i, c in enumerate(categories) if c == "other"]
    return others[0] if len(others) == 1 else max(nplurals - 1, 0)


def context_note(msgctxt: str) -> str:
    """Translator note for an entry with a msgctxt."""
    return (
        f"gettext context (msgctxt): '{msgctxt}'. The same source text may appear under other "
        "contexts with a different meaning; translate it for this context."
    )


def build_plural_contexts(
    source_file: str,
    source_language: str,
    target_language: str,
    target_file: Optional[str] = None,
) -> Dict[str, str]:
    """
    Translator notes: for every target plural-form key, which counts it covers; for every entry
    with a msgctxt, the context. The result's `anchors` (PluralContexts) map each form to its
    entry's anchor form (plural_anchor_index), which is translated first and quoted in the other
    forms' notes; a singular key with a context note is its own anchor.
    """
    from algebras.utils.ios_stringsdict_handler import PluralContexts
    from algebras.utils.plural_rules import get_language_name

    entries = read_po_entries(source_file)
    contexts = PluralContexts()
    for entry in entries:
        if entry.get("msgid") and entry.get("msgctxt") and entry.get("msgid_plural") is None:
            key = entry_key(entry)
            contexts[key] = context_note(entry["msgctxt"])
            contexts.anchors[key] = key

    plural_entries = [e for e in entries if e.get("msgid_plural") is not None and e.get("msgid")]
    if not plural_entries:
        return contexts if contexts else {}
    target_forms = read_po_plural_forms(target_file) if target_file else None
    nplurals, expr = target_forms or plural_forms_for_language(target_language)
    samples = plural_index_samples(nplurals, expr)
    source_forms = file_plural_forms(entries)
    target_name = get_language_name(target_language)
    source_name = get_language_name(source_language)

    anchor_index = plural_anchor_index(nplurals, expr, target_language)
    for entry in plural_entries:
        singular, plural = source_plural_texts(entry, source_forms)
        base = entry_key(entry)
        for index in range(nplurals):
            contexts.anchors[plural_key(base, index)] = plural_key(base, anchor_index)
            counts = samples[index]
            parts = [
                f"gettext plural form msgstr[{index}] for {target_name}"
                + (f", used when the count is {describe_counts(counts)}." if counts else "."),
                f"{source_name} singular: '{singular}'; plural: '{plural}'.",
                f"Write the {target_name} text for exactly these counts, using the correct "
                "grammatical form of the counted noun.",
            ]
            if not covers_single_count(counts):
                parts.append(
                    "This form covers several different counts, so keep every placeholder of the "
                    "plural text, including the number, instead of spelling out a number."
                )
            if entry.get("msgctxt"):
                parts.append(context_note(entry["msgctxt"]))
            contexts[plural_key(base, index)] = " ".join(parts)
    return contexts


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def read_po_entries(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        return _parse_po_content(f.read())


def _entry_values(entry: Dict[str, Any]) -> Dict[str, str]:
    """Flat {key: text} for one entry (empty for the header and comment-only blocks)."""
    if not entry.get("msgid"):
        return {}
    key = entry_key(entry)
    if entry.get("msgid_plural") is not None:
        forms = entry.get("msgstr_plural") or {}
        return {plural_key(key, i): forms[i] for i in sorted(forms)}
    if entry.get("msgstr") is None:
        return {}
    return {key: entry["msgstr"]}


def read_po_file(file_path: str) -> Dict[str, Any]:
    """
    Read a .po (gettext) localization file and extract key-value pairs.

    Args:
        file_path: Path to the .po file

    Returns:
        Dictionary containing the translation content, keyed by entry_key (plural forms as
        "<entry key>::msgstr[N]")
    """
    result: Dict[str, Any] = {}
    for entry in read_po_entries(file_path):
        result.update(_entry_values(entry))
    return result


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _guess_source_file(file_path: str) -> Optional[str]:
    """Source file next to the target (en.po, messages.en.po ...) when none was given."""
    dir_path = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    candidates: List[str] = []
    if "." in filename:
        name_parts = filename.split(".")
        if len(name_parts) >= 2:
            for src_lang in ["en", "es", "fr", "de"]:
                candidate_name = (
                    f"{name_parts[0]}.{src_lang}.{'.'.join(name_parts[2:])}"
                    if len(name_parts) > 2
                    else f"{src_lang}.{name_parts[1]}"
                )
                candidates.append(os.path.join(dir_path, candidate_name))
            for src_lang in ["en", "es", "fr", "de"]:
                candidates.append(os.path.join(dir_path, f"{src_lang}.{name_parts[1]}"))
    for candidate in candidates:
        if os.path.exists(candidate) and os.path.abspath(candidate) != os.path.abspath(file_path):
            return candidate
    return None


def _set_header_field(header_text: str, name: str, value: str) -> str:
    line = f"{name}: {value}\n"
    pattern = re.compile(rf"^{re.escape(name)}:.*(?:\n|$)", re.MULTILINE | re.IGNORECASE)
    if pattern.search(header_text):
        return pattern.sub(lambda _m: line, header_text, count=1)
    if header_text and not header_text.endswith("\n"):
        header_text += "\n"
    return header_text + line


def write_po_file(
    file_path: str,
    content: Dict[str, Any],
    mark_fuzzy: bool = False,
    source_file: Optional[str] = None,
    language: Optional[str] = None,
) -> None:
    """
    Write a dictionary to a .po localization file while preserving structure.

    Args:
        file_path: Path to the .po file
        content: Dictionary to write ({entry key: text}, plural forms as "<entry key>::msgstr[N]")
        mark_fuzzy: If True, add "#, fuzzy" comment to every translated entry
        source_file: Source .po file; new entries take their comments, flags, msgctxt and
            msgid_plural from it, and a new target file is created from it as a template.
            Guessed from the file name (en.po, messages.en.po ...) when not given.
        language: Target language; sets Language and Plural-Forms when a new file is created
            from the source template.
    """
    if source_file is None or not os.path.exists(source_file):
        source_file = _guess_source_file(file_path)
    source_entries = read_po_entries(source_file) if source_file else []
    source_by_key = {entry_key(e): e for e in source_entries if e.get("msgid")}

    from_template = False
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()
        entries = _parse_po_content(original_content)
    elif source_file:
        with open(source_file, "r", encoding="utf-8") as f:
            original_content = f.read()
        entries = _parse_po_content(original_content)
        from_template = True
    else:
        original_content = _scratch_header(language, any(split_plural_key(k) for k in content))
        entries = _parse_po_content(original_content)

    if from_template:
        _prepare_template(entries, language)

    plural_forms = file_plural_forms(entries) or plural_forms_for_language(language)
    _apply_content(entries, content, mark_fuzzy, source_by_key, plural_forms, file_path)
    _write_text(file_path, _reconstruct_po_content(entries, original_content))


def _write_text(file_path: str, text: str) -> None:
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _prepare_template(entries: List[Dict[str, Any]], language: Optional[str]) -> None:
    """
    A new target made from the source: no source text is kept as a "translation" (a value the
    translator did not provide, or that the placeholder gate rejected, stays empty so gettext
    falls back to the source and 'status' reports it), and the header gets the target's
    Language and Plural-Forms.
    """
    nplurals = None
    if language:
        nplurals, expr = plural_forms_for_language(language)
    for entry in entries:
        if _is_header(entry):
            if language and entry.get("msgstr") is not None:
                header = _set_header_field(entry["msgstr"], "Language", language.replace("-", "_"))
                header = _set_header_field(header, "Plural-Forms", f"nplurals={nplurals}; plural={expr};")
                entry["msgstr"] = header
            continue
        if not entry.get("msgid"):
            continue
        if entry.get("msgid_plural") is not None:
            count = nplurals if nplurals else len(entry.get("msgstr_plural") or {}) or 2
            entry["msgstr_plural"] = {i: "" for i in range(count)}
        elif entry.get("msgstr") is not None:
            entry["msgstr"] = ""


def _gate(entry: Dict[str, Any], index: Optional[int], value: str, source_entry, plural_forms, file_path: str) -> str:
    """The value, or "" when its placeholders don't match the entry's source (reported)."""
    if not isinstance(value, str) or not value.strip():
        return value
    try:
        from algebras.services.placeholders.formats.po import check_value
    except Exception:  # placeholder engine unavailable: write as before
        return value
    _source, problems = check_value(entry, index, value, source_entry, plural_forms)
    if not problems:
        return value
    key = entry_key(entry) if index is None else plural_key(entry_key(entry), index)
    details = "; ".join(p.message for p in problems)
    print(
        f"  ⚠ {os.path.basename(file_path)}: not writing '{display_key(key)}' ({details}); "
        "left empty so gettext uses the source text"
    )
    return ""


def _apply_content(
    entries: List[Dict[str, Any]],
    content: Dict[str, Any],
    mark_fuzzy: bool,
    source_by_key: Dict[str, Dict[str, Any]],
    plural_forms: Tuple[int, str],
    file_path: str,
) -> None:
    singular: Dict[str, Any] = {}
    plurals: Dict[str, Dict[int, Any]] = {}
    for key, value in content.items():
        if not isinstance(key, str) or not key:
            continue
        split = split_plural_key(key)
        if split:
            plurals.setdefault(split[0], {})[split[1]] = value
        else:
            singular[key] = value

    nplurals = plural_forms[0]
    handled_singular = set()
    handled_plural = set()

    for entry in entries:
        if not entry.get("msgid"):
            continue
        key = entry_key(entry)
        source_entry = source_by_key.get(key)
        if entry.get("msgid_plural") is not None:
            values = plurals.get(key)
            if values is None:
                continue
            handled_plural.add(key)
            forms = dict(entry.get("msgstr_plural") or {})
            for index in range(nplurals):
                forms.setdefault(index, "")
            changed = False
            for index, value in values.items():
                value = "" if value is None else str(value)
                if forms.get(index) != value:
                    forms[index] = _gate(entry, index, value, source_entry, plural_forms, file_path)
                    changed = True
            entry["msgstr_plural"] = forms
            if changed:
                _add_fuzzy_comment_if_needed(entry, mark_fuzzy)
        elif key in singular:
            handled_singular.add(key)
            value = singular[key]
            value = "" if value is None else str(value)
            if entry.get("msgstr") != value:
                entry["msgstr"] = _gate(entry, None, value, source_entry, plural_forms, file_path)
                _add_fuzzy_comment_if_needed(entry, mark_fuzzy)

    # New entries: comments, flags, msgctxt and msgid_plural come from the source entry.
    for key in sorted(set(singular) - handled_singular):
        source_entry = source_by_key.get(key)
        if source_entry is not None and source_entry.get("msgid_plural") is not None:
            continue  # a plural entry is written from its plural keys
        entry = _new_entry(key, source_entry)
        value = "" if singular[key] is None else str(singular[key])
        entry["msgstr"] = _gate(entry, None, value, source_entry, plural_forms, file_path)
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy)
        entries.append(entry)

    for key in sorted(set(plurals) - handled_plural):
        source_entry = source_by_key.get(key)
        entry = _new_entry(key, source_entry)
        entry["msgid_plural"] = (source_entry or {}).get("msgid_plural") or entry["msgid"]
        forms = {i: "" for i in range(nplurals)}
        for index, value in plurals[key].items():
            value = "" if value is None else str(value)
            forms[index] = _gate(entry, index, value, source_entry, plural_forms, file_path)
        entry["msgstr_plural"] = forms
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy)
        entries.append(entry)


def _new_entry(key: str, source_entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    msgctxt, msgid = split_entry_key(key)
    source_entry = source_entry or {}
    comments = list(source_entry.get("comments") or [])
    return {
        "comments": comments,
        "flags": _flags_from_comments(comments),
        "msgctxt": msgctxt if msgctxt is not None else (source_entry.get("msgctxt") or ""),
        "msgctxt_lines": [],
        "msgid": msgid,
        "msgid_lines": [],
        "msgid_plural": None,
        "msgid_plural_lines": [],
        "msgstr": "",
        "msgstr_lines": [],
        "msgstr_plural": None,
        "msgstr_plural_lines": {},
        "new": True,
    }


def update_po_values(file_path: str, values: Dict[str, str], mark_fuzzy: bool = False) -> List[str]:
    """
    Set the given values ({entry key: text} / {"<entry key>::msgstr[N]": text}) in place, without the
    placeholder gate (used by 'algebras placeholders --fix' for already verified values). Only the
    changed entries are re-serialized. Returns the keys that were not found.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        original_content = f.read()
    entries = _parse_po_content(original_content)
    by_key = {entry_key(e): e for e in entries if e.get("msgid")}
    not_found: List[str] = []
    for key, value in values.items():
        split = split_plural_key(key)
        base, index = split if split else (key, None)
        entry = by_key.get(base)
        if entry is None or (index is None) != (entry.get("msgid_plural") is None):
            not_found.append(key)
            continue
        if index is None:
            if entry.get("msgstr") == value:
                continue
            entry["msgstr"] = value
        else:
            forms = dict(entry.get("msgstr_plural") or {})
            if forms.get(index) == value:
                continue
            forms[index] = value
            entry["msgstr_plural"] = forms
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy)
    _write_text(file_path, _reconstruct_po_content(entries, original_content))
    return not_found


def _has_translation(entry: Dict[str, Any]) -> bool:
    if entry.get("msgid_plural") is not None:
        return any(isinstance(v, str) and v.strip() for v in (entry.get("msgstr_plural") or {}).values())
    return bool(entry.get("msgstr") and entry["msgstr"].strip())


def _add_fuzzy_comment_if_needed(entry: Dict[str, Any], mark_fuzzy: bool) -> None:
    """
    Add the fuzzy flag to entry if mark_fuzzy is True and the entry has a non-empty translation.
    An existing "#," flags line gets "fuzzy" added to it; otherwise a "#, fuzzy" line is inserted.
    """
    if not mark_fuzzy or not _has_translation(entry):
        return
    comments = entry.setdefault("comments", [])
    if "fuzzy" in _flags_from_comments(comments):
        return
    for i, comment in enumerate(comments):
        if comment.lstrip().startswith("#,"):
            stripped = comment.lstrip()
            comments[i] = "#, fuzzy, " + stripped[2:].strip()
            break
    else:
        comments.insert(0, "#, fuzzy")
    entry["flags"] = _flags_from_comments(comments)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_MSGSTR_INDEX_RE = re.compile(r"^msgstr\[(\d+)\]")


def _flags_from_comments(comments: List[str]) -> List[str]:
    """The `#,` flags of an entry (fuzzy, c-format, no-python-format ...), in file order."""
    flags: List[str] = []
    for comment in comments:
        stripped = comment.strip()
        if stripped.startswith("#,"):
            for flag in stripped[2:].split(","):
                flag = flag.strip()
                if flag and flag not in flags:
                    flags.append(flag)
    return flags


def _is_header(entry: Dict[str, Any]) -> bool:
    return entry.get("msgid") == "" and bool(entry.get("msgid_lines")) and not entry.get("msgctxt")


def _read_continuations(lines: List[str], i: int, first: str, target: List[str]) -> Tuple[str, int]:
    """Text of a keyword line plus its "..." continuation lines; returns (text, next index)."""
    target.append(first)
    text = _extract_quoted_string(first)
    while i < len(lines) and lines[i].strip().startswith('"'):
        continued = lines[i].strip()
        target.append(continued)
        text += _extract_quoted_string(continued)
        i += 1
    return text, i


def _parse_po_content(content: str) -> List[Dict[str, Any]]:
    """
    Parse .po file content into entries with metadata.

    Args:
        content: Raw .po file content

    Returns:
        List of entries with msgctxt, msgid, msgid_plural, msgstr / msgstr_plural, comments,
        flags and position info (start_line .. end_line)
    """
    entries = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        if line.startswith(("#", "msgid", "msgctxt")):
            entry: Dict[str, Any] = {
                "comments": [],
                "flags": [],
                "msgctxt": "",
                "msgctxt_lines": [],
                "msgid": "",
                "msgstr": "",
                "msgid_lines": [],
                "msgstr_lines": [],
                "msgid_plural": None,
                "msgid_plural_lines": [],
                "msgstr_plural": None,
                "msgstr_plural_lines": {},
                "start_line": i,
                "end_line": i,
            }

            while i < len(lines) and lines[i].strip().startswith("#"):
                entry["comments"].append(lines[i])
                i += 1

            if i < len(lines) and lines[i].strip().startswith("msgctxt"):
                entry["msgctxt"], i = _read_continuations(lines, i + 1, lines[i].strip(), entry["msgctxt_lines"])

            if i < len(lines) and lines[i].strip().startswith("msgid") and not lines[i].strip().startswith("msgid_plural"):
                entry["msgid"], i = _read_continuations(lines, i + 1, lines[i].strip(), entry["msgid_lines"])

            if i < len(lines) and lines[i].strip().startswith("msgid_plural"):
                entry["msgid_plural"], i = _read_continuations(
                    lines, i + 1, lines[i].strip(), entry["msgid_plural_lines"]
                )

            while i < len(lines) and lines[i].strip().startswith("msgstr"):
                stripped = lines[i].strip()
                m = _MSGSTR_INDEX_RE.match(stripped)
                if m:
                    index = int(m.group(1))
                    if entry["msgstr_plural"] is None:
                        entry["msgstr_plural"] = {}
                    target_lines = entry["msgstr_plural_lines"].setdefault(index, [])
                    entry["msgstr_plural"][index], i = _read_continuations(lines, i + 1, stripped, target_lines)
                else:
                    entry["msgstr"], i = _read_continuations(lines, i + 1, stripped, entry["msgstr_lines"])
                    break

            if entry["msgid_plural"] is not None and entry["msgstr_plural"] is None:
                entry["msgstr_plural"] = {}

            entry["flags"] = _flags_from_comments(entry["comments"])
            entry["end_line"] = i - 1
            entry["_orig"] = _snapshot(entry)
            entries.append(entry)
        else:
            i += 1

    return entries


def _snapshot(entry: Dict[str, Any]) -> Tuple:
    return (
        tuple(entry.get("comments") or ()),
        entry.get("msgctxt"),
        entry.get("msgid"),
        entry.get("msgid_plural"),
        entry.get("msgstr"),
        tuple(sorted((entry.get("msgstr_plural") or {}).items())),
    )


def _extract_quoted_string(line: str) -> str:
    """
    Extract string content from a quoted line.

    Args:
        line: Line containing quoted string

    Returns:
        Unescaped string content
    """
    match = re.search(r'"(.*)"', line)
    if match:
        return _unescape_po_string(match.group(1))
    return ""


_UNESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}


def _unescape_po_string(text: str) -> str:
    """
    Unescape .po string content in one pass ("\\\\n" stays a backslash followed by "n").
    Unknown escapes are kept as written.
    """
    return re.sub(r"\\(.)", lambda m: _UNESCAPES.get(m.group(1), m.group(0)), text)


def _escape_po_string(text: str) -> str:
    """
    Escape text for .po string format.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    replacements = [
        ("\\", "\\\\"),
        ('"', '\\"'),
        ("\n", "\\n"),
        ("\t", "\\t"),
        ("\r", "\\r"),
    ]
    result = text
    for unescaped, escaped in replacements:
        result = result.replace(unescaped, escaped)
    return result


# ---------------------------------------------------------------------------
# Serializing
# ---------------------------------------------------------------------------


def _field_lines(keyword: str, text: str, original_lines: List[str]) -> List[str]:
    """Lines for one keyword: the original lines if the text is unchanged, else re-serialized."""
    if original_lines and "".join(_extract_quoted_string(l) for l in original_lines) == text:
        return list(original_lines)
    if len(original_lines) > 1:
        return _format_multiline_entry(keyword, text)
    if len(original_lines) == 1:
        return [f'{keyword} "{_escape_po_string(text)}"']
    if text == "" or "\n" in text or len(text) > 120:
        return _format_multiline_entry(keyword, text)
    return [f'{keyword} "{_escape_po_string(text)}"']


def _entry_lines(entry: Dict[str, Any]) -> List[str]:
    lines: List[str] = list(entry.get("comments") or [])
    if entry.get("msgctxt_lines") or entry.get("msgctxt"):
        lines.extend(_field_lines("msgctxt", entry.get("msgctxt") or "", entry.get("msgctxt_lines") or []))
    if not entry.get("new") and not entry.get("msgid_lines"):
        # A block without msgid (comment-only, e.g. obsolete "#~" entries): keep what it has.
        if entry.get("msgstr_lines"):
            lines.extend(_field_lines("msgstr", entry.get("msgstr") or "", entry["msgstr_lines"]))
        return lines
    lines.extend(_field_lines("msgid", entry.get("msgid") or "", entry.get("msgid_lines") or []))
    if entry.get("msgid_plural") is not None:
        lines.extend(_field_lines("msgid_plural", entry["msgid_plural"], entry.get("msgid_plural_lines") or []))
        forms = entry.get("msgstr_plural") or {}
        original = entry.get("msgstr_plural_lines") or {}
        for index in sorted(forms):
            lines.extend(_field_lines(f"msgstr[{index}]", forms[index] or "", original.get(index) or []))
    else:
        lines.extend(_field_lines("msgstr", entry.get("msgstr") or "", entry.get("msgstr_lines") or []))
    return lines


def _reconstruct_po_content(entries: List[Dict[str, Any]], original_content: str) -> str:
    """
    Reconstruct .po file content from parsed entries.

    Every line outside the entries (blank lines, stray text) and every unchanged entry is kept
    byte-for-byte; changed entries are re-serialized in place; new entries are appended.

    Args:
        entries: Parsed entries with updated translations
        original_content: Original file content for reference

    Returns:
        Reconstructed .po file content
    """
    lines = original_content.split("\n")
    existing = sorted(
        (e for e in entries if not e.get("new") and "start_line" in e and e["start_line"] < len(lines)),
        key=lambda e: e["start_line"],
    )
    existing_ids = {id(e) for e in existing}
    new_entries = [e for e in entries if id(e) not in existing_ids]

    result_lines: List[str] = []
    pos = 0
    for entry in existing:
        start, end = entry["start_line"], entry["end_line"]
        if start < pos:
            continue
        result_lines.extend(lines[pos:start])
        if entry.get("_orig") is not None and entry["_orig"] == _snapshot(entry):
            result_lines.extend(lines[start : end + 1])
        else:
            result_lines.extend(_entry_lines(entry))
        pos = end + 1
    result_lines.extend(lines[pos:])

    for entry in new_entries:
        while result_lines and result_lines[-1] == "":
            result_lines.pop()
        if result_lines:
            result_lines.append("")
        entry = dict(entry)
        entry.pop("_orig", None)
        entry["new"] = True
        result_lines.extend(_entry_lines(entry))

    while result_lines and result_lines[-1] == "":
        result_lines.pop()
    result_lines.append("")
    return "\n".join(result_lines)


def _should_be_multiline(text: str) -> bool:
    """
    Determine if a string should be formatted as multi-line in .po format.

    Args:
        text: String to check

    Returns:
        True if should be multi-line, False otherwise
    """
    return text == "" or "\n" in text or len(text) > 80


def _wrap(text: str, width: int = 76) -> List[str]:
    """Split text into chunks of about `width` characters at spaces; spaces are kept."""
    tokens = re.findall(r"\S+\s*|\s+", text)
    chunks: List[str] = []
    current = ""
    for token in tokens:
        if current and len(current) + len(token) > width:
            chunks.append(current)
            current = ""
        current += token
    if current:
        chunks.append(current)
    return chunks


def _format_multiline_entry(entry_type: str, text: str) -> List[str]:
    """
    Format a string as a multi-line .po entry.

    Args:
        entry_type: 'msgid', 'msgstr', 'msgstr[N]' ...
        text: Text to format

    Returns:
        List of lines for the multi-line entry
    """
    if text == "":
        return [f'{entry_type} ""']

    if "\n" in text:
        lines = [f'{entry_type} ""']
        text_lines = text.split("\n")
        for i, line in enumerate(text_lines):
            if i == len(text_lines) - 1 and line == "":
                continue
            piece = line + "\n" if i < len(text_lines) - 1 else line
            lines.append(f'"{_escape_po_string(piece)}"')
        return lines

    if len(text) > 80:
        return [f'{entry_type} ""'] + [f'"{_escape_po_string(chunk)}"' for chunk in _wrap(text)]

    return [f'{entry_type} "{_escape_po_string(text)}"']


def _scratch_header(language: Optional[str] = None, with_plurals: bool = False) -> str:
    header = []
    if language:
        header.append(f"Language: {language.replace('-', '_')}\n")
    header += ["Content-Type: text/plain; charset=UTF-8\n", "Content-Transfer-Encoding: 8bit\n"]
    if language or with_plurals:
        nplurals, expr = plural_forms_for_language(language)
        header.append(f"Plural-Forms: nplurals={nplurals}; plural={expr};\n")
    lines = ["# Translation file", "# Generated by algebras-cli", "#", 'msgid ""', 'msgstr ""']
    lines.extend(f'"{_escape_po_string(h)}"' for h in header)
    lines.append("")
    return "\n".join(lines)


def _create_po_from_scratch(content: Dict[str, Any], mark_fuzzy: bool = False, language: Optional[str] = None) -> str:
    """
    Create a .po file from scratch when no template is available.

    Args:
        content: Dictionary of translations
        mark_fuzzy: If True, add "#, fuzzy" comment to every translated entry
        language: Target language (sets Language and Plural-Forms)

    Returns:
        Complete .po file content
    """
    original_content = _scratch_header(language, any(split_plural_key(k) for k in content))
    entries = _parse_po_content(original_content)
    plural_forms = file_plural_forms(entries) or plural_forms_for_language(language)
    _apply_content(entries, content, mark_fuzzy, {}, plural_forms, "")
    return _reconstruct_po_content(entries, original_content)
