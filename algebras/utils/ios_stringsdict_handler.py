"""
iOS .stringsdict localization file handler
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

from algebras.utils.plural_rules import (
    get_category_examples,
    get_language_name,
    get_plural_categories,
)


def read_ios_stringsdict_file(file_path: str) -> Dict[str, Any]:
    """
    Read an iOS .stringsdict localization file and extract key-value pairs.
    
    Args:
        file_path: Path to the iOS .stringsdict file
        
    Returns:
        Dictionary containing the translation content
    """
    if not os.path.exists(file_path):
        return {}
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Find the main dict element
        main_dict = root.find('.//dict')
        if main_dict is None:
            return {}
        
        return _parse_dict_element(main_dict)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in .stringsdict file {file_path}: {e}")


def write_ios_stringsdict_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write a dictionary to an iOS .stringsdict localization file.
    
    Args:
        file_path: Path to the iOS .stringsdict file
        content: Dictionary to write
    """
    # Create the XML structure
    root = ET.Element("plist")
    root.set("version", "1.0")
    
    # Add DOCTYPE
    # Note: ElementTree doesn't handle DOCTYPE well, so we'll add it manually later
    
    main_dict = ET.SubElement(root, "dict")
    _dict_to_xml(content, main_dict)
    
    # Create the tree and write
    tree = ET.ElementTree(root)
    
    # Write with proper formatting
    _write_formatted_xml(tree, file_path)


def _parse_dict_element(dict_elem: ET.Element) -> Dict[str, Any]:
    """
    Parse a dict XML element into a Python dictionary.
    
    Args:
        dict_elem: The dict XML element
        
    Returns:
        Python dictionary representation
    """
    result = {}
    
    # Process key-value pairs
    children = list(dict_elem)
    for i in range(0, len(children), 2):
        if i + 1 >= len(children):
            break
            
        key_elem = children[i]
        value_elem = children[i + 1]
        
        if key_elem.tag != "key":
            continue
            
        key = key_elem.text or ""
        value = _parse_value_element(value_elem)
        result[key] = value
    
    return result


def _parse_value_element(elem: ET.Element) -> Any:
    """
    Parse a value XML element (string, dict, etc.) into a Python value.
    
    Args:
        elem: The value XML element
        
    Returns:
        Python value representation
    """
    if elem.tag == "string":
        return elem.text or ""
    elif elem.tag == "dict":
        return _parse_dict_element(elem)
    elif elem.tag == "integer":
        return int(elem.text or "0")
    elif elem.tag == "real":
        return float(elem.text or "0.0")
    elif elem.tag == "true":
        return True
    elif elem.tag == "false":
        return False
    else:
        # Default to string representation
        return elem.text or ""


def _dict_to_xml(data: Dict[str, Any], parent: ET.Element) -> None:
    """
    Convert a Python dictionary to XML dict format.
    
    Args:
        data: Dictionary to convert
        parent: Parent XML element to append to
    """
    # Sort keys for consistent output
    sorted_keys = sorted(data.keys())
    
    for key in sorted_keys:
        value = data[key]
        
        # Add key element
        key_elem = ET.SubElement(parent, "key")
        key_elem.text = str(key)
        
        # Add value element
        _value_to_xml(value, parent)


def _value_to_xml(value: Any, parent: ET.Element) -> None:
    """
    Convert a Python value to appropriate XML element.
    
    Args:
        value: Value to convert
        parent: Parent XML element to append to
    """
    if isinstance(value, dict):
        dict_elem = ET.SubElement(parent, "dict")
        _dict_to_xml(value, dict_elem)
    elif isinstance(value, bool):
        if value:
            ET.SubElement(parent, "true")
        else:
            ET.SubElement(parent, "false")
    elif isinstance(value, int):
        int_elem = ET.SubElement(parent, "integer")
        int_elem.text = str(value)
    elif isinstance(value, float):
        real_elem = ET.SubElement(parent, "real")
        real_elem.text = str(value)
    else:
        # Default to string
        string_elem = ET.SubElement(parent, "string")
        string_elem.text = str(value)


