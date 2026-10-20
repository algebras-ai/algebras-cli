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

# printf-style specifiers iOS accepts: %d, %ld, %lu, %@, %1$@, %.2f, ...
_IOS_FORMAT_SPECIFIER = re.compile(
    r"%(?:\d+\$)?[-+ 0#']*\d*(?:\.\d+)?(?:hh|h|ll|l|q|L|z|t|j)?[@dDiuUxXoOfFeEgGaAcCsSp]"
)


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
    return sorted(_IOS_FORMAT_SPECIFIER.findall(text.replace("%%", "")))


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

    count_specifiers = extract_format_specifiers(plural_dict.get("other", ""))
    if count_specifiers and form in get_plural_categories(target_lang) and not _covers_single_count(target_lang, form):
        parts.append(
            "This form covers several different counts, so include the number "
            f"placeholder ({count_specifiers[0]}) instead of spelling out a number."
        )
    parts.append("Keep every placeholder (such as %d, %ld, %@, %1$@) exactly as written.")
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


def split_plural_passes(
    keys: List[str], contexts: Dict[str, str]
) -> Tuple[List[str], List[str]]:
    """
    Split keys into (first pass, second pass): plural forms other than 'other' go second,
    so they can be anchored to their entry's translated 'other' and use the same wording.
    """
    first: List[str] = []
    second: List[str] = []
    for key in keys:
        if key in contexts and not key.endswith(".other"):
            second.append(key)
        else:
            first.append(key)
    return first, second


def anchor_plural_contexts(
    contexts: Dict[str, str], keys: List[str], translated: Dict[str, Any]
) -> Dict[str, str]:
    """Contexts for `keys`, each extended with its entry's translated 'other' form when known."""
    anchored = dict(contexts)
    for key in keys:
        base = key.rsplit(".", 1)[0]
        other = translated.get(f"{base}.other")
        if key in anchored and isinstance(other, str) and other.strip():
            anchored[key] += (
                f" This entry's general plural form is already translated as '{other}'. "
                "Use the same wording and the same noun, inflected for this form."
            )
    return anchored


def validate_plural_forms(
    target_raw: Dict[str, Any],
    source_raw: Dict[str, Any],
    target_lang: str,
) -> List[str]:
    """Warnings for missing plural forms or placeholders that don't match the source."""
    warnings: List[str] = []
    target_by_key = dict(find_plural_rule_dicts(target_raw))
    required = get_plural_categories(target_lang)

    for key, source_dict in find_plural_rule_dicts(source_raw):
        target_dict = target_by_key.get(key)
        if target_dict is None:
            warnings.append(f"{key}: plural entry is missing")
            continue

        missing = [f for f in required if not isinstance(target_dict.get(f), str)]
        if missing:
            warnings.append(f"{key}: missing plural forms {', '.join(missing)}")

        allowed = set()
        for f in _present_forms(source_dict):
            allowed.update(extract_format_specifiers(source_dict[f]))
        count_specifiers = set(extract_format_specifiers(source_dict.get("other", "")))

        for form in _present_forms(target_dict):
            found = set(extract_format_specifiers(target_dict[form]))
            unexpected = found - allowed
            if unexpected:
                warnings.append(
                    f"{key}.{form}: placeholders not in source: {', '.join(sorted(unexpected))}"
                )
            lost = count_specifiers - found
            if lost and form in required and not _covers_single_count(target_lang, form):
                warnings.append(
                    f"{key}.{form}: missing placeholder {', '.join(sorted(lost))}"
                )

    return warnings


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

    def _merge_missing_keys(data: Dict[str, Any], source_data: Dict[str, Any], prefix: str = "") -> None:
        # Copy entries present in source but missing from data, so their
        # (possibly plural-rule) structure exists before translation.
        for key, source_value in source_data.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if key not in data:
                data[key] = copy.deepcopy(source_value)
                continue

            value = data[key]
            if isinstance(value, dict) and isinstance(source_value, dict) and not _is_plural_rule_dict(value):
                _merge_missing_keys(value, source_value, current_key)

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
    return result