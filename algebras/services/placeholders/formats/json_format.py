"""
JSON localization files (i18next, FormatJS/react-intl, vue-i18n, ngx-translate, Chrome messages.json).

JSON has no placeholder syntax of its own; the app's i18n library decides it. The profile is
detected from the source file's values (detect_profile), unless pinned in the config
(`placeholders: [i18next]`):

- i18next: {{name}}, {{- html}}, {{value, number}}, $t(other.key) nesting, <0>…</0> Trans tags;
- FormatJS: ICU {name} (plural/select is split by ICUMessageService), <b>…</b> rich-text tags
  (xml_tag: open and close are separate tokens, the text between them is translated);
- vue-i18n: {name}, {0}, linked messages @:key / @.lower:key, and pipe plurals "car | cars".
  The "|" separator is masked as a token, so the model translates all forms in one text (same
  wording, same noun) and must keep the number of forms. Splitting into segments would send each
  form on its own, without the others as context, and needs its own split/join around the batch;
- Chrome messages.json: $NAME$ and $1, in "message" only.

`$t(…)` and `@:…` reference other keys and must stay byte-identical: a changed one is reported as
`linked_key_changed` and restored from the source by order.
"""

import json
import re
from json.decoder import scanstring
from typing import Any, Dict, Iterator, List, Optional, Tuple

from algebras.services.placeholders.engine import Problem, extract, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.profiles import (
    GENERIC_PROFILE,
    PlaceholderProfile,
    detect_profile,
    profile_for_path,
    register_profile_resolver,
)
from algebras.services.placeholders.syntaxes import SYNTAXES, Syntax

KeyPath = Tuple[str, ...]

# ---------------------------------------------------------------------------
# Syntaxes
# ---------------------------------------------------------------------------

# i18next nesting: the same span as the shared i18next syntax, listed first in JSON profiles so
# a changed key is reported as linked_key_changed.
I18NEXT_NESTING = Syntax(
    name="i18next_nesting",
    kind="linked",
    pattern=re.compile(r"\$t\([^()]*\)"),
    lenient=re.compile(r"[$＄]\s?[tт]\s?[(（][^()（）]*[)）]"),
)

# vue-i18n linked messages: @:key, @.lower:key, @:(key.with:colon).
VUE_LINKED = Syntax(
    name="vue_linked",
    kind="linked",
    pattern=re.compile(r"@(?:\.[A-Za-z]+)?:(?:\([\w\-.:/]+\)|[\w\-./]*[\w\-])"),
    lenient=re.compile(r"[@＠](?:\.\w+)?\s?[:：]\s?(?:\([^()\s]+\)|[\w\-./]*[\w\-])"),
)

VUE_PIPE = Syntax(name="vue_pipe", kind="separator", pattern=re.compile(r"\|"))

# react-i18next <Trans> components: <0>…</0>, <1/>.
INDEXED_TAG = Syntax(name="indexed_tag", kind="tag", pattern=re.compile(r"</?\d+>|<\d+\s*/>"))

_LINKED = (I18NEXT_NESTING, VUE_LINKED)


def _is_linked(raw: str) -> bool:
    return any(s.pattern.fullmatch(raw) or s.lenient.fullmatch(raw) for s in _LINKED)


def linked_check(src, tgt, problems: List[Problem]) -> List[Problem]:
    """A lost linked key paired with a new or damaged one in its place: linked_key_changed."""
    lost = [p for p in problems if p.code == "missing" and _is_linked(p.placeholder)]
    changed = [p for p in problems if p.code in ("extra", "corrupted") and _is_linked(p.placeholder)]
    pairs = list(zip(lost, changed))
    if not pairs:
        return problems
    paired = {id(p) for pair in pairs for p in pair}
    result = [p for p in problems if id(p) not in paired]
    for before, after in pairs:
        result.append(
            Problem(
                "linked_key_changed",
                after.placeholder,
                f"Linked key {before.placeholder} was changed to {after.placeholder}; it must stay as in the source",
            )
        )
    return result


for _syntax in (I18NEXT_NESTING, VUE_LINKED):
    SYNTAXES.setdefault(_syntax.name, Syntax(_syntax.name, _syntax.kind, _syntax.pattern, _syntax.lenient, linked_check))
for _syntax in (VUE_PIPE, INDEXED_TAG):
    SYNTAXES.setdefault(_syntax.name, _syntax)

# ---------------------------------------------------------------------------
# Profile detection
# ---------------------------------------------------------------------------

# Candidate order matters for equal spans: "$t(x)" is i18next_nesting, not i18next.
JSON_CANDIDATES = (
    "i18next_nesting",
    "vue_linked",
    "i18next",
    "indexed_tag",
    "xml_tag",
    "js_template",
    "icu_simple",
    "python_percent",
    "ruby",
    "printf",
    "vue_pipe",
)
CHROME_CANDIDATES = ("xml_tag",)