def _write_formatted_xml(tree: ET.ElementTree, file_path: str) -> None:
    """
    Write XML tree to file with proper formatting and DOCTYPE.
    
    Args:
        tree: ElementTree to write
        file_path: Path to write to
    """
    # First, format the XML
    _indent_xml(tree.getroot())
    
    # Write to file with DOCTYPE
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n')
        
        # Write the rest of the XML
        xml_str = ET.tostring(tree.getroot(), encoding='unicode')
        f.write(xml_str)
        f.write('\n')


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """
    Add proper indentation to XML elements for pretty printing.
    
    Args:
        elem: Element to indent
        level: Current indentation level
    """
    indent = "\n" + level * "\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "\t"
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def extract_translatable_strings(content: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract translatable strings from .stringsdict content.
    This flattens the nested structure to get just the translatable text values.
    
    Args:
        content: Parsed .stringsdict content
        
    Returns:
        Flat dictionary of translatable strings with dot-notation keys
    """
    result = {}
    
    def _extract_from_dict(data: Dict[str, Any], prefix: str = "") -> None:
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Check if this is a plural rule dict (contains NSStringFormatSpecTypeKey)
                if "NSStringFormatSpecTypeKey" in value and value.get("NSStringFormatSpecTypeKey") == "NSStringPluralRuleType":
                    # Extract plural forms (zero, one, two, few, many, other)
                    plural_forms = ["zero", "one", "two", "few", "many", "other"]
                    for form in plural_forms:
                        if form in value and isinstance(value[form], str):
                            result[f"{current_key}.{form}"] = value[form]
                else:
                    # Recursively process nested dicts
                    _extract_from_dict(value, current_key)
            elif isinstance(value, str):
                # Skip format keys and other metadata
                if not key.startswith("NSString"):
                    result[current_key] = value
    
    _extract_from_dict(content)
    return result


PLURAL_FORMS = ("zero", "one", "two", "few", "many", "other")

FORMAT_KEY = "NSStringLocalizedFormatKey"
# Plural-rule metadata: never translated, must equal the source's.
TYPE_KEYS = ("NSStringFormatSpecTypeKey", "NSStringFormatValueTypeKey")


def _profile():
    """The .stringsdict placeholder profile (%#@var@ references + printf incl. %@)."""
    from algebras.services.placeholders.formats.ios_stringsdict import IOS_STRINGSDICT_PROFILE

    return IOS_STRINGSDICT_PROFILE


def _is_plural_rule_dict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("NSStringFormatSpecTypeKey") == "NSStringPluralRuleType"
    )


def find_plural_rule_dicts(content: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """(dot-notation key, plural rule dict) pairs, keyed the same way as extract_translatable_strings."""
    found: List[Tuple[str, Dict[str, Any]]] = []

    def _walk(data: Dict[str, Any], prefix: str) -> None:
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key
            if _is_plural_rule_dict(value):
                found.append((current_key, value))
            elif isinstance(value, dict):
                _walk(value, current_key)

    _walk(content, "")
    return found


def extract_format_specifiers(text: str) -> List[str]:
    """Placeholders in `text` (%d, %1$@, %#@items@ …; not the %% literal), via the shared engine."""
    from algebras.services.placeholders import extract

    return sorted(p.raw for p in extract(text or "", _profile()) if p.is_argument)


def _count_specifiers(text: str) -> List[str]:
    """Integer placeholders (%d, %ld, %1$lu …) in `text`: the ones a plural form's count fills."""
    from algebras.services.placeholders import count_drop_allowed

    return sorted(count_drop_allowed(text or "", _profile()))


def is_reference_only(format_key: str) -> bool:
    """True if a NSStringLocalizedFormatKey value is only variable references (e.g. "%#@items@")."""
    from algebras.services.placeholders import extract

    if not isinstance(format_key, str):
        return False
    rest = format_key
    for p in sorted(extract(format_key, _profile()), key=lambda p: p.start, reverse=True):
        if p.kind == "objc_variable":
            rest = rest[: p.start] + rest[p.end :]
    return rest.strip() == "" and rest != format_key


def _base_form(plural_dict: Dict[str, Any]) -> Optional[str]:
    present = _present_forms(plural_dict)
    if not present:
        return None
    return plural_dict["other" if "other" in present else present[-1]]


def plural_source_text(plural_dict: Dict[str, Any], form: str, target_lang: str) -> Optional[str]:
    """
    The source text to translate (and check) a target plural form against.

    A form the source lacks uses the source's 'other' text (as expand_plural_forms does). A form
    the source has keeps its text, except when the form covers several counts in the target
    language but its source text has no count placeholder: English "one: One item" cannot become
    Russian "one" (1, 21, 31 …) without "%d", so the 'other' text ("%d items") is used instead.
    Otherwise the placeholder gate would reject the "%d" the model is asked to add.
    """
    from algebras.utils.plural_rules import covers_single_count

    base = _base_form(plural_dict)
    text = plural_dict.get(form)
    if not isinstance(text, str):
        return base
    if form == "other" or form not in get_plural_categories(target_lang) or covers_single_count(target_lang, form):
        return text
    counts = set(_count_specifiers(base))
    if counts and not counts <= set(extract_format_specifiers(text)):
        return base
    return text


def plural_sources_for_translation(
    source_raw: Dict[str, Any],
    source_flat: Dict[str, Any],
    target_lang: str,
) -> Dict[str, Any]:
    """
    expand_plural_forms, plus each plural form's text replaced by plural_source_text, so every
    form is sent with the placeholders its translation must keep.
    """
    result = expand_plural_forms(source_raw, source_flat, target_lang)
    for key, plural_dict in find_plural_rule_dicts(source_raw):
        for form in PLURAL_FORMS:
            flat_key = f"{key}.{form}"
            if flat_key in result:
                text = plural_source_text(plural_dict, form, target_lang)
                if text is not None:
                    result[flat_key] = text
    return result


def _present_forms(plural_dict: Dict[str, Any]) -> List[str]:
    return [f for f in PLURAL_FORMS if isinstance(plural_dict.get(f), str)]


def _covers_single_count(language: str, form: str) -> bool:
    examples = get_category_examples(language, form)
    return bool(examples) and examples.isdigit()


def _build_plural_context(
    form: str,
    plural_dict: Dict[str, Any],
    source_lang: str,
    target_lang: str,
) -> str:
    target_name = get_language_name(target_lang)
    source_name = get_language_name(source_lang)
    examples = get_category_examples(target_lang, form)

    if form in get_plural_categories(target_lang):
        usage = ""
        if examples:
            usage = f"It is shown when the count is {examples}"
            usage += "" if examples.endswith("…") else "."
    elif form == "zero":
        usage = "It is an explicit override shown when the count is 0."
    else:
        usage = (
            f"{target_name} does not use this form, so iOS will not show it; "
            "translate it like the general plural."
        )

    source_forms = "; ".join(
        f"{f}: '{plural_dict[f]}'" for f in _present_forms(plural_dict)
    )
    parts = [
        f"iOS .stringsdict plural form '{form}' for {target_name}. {usage}".strip(),
        f"{source_name} source forms: {source_forms}.",
        f"Write the {target_name} text for exactly these counts, using the correct "
        "grammatical form of the counted noun.",
    ]

    # The general placeholder rule (keep each token unchanged) is added per text by the
    # BatchProcessor, listing that text's own tokens; only the plural-specific rule is here.
    other = plural_dict.get("other", "")
    count_specifiers = _count_specifiers(other) or [
        s for s in extract_format_specifiers(other) if "#@" not in s
    ]
    if count_specifiers and form in get_plural_categories(target_lang) and not _covers_single_count(target_lang, form):
        parts.append(
            "This form covers several different counts, so include the number "
            f"placeholder ({count_specifiers[0]}) instead of spelling out a number."
        )
    return " ".join(parts)


def expand_plural_forms(
    source_raw: Dict[str, Any],
    source_flat: Dict[str, Any],
    target_lang: str,
) -> Dict[str, Any]:
    """
    Add the plural forms `target_lang` needs but the source lacks (e.g. en one/other -> ru few/many).
    New forms take the source 'other' text as the text to translate.
    """
    expanded = dict(source_flat)
    target_forms = get_plural_categories(target_lang)

    for key, plural_dict in find_plural_rule_dicts(source_raw):
        present = _present_forms(plural_dict)
        if not present:
            continue
        base_form = "other" if "other" in present else present[-1]
        for form in target_forms:
            if form not in present:
                expanded[f"{key}.{form}"] = plural_dict[base_form]

    return expanded


def build_plural_contexts(
    source_raw: Dict[str, Any],
    source_lang: str,
    target_lang: str,
) -> Dict[str, str]:
    """Translator context for every plural-form key (source forms plus the target's required forms)."""
    contexts: Dict[str, str] = {}
    target_forms = get_plural_categories(target_lang)

    for key, plural_dict in find_plural_rule_dicts(source_raw):
        present = _present_forms(plural_dict)
        if not present:
            continue
        for form in set(present) | set(target_forms):
            contexts[f"{key}.{form}"] = _build_plural_context(
                form, plural_dict, source_lang, target_lang
            )

    return contexts


class PluralContexts(dict):
    """
    Plural notes by key, plus `anchors`: for each plural-form key, the key of the form it is
    anchored to (translated first and quoted in its context). Formats whose forms have no CLDR
    names (gettext msgstr[N]) set the anchors explicitly; otherwise a form key "<entry>.<form>"
    is anchored to "<entry>.other".
    """

    def __init__(self, notes: Any = (), anchors: Optional[Dict[str, str]] = None):
        super().__init__(notes)
        self.anchors: Dict[str, str] = dict(anchors or {})


def plural_anchor_key(key: str, contexts: Dict[str, str]) -> Optional[str]:
    """The key of the form `key` is anchored to, `key` itself for an anchor, None if not plural."""
    if key not in contexts:
        return None
    anchors = getattr(contexts, "anchors", None)
    if anchors:
        return anchors.get(key)
    return f"{key.rsplit('.', 1)[0]}.other"


def _lookup(data: Any, key: str) -> Any:
    """
    `data[key]`, or for nested content (YAML) the value at the dotted path `key`
    ("en.inbox.messages.other"); key names that contain dots are matched as a whole.
    """
    if not isinstance(data, dict):
        return None
    if key in data:
        return data[key]
    parts = key.split(".")
    for i in range(1, len(parts)):
        head = ".".join(parts[:i])
        if isinstance(data.get(head), dict):
            found = _lookup(data[head], ".".join(parts[i:]))
            if found is not None:
                return found
    return None


def split_plural_passes(
    keys: List[str], contexts: Dict[str, str]
) -> Tuple[List[str], List[str]]:
    """
    Split keys into (first pass, second pass): plural forms other than the anchor ('other', or
    the form PluralContexts.anchors names) go second, so they can be anchored to their entry's
    translated anchor form and use the same wording.
    """
    first: List[str] = []
    second: List[str] = []
    for key in keys:
        anchor = plural_anchor_key(key, contexts)
        if anchor is not None and anchor != key:
            second.append(key)
        else:
            first.append(key)
    return first, second


def anchor_plural_contexts(
    contexts: Dict[str, str],
    keys: List[str],
    translated: Dict[str, Any],
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Contexts for `keys`, each extended with its entry's translated 'other' form when known.
    `translated` and `source` may be flat or nested (dotted key paths, as for YAML).

    With `source`, the translated 'other' is quoted only if its placeholders match the source
    'other': a damaged translation (e.g. "%1$д") must not be shown to the model as the example.
    """
    from algebras.services.placeholders import verify

    anchored = dict(contexts)
    for key in keys:
        anchor = plural_anchor_key(key, contexts)
        if anchor is None or anchor == key:
            continue
        other = _lookup(translated, anchor)
        source_other = _lookup(source, anchor) if source else None
        if isinstance(other, str) and isinstance(source_other, str) and verify(source_other, other):
            continue
        if key in anchored and isinstance(other, str) and other.strip():
            anchored[key] += (
                f" This entry's general plural form is already translated as '{other}'. "
                "Use the same wording and the same noun, inflected for this form."
            )
    return anchored


def plural_form_problems(
    source_dict: Dict[str, Any],
    form: str,
    target_text: str,
    target_lang: str,
):
    """
    (source text, placeholder problems) for one target plural form, checked with the shared
    engine against plural_source_text. A form that covers a single count in the target language
    may leave out its count placeholder ("Ein Element"); every other placeholder must stay.
    """
    from algebras.services.placeholders import verify
    from algebras.services.placeholders.plurals import drop_allowed_for_key

    profile = _profile()
    source_text = plural_source_text(source_dict, form, target_lang) or ""
    drop = drop_allowed_for_key(f"_.{form}", source_text, target_lang, profile)
    return source_text, verify(source_text, target_text, profile, drop)


def missing_plural_forms(target_dict: Dict[str, Any], target_lang: str) -> List[str]:
    """CLDR forms `target_lang` needs that the target plural dict lacks."""
    return [f for f in get_plural_categories(target_lang) if not isinstance(target_dict.get(f), str)]


def validate_plural_forms(
    target_raw: Dict[str, Any],
    source_raw: Dict[str, Any],
    target_lang: str,
) -> List[str]:
    """Warnings for missing plural forms or placeholders that don't match the source."""
    warnings: List[str] = []
    target_by_key = dict(find_plural_rule_dicts(target_raw))

    for key, source_dict in find_plural_rule_dicts(source_raw):
        target_dict = target_by_key.get(key)
        if target_dict is None:
            warnings.append(f"{key}: plural entry is missing")
            continue

        missing = missing_plural_forms(target_dict, target_lang)
        if missing:
            warnings.append(f"{key}: missing plural forms {', '.join(missing)}")

        for form in _present_forms(target_dict):
            _, problems = plural_form_problems(source_dict, form, target_dict[form], target_lang)
            by_code: Dict[str, set] = {}
            for p in problems:
                by_code.setdefault(p.code, set()).add(p.placeholder)
            if by_code.get("extra"):
                warnings.append(
                    f"{key}.{form}: placeholders not in source: {', '.join(sorted(by_code['extra']))}"
                )
            if by_code.get("corrupted"):
                warnings.append(
                    f"{key}.{form}: damaged placeholders: {', '.join(sorted(by_code['corrupted']))}"
                )
            lost = by_code.get("missing", set()) | by_code.get("count_mismatch", set())
            if lost:
                warnings.append(f"{key}.{form}: missing placeholder {', '.join(sorted(lost))}")
            for p in problems:
                if p.code not in ("extra", "corrupted", "missing", "count_mismatch"):
                    warnings.append(f"{key}.{form}: {p.message}")

    return warnings


def sync_format_metadata(target_entry: Dict[str, Any], source_entry: Dict[str, Any]) -> List[str]:
    """
    Make the non-translatable keys of a target entry match the source, in place:
    NSStringFormatSpecTypeKey / NSStringFormatValueTypeKey are copied, and a
    NSStringLocalizedFormatKey that is only variable references (%#@items@) is copied too
    (a translated variable name breaks the plural lookup). A format key with text around its
    references is repaired only if its references were damaged.

    Returns the dot-notation keys (relative to the entry) that changed.
    """
    changed: List[str] = []

    def _walk(target: Dict[str, Any], source: Dict[str, Any], prefix: str) -> None:
        for key, source_value in source.items():
            path = f"{prefix}.{key}" if prefix else key
            target_value = target.get(key)
            if key in TYPE_KEYS and isinstance(source_value, str):
                if target_value != source_value:
                    target[key] = source_value
                    changed.append(path)
            elif key == FORMAT_KEY and isinstance(source_value, str) and isinstance(target_value, str):
                fixed = fixed_format_key(source_value, target_value)
                if fixed is not None:
                    target[key] = fixed
                    changed.append(path)
            elif isinstance(source_value, dict) and isinstance(target_value, dict):
                _walk(target_value, source_value, path)

    _walk(target_entry, source_entry, "")
    return changed


def format_key_problems(source_value: str, target_value: str):
    """Placeholder problems of a target NSStringLocalizedFormatKey (its %#@var@ references above all)."""
    from algebras.services.placeholders import verify

    return verify(source_value, target_value, _profile())


def fixed_format_key(source_value: str, target_value: str) -> Optional[str]:
    """
    The corrected NSStringLocalizedFormatKey, or None if it is fine or cannot be fixed safely.
    A reference-only key is copied from the source; one with text is repaired deterministically.
    """
    from algebras.services.placeholders import repair

    if not format_key_problems(source_value, target_value):
        return None
    if is_reference_only(source_value):
        return source_value
    return repair(source_value, target_value, _profile())


def update_translatable_strings(
    content: Dict[str, Any],
    translations: Dict[str, str],
    source_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update .stringsdict content with new translations.

    Keys that already exist in `content` have their translatable values
    updated in place. Keys that exist in `source_content` (e.g. the source
    language file) but are missing from `content` — such as newly added
    source strings that don't have a target entry yet — are first copied
    over from `source_content` so their structure (including plural rule
    metadata) is available, and are then translated like any other key.
    Without `source_content`, keys missing from `content` are left
    untouched, since there's no structural template to create them from.

    An entry copied from the source keeps only the strings that were
    translated: a form whose translation was rejected (e.g. its placeholders
    were damaged) is left out rather than written in the source language, and
    an entry left without its 'other' form is not added at all, so 'status'
    still reports it and the next run retries it. For entries in both files,
    the plural-rule type keys (and a reference-only format key) are copied
    from the source, since they must never differ from it.

    Args:
        content: Original .stringsdict content (typically the target file)
        translations: New translations with dot-notation keys
        source_content: Source .stringsdict content, used as a structural
            template for keys missing from `content`

    Returns:
        Updated content
    """
    import copy
    result = copy.deepcopy(content)
    # (parent dict, key, dot-notation key) of every entry copied from the source.
    copied: List[Tuple[Dict[str, Any], str, str]] = []

    def _merge_missing_keys(data: Dict[str, Any], source_data: Dict[str, Any], prefix: str = "") -> None:
        # Copy entries present in source but missing from data, so their
        # (possibly plural-rule) structure exists before translation.
        for key, source_value in source_data.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if key not in data:
                data[key] = copy.deepcopy(source_value)
                copied.append((data, key, current_key))
                continue

            value = data[key]
            if isinstance(value, dict) and isinstance(source_value, dict):
                sync_format_metadata(value, source_value)
                if not _is_plural_rule_dict(value):
                    _merge_missing_keys(value, source_value, current_key)

    def _drop_untranslated(value: Any, current_key: str) -> bool:
        """Remove source-language strings from a copied entry. False = drop the whole entry."""
        if isinstance(value, str):
            return current_key in translations or current_key.rsplit(".", 1)[-1].startswith("NSString")
        if not isinstance(value, dict):
            return True
        if _is_plural_rule_dict(value):
            for form in PLURAL_FORMS:
                if isinstance(value.get(form), str) and f"{current_key}.{form}" not in translations:
                    del value[form]
            return isinstance(value.get("other"), str)
        # A variable whose plural rule lost its 'other' form would break the whole format key,
        # so one such variable drops the entry.
        for key in list(value):
            child = value[key]
            if isinstance(child, str):
                if not key.startswith("NSString") and f"{current_key}.{key}" not in translations:
                    del value[key]  # format/type metadata stays; untranslated text goes
            elif not _drop_untranslated(child, f"{current_key}.{key}"):
                return False
        return True

    def _apply_translations(data: Dict[str, Any], prefix: str = "") -> None:
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                if _is_plural_rule_dict(value):
                    # Update plural forms
                    plural_forms = ["zero", "one", "two", "few", "many", "other"]
                    for form in plural_forms:
                        form_key = f"{current_key}.{form}"
                        if form_key in translations:
                            value[form] = translations[form_key]
                else:
                    # Recursively process nested dicts
                    _apply_translations(value, current_key)
            elif isinstance(value, str):
                # Update direct string values
                if current_key in translations and not key.startswith("NSString"):
                    data[key] = translations[current_key]

    if source_content:
        _merge_missing_keys(result, source_content)

    _apply_translations(result)

    for parent, key, current_key in copied:
        if not _drop_untranslated(parent[key], current_key):
            del parent[key]
    return result

def _string_value_spans(data: bytes) -> Dict[str, Tuple[int, int, bool]]:
    """
    Byte span of every <string> value in a plist, by dot-notation key (the keys
    extract_translatable_strings uses, plus the NSString* metadata keys).

    Span = (content start, content end, self-closing). For <string/> the span covers the tag.
    """
    import xml.parsers.expat

    spans: Dict[str, Tuple[int, int, bool]] = {}
    # One frame per open element: ("dict", key parts or None, pending key) or (tag, None, None).
    frames: List[List[Any]] = []
    key_text: List[str] = []
    open_strings: List[Tuple[Optional[str], int]] = []
    parser = xml.parsers.expat.ParserCreate()

    def _value_path() -> Optional[List[str]]:
        if not frames or frames[-1][0] != "dict" or frames[-1][1] is None or frames[-1][2] is None:
            return None
        return frames[-1][1] + [frames[-1][2]]

    def start(tag, attrs):
        index = parser.CurrentByteIndex
        if tag == "key":
            key_text.clear()
            frames.append(["key", None, None])
            return
        # The root <dict> has the empty path; any other element is the value of the pending key.
        path = [] if not any(f[0] == "dict" for f in frames) else _value_path()
        if frames and frames[-1][0] == "dict":
            frames[-1][2] = None  # the pending key is used by this value
        if tag == "dict":
            frames.append(["dict", path, None])
            return
        if tag == "string":
            content_start = data.index(b">", index) + 1
            if path is not None and data[content_start - 2 : content_start] == b"/>":
                spans[".".join(path)] = (index, content_start, True)
                path = None
            open_strings.append((".".join(path) if path is not None else None, content_start))
        frames.append([tag, None, None])

    def end(tag):
        index = parser.CurrentByteIndex
        frames.pop()
        if tag == "key":
            if frames and frames[-1][0] == "dict":
                frames[-1][2] = "".join(key_text)
        elif tag == "string":
            key, content_start = open_strings.pop()
            if key is not None and key not in spans:
                spans[key] = (content_start, index, False)

    def chars(text):
        if frames and frames[-1][0] == "key":
            key_text.append(text)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    parser.Parse(data, True)
    return spans


def write_stringsdict_fixes(file_path: str, fixes: Dict[str, str]) -> List[str]:
    """
    Replace the given string values of a .stringsdict file in place, keeping everything else
    (key order, formatting, comments) byte for byte.

    `fixes` maps dot-notation keys (plural forms such as "items_count.items.few", or metadata
    such as "items_count.NSStringLocalizedFormatKey") to their new values.
    Returns the keys that were not found in the file.
    """
    from xml.sax.saxutils import escape

    with open(file_path, "rb") as f:
        data = f.read()
    spans = _string_value_spans(data)

    edits: List[Tuple[int, int, bytes]] = []
    not_found: List[str] = []
    for key, value in fixes.items():
        span = spans.get(key)
        if span is None:
            not_found.append(key)
            continue
        start, end, self_closing = span
        encoded = escape(value).encode("utf-8")
        edits.append((start, end, b"<string>" + encoded + b"</string>" if self_closing else encoded))

    for start, end, replacement in sorted(edits, reverse=True):
        data = data[:start] + replacement + data[end:]

    if edits:
        with open(file_path, "wb") as f:
            f.write(data)
    return not_found
