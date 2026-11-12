"""
JSON localization files: the parts the i18n library gives meaning to.

Chrome extension messages.json
    {"greeting": {"message": "Hello $USER$", "description": "…", "placeholders": {"user": {"content": "$1"}}}}
    Only `message` is translatable. `description` is a note for translators, and
    `placeholders.*.content` / `example` are code ("$1"). They are copied from the source as they are.

i18next plural keys
    {"item_one": "One item", "item_other": "{{count}} items"}
    A target form that covers several counts (Russian "one" = 1, 21, 31 …) needs {{count}}, so when
    the source form lacks it, the form is translated from (and checked against) the `_other` text —
    the same rule as Android <plurals> and .stringsdict (see android_plurals.plural_source_text).
    When the file's profile is i18next (detected from its {{…}} placeholders, or pinned in the
    config), each group also gets the CLDR forms the target language needs but the source lacks
    (ru `_few`, `_many`), translated from the `_other` text and placed next to the group in CLDR
    order (expand_i18next_plurals). Other JSON whose keys happen to end in `_one` is left alone.
"""

import copy
import re
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from algebras.utils.plural_rules import (
    PLURAL_CATEGORY_ORDER,
    covers_single_count,
    get_category_examples,
    get_language_name,
    get_plural_categories,
)

KeyPath = Tuple[str, ...]

# ---------------------------------------------------------------------------
# Chrome extension messages.json
# ---------------------------------------------------------------------------

CHROME_FIELDS = frozenset({"message", "description", "placeholders"})


def is_chrome_messages(content: Any) -> bool:
    """True for a Chrome extension messages.json: every entry is {"message": …, [description, placeholders]}."""
    return (
        isinstance(content, dict)
        and bool(content)
        and all(
            isinstance(v, dict) and isinstance(v.get("message"), str) and set(v) <= CHROME_FIELDS
            for v in content.values()
        )
    )


def chrome_messages_only(content: Dict[str, Any]) -> Dict[str, Any]:
    """{name: {"message": text}}: what is sent for translation."""
    return {name: {"message": entry["message"]} for name, entry in content.items()}


def _merge_chrome_entry(source_entry: Dict[str, Any], target_entry: Any) -> Dict[str, Any]:
    """Target entry in source field order: its own message, the source's non-translatable fields."""
    target_entry = target_entry if isinstance(target_entry, dict) else {}
    merged: Dict[str, Any] = {}
    for field, value in source_entry.items():
        if field == "message":
            if "message" in target_entry:
                merged["message"] = target_entry["message"]
        elif field in target_entry:
            merged[field] = target_entry[field]
        else:
            merged[field] = copy.deepcopy(value)
    for field, value in target_entry.items():
        merged.setdefault(field, value)
    return merged


# ---------------------------------------------------------------------------
# i18next plural keys
# ---------------------------------------------------------------------------

_PLURAL_KEY = re.compile(r"^(?P<base>.+?)_(?P<ordinal>ordinal_)?(?P<form>zero|one|two|few|many|other)$")


def i18next_plural_form(key: str) -> Optional[Tuple[str, str]]:
    """("item", "one") for "item_one"; None for other keys and ordinal forms ("place_ordinal_one")."""
    m = _PLURAL_KEY.match(key)
    if not m or m.group("ordinal"):
        return None
    return m.group("base"), m.group("form")