def _json_strings(data: Any) -> Iterator[str]:
    if isinstance(data, dict):
        for value in data.values():
            yield from _json_strings(value)
    elif isinstance(data, list):
        for value in data:
            yield from _json_strings(value)
    elif isinstance(data, str):
        yield data


def resolve_profile(file_path: str, config=None) -> PlaceholderProfile:
    """The syntaxes the source file actually uses (Chrome messages.json: in "message" values)."""
    from algebras.utils.json_i18n import is_chrome_messages

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return GENERIC_PROFILE
    if is_chrome_messages(data):
        return detect_profile((v["message"] for v in data.values()), CHROME_CANDIDATES, "chrome", always=("chrome",))
    return detect_profile(_json_strings(data), JSON_CANDIDATES, "json")


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def _read(path: str) -> Any:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _pairs(source: Any, target: Any, target_language: str, profile) -> Iterator[Tuple[KeyPath, str, Any]]:
    """(key path, source text it is checked against, target value) for every translatable string."""
    from algebras.utils.json_i18n import (
        i18next_plural_form,
        i18next_plural_groups,
        i18next_plural_source_text,
        is_chrome_messages,
    )

    if is_chrome_messages(source):
        for name, entry in source.items():
            target_entry = target.get(name) if isinstance(target, dict) else None
            yield (name, "message"), entry["message"], target_entry.get("message") if isinstance(target_entry, dict) else None
        return

    def walk(src: Dict[str, Any], tgt: Any, prefix: KeyPath):
        tgt = tgt if isinstance(tgt, dict) else {}
        groups = i18next_plural_groups(src)
        for key, value in src.items():
            path = prefix + (str(key),)
            if isinstance(value, dict):
                yield from walk(value, tgt.get(key), path)
            elif isinstance(value, str):
                parsed = i18next_plural_form(str(key))
                if parsed and parsed[0] in groups:
                    value = i18next_plural_source_text(groups[parsed[0]], parsed[1], target_language, profile)
                yield path, value, tgt.get(key)
        # Plural forms the target has but the source lacks (ru item_few) are checked against _other.
        for key, value in tgt.items():
            parsed = i18next_plural_form(str(key)) if key not in src and isinstance(value, str) else None
            if parsed and parsed[0] in groups:
                text = i18next_plural_source_text(groups[parsed[0]], parsed[1], target_language, profile)
                yield prefix + (str(key),), text, value

    if isinstance(source, dict):
        yield from walk(source, target, ())


def _missing_forms(source: Any, target: Any, target_language: str, profile) -> Iterator[Finding]:
    """
    i18next plural groups the target has translated but without every CLDR form the target
    language needs (ru item_few / item_many): `missing_form`, keyed like the form's own key.
    """
    from algebras.services.placeholders.plurals import missing_form_problem
    from algebras.utils.json_i18n import (
        i18next_plural_groups,
        i18next_plural_source_text,
        is_chrome_messages,
        is_i18next_profile,
    )
    from algebras.utils.plural_rules import PLURAL_CATEGORY_ORDER, get_plural_categories

    if not is_i18next_profile(profile) or not isinstance(source, dict) or is_chrome_messages(source):
        return

    def walk(src: Dict[str, Any], tgt: Any, prefix: KeyPath):
        if not isinstance(tgt, dict):
            return
        for base, forms in i18next_plural_groups(src).items():
            if len(forms) < 2:
                continue  # a lone `x_other` is not expanded (missing_i18next_forms)
            present = {
                form
                for form in PLURAL_CATEGORY_ORDER
                if isinstance(tgt.get(f"{base}_{form}"), str) and tgt[f"{base}_{form}"].strip()
            }
            if not present:
                continue  # untranslated group: 'status' reports it
            for form in get_plural_categories(target_language):
                if form in present:
                    continue
                path = prefix + (f"{base}_{form}",)
                yield Finding(
                    key=".".join(path),
                    source=i18next_plural_source_text(forms, form, target_language, profile),
                    target="",
                    problems=[missing_form_problem(form, target_language)],
                    path=path,
                )
        for key, value in src.items():
            if isinstance(value, dict):
                yield from walk(value, tgt.get(key), prefix + (str(key),))

    yield from walk(source, target, ())


def restore_linked(source: str, target: str, profile: PlaceholderProfile) -> Optional[str]:
    """
    Put the source's $t(…) / @:… back: the target's changed linked keys are replaced, in order, by
    the source ones it lost. Intact keys stay where the translation put them.
    """
    names = {s.name for s in _LINKED}
    if not names & set(profile.syntax_names):
        return None
    lost = [p.raw for p in extract(source, profile) if p.syntax in names]
    if not lost:
        return None
    found: List[Tuple[int, int]] = []
    for syntax in _LINKED:
        for pattern in (syntax.pattern, syntax.lenient):
            for m in pattern.finditer(target):
                if not any(s < m.end() and m.start() < e for s, e in found):
                    found.append((m.start(), m.end()))
    changed: List[Tuple[int, int]] = []
    for start, end in sorted(found):
        if target[start:end] in lost:
            lost.remove(target[start:end])  # intact
        else:
            changed.append((start, end))
    if not changed or len(changed) != len(lost):
        return None
    fixed = target
    for (start, end), raw in sorted(zip(changed, lost), reverse=True):
        fixed = fixed[:start] + raw + fixed[end:]
    return fixed


