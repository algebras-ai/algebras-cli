"""
Plural support for Android <plurals> during translation (DEV-640 parity with .stringsdict).

The Android reader stores plurals as {"name.__plurals__": {"one": ..., "other": ...}}. For
translation they are flattened to one key per form ("name.__plurals__.one"), so that:

- the forms the target language needs but the source lacks are added (en one/other -> ru
  one/few/many/other), each starting from the source 'other' text;
- every form gets a translator note: which counts it covers in the target language, the source
  forms, and (for forms covering several counts) to keep the number placeholder;
- the existing two-pass translation (split_plural_passes / anchor_plural_contexts) translates
  each 'other' first and anchors the remaining forms to it.

The result is folded back into the nested structure the Android writers expect.
"""

import copy
from typing import Any, Callable, Dict, Iterable, List, Optional

from algebras.utils.plural_rules import (
    PLURAL_CATEGORY_ORDER,
    covers_single_count,
    get_category_examples,
    get_language_name,
    get_plural_categories,
)

PLURALS_SUFFIX = ".__plurals__"
_FORM_SEPARATOR = PLURALS_SUFFIX + "."


def has_android_plurals(content: Any) -> bool:
    return isinstance(content, dict) and any(
        isinstance(k, str) and k.endswith(PLURALS_SUFFIX) and isinstance(v, dict) for k, v in content.items()
    )


def _forms(plural_dict: Dict[str, Any]) -> List[str]:
    return [f for f in PLURAL_CATEGORY_ORDER if isinstance(plural_dict.get(f), str)]


def _plurals(content: Dict[str, Any]):
    for key, value in content.items():
        if isinstance(key, str) and key.endswith(PLURALS_SUFFIX) and isinstance(value, dict):
            yield key, value


def flatten(content: Dict[str, Any]) -> Dict[str, Any]:
    """{"n.__plurals__": {"one": a}} -> {"n.__plurals__.one": a}; other keys unchanged."""
    flat: Dict[str, Any] = {}
    for key, value in (content or {}).items():
        if isinstance(key, str) and key.endswith(PLURALS_SUFFIX) and isinstance(value, dict):
            for form, text in value.items():
                flat[f"{key}.{form}"] = text
        else:
            flat[key] = value
    return flat