def i18next_plural_groups(level: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """{base: {form: text}} for the plural keys of one dict level that have an `_other` form."""
    groups: Dict[str, Dict[str, str]] = {}
    for key, value in level.items():
        parsed = i18next_plural_form(str(key)) if isinstance(value, str) else None
        if parsed:
            groups.setdefault(parsed[0], {})[parsed[1]] = value
    return {base: forms for base, forms in groups.items() if "other" in forms}


def _count_placeholder(text: str, profile) -> Optional[str]:
    from algebras.services.placeholders import count_drop_allowed, extract

    counts = count_drop_allowed(text, profile)
    return next((p.raw for p in extract(text, profile) if p.raw in counts), None)


def i18next_plural_source_text(forms: Dict[str, str], form: str, target_lang: str, profile) -> str:
    """
    The source text a target plural form is translated from and checked against: its own source
    text, or the `_other` text for a form the source lacks or whose source text has no count
    placeholder while the form covers several counts in the target language.
    """
    other = forms["other"]
    text = forms.get(form)
    if text is None:
        return other
    if form != "other" and form in get_plural_categories(target_lang) and not covers_single_count(target_lang, form):
        count = _count_placeholder(other, profile)
        if count and count not in text:
            return other
    return text


def i18next_plural_context(forms: Dict[str, str], form: str, source_lang: str, target_lang: str, profile) -> str:
    target_name = get_language_name(target_lang)
    examples = get_category_examples(target_lang, form) if form in get_plural_categories(target_lang) else None
    usage = f" It is shown when the count is {examples}" + ("" if not examples or examples.endswith("…") else ".") if examples else ""
    source_forms = "; ".join(f"{f}: '{forms[f]}'" for f in PLURAL_CATEGORY_ORDER if f in forms)
    parts = [
        f"i18next plural form '{form}' for {target_name}.{usage}",
        f"{get_language_name(source_lang)} source forms: {source_forms}.",
    ]
    count = _count_placeholder(forms["other"], profile)
    if count and form in get_plural_categories(target_lang) and not covers_single_count(target_lang, form):
        parts.append(f"This form covers several counts, so keep the count placeholder ({count}).")
    return " ".join(parts)


def iter_i18next_plural_keys(
    content: Any, prefix: KeyPath = (), target_lang: Optional[str] = None
) -> Iterator[Tuple[KeyPath, Dict[str, str], str]]:
    """
    (key path, forms of its group, form) for every i18next plural key in `content`; with
    `target_lang`, also for the forms that language needs but an expandable group lacks.
    """
    if not isinstance(content, dict):
        return
    groups = i18next_plural_groups(content)
    for key, value in content.items():
        if isinstance(value, dict):
            yield from iter_i18next_plural_keys(value, prefix + (str(key),), target_lang)
            continue
        parsed = i18next_plural_form(str(key)) if isinstance(value, str) else None
        if parsed and parsed[0] in groups:
            yield prefix + (str(key),), groups[parsed[0]], parsed[1]
    if target_lang:
        for base, forms in groups.items():
            for form in missing_i18next_forms(forms, target_lang):
                yield prefix + (f"{base}_{form}",), forms, form


# ---------------------------------------------------------------------------
# i18next plural expansion: the CLDR forms the target language needs
# ---------------------------------------------------------------------------


def is_i18next_profile(profile) -> bool:
    """
    True when a JSON file's placeholder profile is i18next: detected from the file's own values
    (json_format.resolve_profile) or pinned in the config. The generic fallback profile, which
    lists every syntax, does not count.
    """
    return profile is not None and profile.name != "generic" and "i18next" in profile.syntax_names


def missing_i18next_forms(forms: Dict[str, str], target_lang: str) -> List[str]:
    """
    CLDR forms `target_lang` needs that a plural group lacks, in CLDR order. Only groups with
    `_other` and at least one other form are expanded: a lone `contact_other` is more likely an
    ordinary key than a plural.
    """
    if "other" not in forms or len(forms) < 2:
        return []
    return [f for f in get_plural_categories(target_lang) if f not in forms]


def _rank(form: str) -> int:
    return PLURAL_CATEGORY_ORDER.index(form)


def _expand_level(level: Dict[str, Any], target_lang: str) -> Dict[str, Any]:
    keys = list(level)
    added: Dict[str, Any] = {}
    for base, forms in i18next_plural_groups(level).items():
        for form in missing_i18next_forms(forms, target_lang):
            members = [(i, i18next_plural_form(k)[1]) for i, k in enumerate(keys) if _group_member(k, base, level, added)]
            before = [(i, f) for i, f in members if _rank(f) < _rank(form)]
            if before:
                at = max(before, key=lambda m: _rank(m[1]))[0] + 1
            else:
                at = min(members, key=lambda m: _rank(m[1]))[0]
            new_key = f"{base}_{form}"
            keys.insert(at, new_key)
            added[new_key] = forms["other"]
    result: Dict[str, Any] = {}
    for key in keys:
        value = added[key] if key in added else level[key]
        result[key] = _expand_level(value, target_lang) if isinstance(value, dict) else copy.deepcopy(value)
    return result


def _group_member(key: str, base: str, level: Dict[str, Any], added: Dict[str, Any]) -> bool:
    value = added.get(key, level.get(key))
    parsed = i18next_plural_form(str(key)) if isinstance(value, str) else None
    return bool(parsed) and parsed[0] == base


def expand_i18next_plurals(content: Any, target_lang: Optional[str], profile) -> Any:
    """
    Copy of `content` in which every i18next plural group also has the forms `target_lang` needs
    but the source lacks (en item_one/item_other -> ru item_one/item_few/item_many/item_other),
    each new key holding the `_other` text and placed next to its group in CLDR order. `content`
    itself is returned when nothing changes: no target language, a profile other than i18next
    (is_i18next_profile), a Chrome messages.json, or no group missing a form.
    """
    if not target_lang or not isinstance(content, dict) or not is_i18next_profile(profile):
        return content
    if is_chrome_messages(content):
        return content
    if not any(True for _ in _missing_paths(content, target_lang)):
        return content
    return _expand_level(content, target_lang)


def _missing_paths(content: Dict[str, Any], target_lang: str, prefix: KeyPath = ()) -> Iterator[KeyPath]:
    for base, forms in i18next_plural_groups(content).items():
        for form in missing_i18next_forms(forms, target_lang):
            yield prefix + (f"{base}_{form}",)
    for key, value in content.items():
        if isinstance(value, dict):
            yield from _missing_paths(value, target_lang, prefix + (str(key),))


def expand_i18next_source_file(source_file: Optional[str], content: Any, target_lang: Optional[str], config=None) -> Any:
    """expand_i18next_plurals for a JSON source file, with the file's detected (or pinned) profile."""
    if not source_file or not target_lang or not str(source_file).lower().endswith(".json"):
        return content
    from algebras.services.placeholders import profile_for_path

    return expand_i18next_plurals(content, target_lang, profile_for_path(source_file, config))


# ---------------------------------------------------------------------------
# Translation preparation
# ---------------------------------------------------------------------------


def _set(content: Dict[str, Any], path: KeyPath, value: Any) -> None:
    for part in path[:-1]:
        content = content.setdefault(part, {})
    content[path[-1]] = value


class JsonTranslationPlan:
    """
    What to send for a JSON file and how to put the result together.

    `source` is the source content to translate from (Chrome: messages only; i18next plural forms:
    the text they must be translated from). `keys` drops the requested keys that are not
    translatable. `finish(result)` puts the non-translatable Chrome fields back.
    """

    def __init__(self, original: Dict[str, Any], source: Dict[str, Any], keys: Optional[List[str]], chrome: bool, contexts: Dict[str, str]):
        self.original = original
        self.source = source
        self.keys = keys
        self.chrome = chrome
        self.contexts = contexts

    def finish(self, result: Dict[str, Any], requested: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        if not self.chrome or not isinstance(result, dict):
            return result
        names = (
            list(self.original)
            if requested is None
            else list(dict.fromkeys(k.split(".", 1)[0] for k in requested if k.split(".", 1)[0] in self.original))
        )
        for name in names:
            if name in result or requested is None:
                result[name] = _merge_chrome_entry(self.original[name], result.get(name))
        return result

    def merge_contexts(self, contexts: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if not self.contexts:
            return contexts
        merged = dict(self.contexts)
        merged.update(contexts or {})
        return merged


def plan_json_translation(
    source_content: Any,
    keys: Optional[Sequence[str]],
    source_lang: str,
    target_lang: str,
    profile,
) -> Optional[JsonTranslationPlan]:
    """
    Plan for a JSON source, or None when nothing needs adjusting (then translate as before).
    `keys` are the requested dot-notation keys (None = the whole file).
    """
    if not isinstance(source_content, dict):
        return None
    chrome = is_chrome_messages(source_content)
    expand = not chrome and is_i18next_profile(profile)
    plural_keys = [] if chrome else list(iter_i18next_plural_keys(source_content, target_lang=target_lang if expand else None))
    if not chrome and not plural_keys:
        return None

    if chrome:
        source = chrome_messages_only(source_content)
    elif expand:
        # The forms the target language needs, next to their group (values set below).
        source = copy.deepcopy(expand_i18next_plurals(source_content, target_lang, profile))
    else:
        source = copy.deepcopy(source_content)
    contexts: Dict[str, str] = {}
    for path, forms, form in plural_keys:
        _set(source, path, i18next_plural_source_text(forms, form, target_lang, profile))
        contexts[".".join(path)] = i18next_plural_context(forms, form, source_lang, target_lang, profile)

    new_keys = None
    if keys is not None:
        new_keys = list(keys)
        if chrome:
            # Only "name" (a whole missing entry) and "name.message" are translated.
            new_keys = [k for k in keys if "." not in k or k.split(".", 1)[1] == "message"]
    return JsonTranslationPlan(source_content, source, new_keys, chrome, contexts)


def run_json_plan(
    translate: Callable[..., Dict[str, Any]],
    source_content: Any,
    target_content: Dict[str, Any],
    keys: List[str],
    target_lang: str,
    source_lang: str,
    profile,
    contexts: Optional[Dict[str, str]],
    **kwargs,
) -> Dict[str, Any]:
    """Call a Translator batch method (missing/outdated keys) through the JSON plan."""
    plan = plan_json_translation(source_content, keys, source_lang, target_lang, profile)
    if plan is None:
        return translate(source_content, target_content, keys, target_lang, contexts=contexts, **kwargs)
    result = translate(plan.source, target_content, plan.keys, target_lang, contexts=plan.merge_contexts(contexts), **kwargs)
    return plan.finish(result, keys)