def repair_value(source: str, target: str, profile: PlaceholderProfile, drop_allowed=frozenset()) -> Optional[str]:
    """Engine repair (lookalikes, unique slot, {{ имя }} → {{name}}) plus linked keys by order."""
    linked = restore_linked(source, target, profile)
    base = linked if linked is not None else target
    fixed = repair(source, base, profile, drop_allowed) or linked
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
    """
    Placeholder findings for a JSON target. Like the default key-by-key check, plus: Chrome
    messages.json compares only "message"; i18next plural forms are checked against the text they
    are translated from (the `_other` text for multi-count forms whose source lacks {{count}}, and
    for target-only forms such as ru `_few`), and an i18next group the target translated without
    every CLDR form its language needs is `missing_form` (fixed by --retranslate).
    """
    from algebras.services.placeholders.plurals import drop_allowed_for_key

    profile = profile_for_path(source_file, config)
    findings: List[Finding] = []
    source, target = _read(source_file), _read(target_file)
    for path, source_text, target_text in _pairs(source, target, target_language, profile):
        if not isinstance(target_text, str) or not target_text.strip():
            continue  # untranslated: 'status' reports it
        key = ".".join(path)
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
                    fixed=repair_value(source_text, target_text, profile, drop),
                )
            )
    findings.extend(_missing_forms(source, target, target_language, profile))
    return findings


# ---------------------------------------------------------------------------
# Fix writer: replace only the fixed string literals
# ---------------------------------------------------------------------------

_WS = re.compile(r"[ \t\n\r]*")
_ESCAPED_NON_ASCII = re.compile(r"\\u(?!00[0-7][0-9a-fA-F])[0-9a-fA-F]{4}")


def string_spans(text: str) -> Dict[KeyPath, Tuple[int, int]]:
    """{key path: (start, end)} of every string value literal (quotes included) in a JSON document."""
    decoder = json.JSONDecoder()
    spans: Dict[KeyPath, Tuple[int, int]] = {}

    def ws(i: int) -> int:
        return _WS.match(text, i).end()

    def value(i: int, path: KeyPath) -> int:
        i = ws(i)
        ch = text[i : i + 1]
        if ch in ("{", "["):
            close = "}" if ch == "{" else "]"
            i = ws(i + 1)
            if text[i : i + 1] == close:
                return i + 1
            index = 0
            while True:
                i = ws(i)
                if ch == "{":
                    if text[i : i + 1] != '"':
                        raise ValueError(f"Expected a key at offset {i}")
                    key, i = scanstring(text, i + 1)
                    i = ws(i)
                    if text[i : i + 1] != ":":
                        raise ValueError(f"Expected ':' at offset {i}")
                    i = value(i + 1, path + (key,))
                else:
                    i = value(i, path + (str(index),))
                    index += 1
                i = ws(i)
                if text[i : i + 1] == ",":
                    i += 1
                elif text[i : i + 1] == close:
                    return i + 1
                else:
                    raise ValueError(f"Expected ',' or '{close}' at offset {i}")
        if ch == '"':
            _, end = scanstring(text, i + 1)
            spans[path] = (i, end)
            return end
        _, end = decoder.raw_decode(text, i)
        return end

    value(1 if text.startswith("﻿") else 0, ())
    return spans


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: str = None, config=None) -> None:
    """
    Replace the fixed values in place. Everything else (key order, indentation, spacing, escapes,
    trailing newline) stays byte-for-byte; new values use the file's escaping style (\\uXXXX if
    the file escapes non-ASCII text, raw UTF-8 otherwise).
    """
    with open(target_file, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    spans = string_spans(text)
    missing = [p for p in fixes if tuple(p) not in spans]
    if missing:
        raise ValueError(f"Could not find {', '.join('.'.join(p) for p in missing)} in {target_file}")
    ensure_ascii = bool(_ESCAPED_NON_ASCII.search(text)) and not re.search(r"[^\x00-\x7f]", text.lstrip("﻿"))
    for path in sorted(fixes, key=lambda p: spans[tuple(p)][0], reverse=True):
        start, end = spans[tuple(path)]
        text = text[:start] + json.dumps(fixes[path], ensure_ascii=ensure_ascii) + text[end:]
    with open(target_file, "w", encoding="utf-8", newline="") as f:
        f.write(text)


register_profile_resolver([".json"], resolve_profile)
register_file_check([".json"], check_file)
register_fix_writer([".json"], write_fixes)