def unflatten(flat: Dict[str, Any], base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Inverse of flatten, merged over `base` (the original nested target)."""
    result = copy.deepcopy(base) if base else {}
    for key, value in flat.items():
        if isinstance(key, str) and _FORM_SEPARATOR in key:
            plural_key, form = key.rsplit(".", 1)
            if plural_key.endswith(PLURALS_SUFFIX):
                if not isinstance(result.get(plural_key), dict):
                    result[plural_key] = {}
                result[plural_key][form] = value
                continue
        result[key] = value
    return result


def plural_source_text(plural_dict: Dict[str, Any], form: str, target_lang: str) -> Optional[str]:
    """
    The source text a target plural form is translated from (and checked against).

    A form the source lacks starts from 'other'. So does a source form that covers several counts
    in the target language but has no count placeholder in the source: English one = "One point"
    is Russian one = 1, 21, 31 ..., which needs "%1$d", so it is translated from "%1$d points".
    Without this, the model would have to add a placeholder the source text does not have, and
    the placeholder check would reject it.
    """
    present = _forms(plural_dict)
    if not present:
        return None
    base = plural_dict["other" if "other" in present else present[-1]]
    if form not in present:
        return base
    text = plural_dict[form]
    if form in get_plural_categories(target_lang) and not covers_single_count(target_lang, form):
        count = _count_placeholder(base)
        if count and count not in text:
            return base
    return text


def expand_plural_forms(source_content: Dict[str, Any], target_lang: str) -> Dict[str, Any]:
    """
    Flattened source plus the plural forms `target_lang` needs but the source lacks, each form
    holding the text it is translated from (see plural_source_text).
    """
    expanded = flatten(source_content)
    target_forms = get_plural_categories(target_lang)
    for key, plural_dict in _plurals(source_content):
        for form in set(_forms(plural_dict)) | set(target_forms):
            text = plural_source_text(plural_dict, form, target_lang)
            if text is not None:
                expanded[f"{key}.{form}"] = text
    return expanded


def _count_placeholder(text: str) -> Optional[str]:
    """The number placeholder of a plural text (%d, %1$d ...), using the Android profile."""
    from algebras.services.placeholders import count_drop_allowed, extract, profile_for_path

    profile = profile_for_path("strings.xml")
    counts = count_drop_allowed(text, profile)
    for p in extract(text, profile):
        if p.raw in counts:
            return p.raw
    return None


def _plural_context(form: str, plural_dict: Dict[str, Any], source_lang: str, target_lang: str) -> str:
    target_name = get_language_name(target_lang)
    source_name = get_language_name(source_lang)
    target_forms = get_plural_categories(target_lang)

    if form in target_forms:
        examples = get_category_examples(target_lang, form)
        usage = ""
        if examples:
            usage = f"It is shown when the count is {examples}"
            usage += "" if examples.endswith("…") else "."
    else:
        usage = (
            f"{target_name} does not use this form, so Android will not show it; "
            "translate it like the general plural."
        )

    source_forms = "; ".join(f"{f}: '{plural_dict[f]}'" for f in _forms(plural_dict))
    parts = [
        f"Android <plurals> quantity '{form}' for {target_name}. {usage}".strip(),
        f"{source_name} source forms: {source_forms}.",
        f"Write the {target_name} text for exactly these counts, using the correct "
        "grammatical form of the counted noun.",
    ]
    count = _count_placeholder(plural_dict.get("other", "") or "")
    if count and form in target_forms and not covers_single_count(target_lang, form):
        parts.append(
            "This form covers several different counts, so include the number "
            f"placeholder ({count}) instead of spelling out a number."
        )
    return " ".join(parts)


def build_plural_contexts(source_content: Dict[str, Any], source_lang: str, target_lang: str) -> Dict[str, str]:
    """Translator note for every flattened plural-form key (source forms plus the target's forms)."""
    contexts: Dict[str, str] = {}
    target_forms = get_plural_categories(target_lang)
    for key, plural_dict in _plurals(source_content or {}):
        present = _forms(plural_dict)
        if not present:
            continue
        for form in set(present) | set(target_forms):
            contexts[f"{key}.{form}"] = _plural_context(form, plural_dict, source_lang, target_lang)
    return contexts


def flat_keys(
    keys: Iterable[str],
    expanded_source: Dict[str, Any],
    flat_target: Dict[str, Any],
) -> List[str]:
    """
    Requested keys in flattened form: a whole plural ("n.__plurals__") becomes all its forms,
    and any requested plural also gets the target forms that are still missing from the target.
    Keys that do not exist in the source are dropped.
    """
    result: List[str] = []
    seen = set()

    def add(key: str) -> None:
        if key not in seen and key in expanded_source:
            seen.add(key)
            result.append(key)

    for key in keys:
        if key in expanded_source and not key.endswith(PLURALS_SUFFIX):
            add(key)
            plural_key = key.rsplit(".", 1)[0] if _FORM_SEPARATOR in key else None
        elif key.endswith(PLURALS_SUFFIX):
            plural_key = key
            for k in expanded_source:
                if k.startswith(key + "."):
                    add(k)
        else:
            plural_key = None
        if plural_key:
            for k in expanded_source:
                if k.startswith(plural_key + ".") and not flat_target.get(k):
                    add(k)
    return result


def translate_plurals(
    translate: Callable[[Dict[str, Any], Dict[str, Any], List[str], Optional[Dict[str, str]]], Dict[str, Any]],
    source_content: Dict[str, Any],
    target_content: Dict[str, Any],
    keys: Iterable[str],
    target_lang: str,
    contexts: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Translate Android content with plurals flattened and expanded.

    `translate(flat_source, flat_target, flat_keys, contexts)` runs the actual (two-pass)
    translation on flat content. Returns the nested target content.
    """
    target_content = target_content or {}
    expanded_source = expand_plural_forms(source_content, target_lang)
    flat_target = flatten(target_content)
    requested = flat_keys(keys, expanded_source, flat_target)
    if not requested:
        return copy.deepcopy(target_content)
    translated = translate(expanded_source, flat_target, requested, contexts)
    return unflatten(translated, target_content)
