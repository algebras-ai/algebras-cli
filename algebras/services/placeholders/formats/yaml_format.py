"""
YAML locale files (.yml / .yaml): Rails i18n, Symfony translations and generic JS/Python i18n.

YAML has no placeholder syntax of its own; the app's i18n library decides. The profile is chosen
per source file (resolve_profile):

- ICU: Symfony `*+intl-icu.<locale>.yaml` files ({name}, plural/select via the ICU scanner);
- Symfony: `messages.<locale>.yaml` or any file under a `translations/` directory (%name%, plus
  {{ limit }} / {0} when they occur);
- Rails: a single top-level locale key (`en:`) or any `%{` in the values (%{name}, %<price>.2f);
- anything else: the syntaxes that actually occur in the values (i18next, ruby, printf, ...).

Markup tags (Rails `*_html` keys and the like) are masked as tokens whenever the file uses them.

Rails plural hashes, a dict whose keys are only CLDR categories (one/few/many/other, optionally
zero), are plural groups:

- translation expands them to the forms the target language needs (en one/other -> ru
  one/few/many/other), each form translated from the right source text (plural_source_text) and
  with a note on which counts it covers;
- `algebras placeholders` checks each target form against that text, allows a single-count form
  ("Ein Element") to leave out %{count}, and reports forms the target lacks (`missing_form`).

`algebras placeholders` also reports `yaml_type_coerced`: a value that is not a string any more
after loading (`key: {name}` is a mapping, `key: yes` a boolean), usually because its quoting was
lost. Its fix is the value as written, quoted.

Fixes are written in place (write_fixes): only the fixed scalars change; comments, key order,
anchors and formatting stay as they are. ruamel.yaml is not a dependency, so PyYAML's node marks
(yaml.compose) locate each scalar's exact span in the file and only that span is replaced.
"""

import copy
import json
import os
import re
import sys
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

from algebras.services.placeholders.engine import Problem, count_drop_allowed, extract, repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import KeyPath, register_fix_writer
from algebras.services.placeholders.profiles import (
    PlaceholderProfile,
    detect_profile,
    profile_for_path,
    register_profile_resolver,
)
from algebras.services.placeholders.syntaxes import SYNTAXES
from algebras.utils import yaml_locale_root
from algebras.utils.yaml_locale_root import locale_root

_EXTENSIONS = [".yaml", ".yml"]

PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")

_GENERIC_CANDIDATES = ("xml_tag", "i18next", "ruby", "python_percent", "printf", "js_template", "icu_simple")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _load(file_path: str) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _strings(data: Any) -> Iterator[str]:
    if isinstance(data, dict):
        for value in data.values():
            yield from _strings(value)
    elif isinstance(data, list):
        for value in data:
            yield from _strings(value)
    elif isinstance(data, str):
        yield data


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def resolve_profile(file_path: str, config=None) -> PlaceholderProfile:
    """Placeholder profile for a YAML source file, from its name, location and values."""
    try:
        data = _load(file_path)
    except Exception:
        data = None
    texts = list(_strings(data))
    normalized = file_path.replace("\\", "/").lower()
    base = os.path.basename(normalized)

    if "+intl-icu." in base:
        icu = "arb_icu" if "arb_icu" in SYNTAXES else "icu_simple"
        return detect_profile(texts, ("xml_tag",), "yaml-icu", always=(icu,))
    if re.match(r"messages\.[^.]+\.ya?ml$", base) or "/translations/" in f"/{normalized}":
        return detect_profile(texts, ("xml_tag", "i18next", "icu_simple"), "yaml-symfony", always=("symfony",))
    if locale_root(data) is not None or any("%{" in t for t in texts):
        return detect_profile(texts, ("xml_tag", "i18next"), "yaml-rails", always=("ruby",))
    return detect_profile(texts, _GENERIC_CANDIDATES, "yaml")


# ---------------------------------------------------------------------------
# Plural groups
# ---------------------------------------------------------------------------


def is_plural_group(value: Any) -> bool:
    """A Rails plural hash: only CLDR category keys, string values, including 'other'."""
    return (
        isinstance(value, dict)
        and "other" in value
        and all(k in PLURAL_CATEGORIES and isinstance(v, str) for k, v in value.items())
    )


def find_plural_groups(data: Any, prefix: Tuple = ()) -> List[Tuple[Tuple, Dict[str, str]]]:
    """(key path, plural group) for every plural group in `data`, keys as in the loaded dict."""
    found: List[Tuple[Tuple, Dict[str, str]]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if is_plural_group(value):
                found.append((prefix + (key,), value))
            elif isinstance(value, dict):
                found.extend(find_plural_groups(value, prefix + (key,)))
    return found


def _count_placeholder(text: str, profile: PlaceholderProfile) -> Optional[str]:
    counts = count_drop_allowed(text, profile)
    return next((p.raw for p in extract(text, profile) if p.raw in counts), None)


def plural_source_text(
    group: Dict[str, str], form: str, target_lang: str, profile: PlaceholderProfile
) -> Optional[str]:
    """
    The source text a target plural form is translated from and checked against.

    A form the source lacks starts from 'other'. So does a source form that covers several counts
    in the target language but has no count placeholder: English one = "One message" is Russian
    one = 1, 21, 31 ..., which needs %{count}, so it is translated from "%{count} messages".
    """
    from algebras.utils.plural_rules import covers_single_count, get_plural_categories

    base = group.get("other")
    if not isinstance(base, str):
        return None
    text = group.get(form)
    if not isinstance(text, str):
        return base
    if form != "other" and form in get_plural_categories(target_lang) and not covers_single_count(target_lang, form):
        count = _count_placeholder(base, profile)
        if count and count not in text:
            return base
    return text


def _target_forms(group: Dict[str, str], target_lang: str) -> List[str]:
    from algebras.utils.plural_rules import get_plural_categories

    wanted = set(group) | set(get_plural_categories(target_lang))
    return [f for f in PLURAL_CATEGORIES if f in wanted]


def expand_plural_source(content: Any, target_lang: str, profile: PlaceholderProfile) -> Any:
    """
    Copy of `content` with every plural group holding the forms `target_lang` needs (plus the
    source's own), each set to the text it is translated from (plural_source_text).
    """
    expanded = copy.deepcopy(content)
    for path, group in find_plural_groups(content):
        target_group = expanded
        for key in path:
            target_group = target_group[key]
        target_group.clear()
        for form in _target_forms(group, target_lang):
            target_group[form] = plural_source_text(group, form, target_lang, profile)
    return expanded


def _plural_context(
    form: str, group: Dict[str, str], source_lang: str, target_lang: str, profile: PlaceholderProfile
) -> str:
    from algebras.utils.plural_rules import (
        covers_single_count,
        get_category_examples,
        get_language_name,
        get_plural_categories,
    )

    target_name = get_language_name(target_lang)
    source_name = get_language_name(source_lang)
    target_forms = get_plural_categories(target_lang)
    if form == "zero":
        usage = "It is an explicit override shown when the count is 0."
    elif form in target_forms:
        examples = get_category_examples(target_lang, form)
        usage = f"It is shown when the count is {examples}" + ("" if examples.endswith("…") else ".") if examples else ""
    else:
        usage = f"{target_name} does not use this form; translate it like the general plural."

    source_forms = "; ".join(f"{f}: '{group[f]}'" for f in PLURAL_CATEGORIES if f in group)
    parts = [
        f"Plural form '{form}' for {target_name}. {usage}".strip(),
        f"{source_name} source forms: {source_forms}.",
        f"Write the {target_name} text for exactly these counts, using the correct grammatical "
        "form of the counted noun.",
    ]
    count = _count_placeholder(group.get("other", ""), profile)
    if count and form in target_forms and form != "zero" and not covers_single_count(target_lang, form):
        parts.append(
            "This form covers several different counts, so include the number placeholder "
            f"({count}) instead of spelling out a number."
        )
    return " ".join(parts)


def build_plural_contexts(
    content: Any, source_lang: str, target_lang: str, profile: PlaceholderProfile
) -> Dict[str, str]:
    """Translator note per plural form, keyed by dotted key path ("en.inbox.messages.few")."""
    contexts: Dict[str, str] = {}
    for path, group in find_plural_groups(content):
        dotted = ".".join(str(k) for k in path)
        for form in _target_forms(group, target_lang):
            contexts[f"{dotted}.{form}"] = _plural_context(form, group, source_lang, target_lang, profile)
    return contexts


def prepare_for_translation(
    content: Any, source_lang: str, target_lang: str, profile: PlaceholderProfile
) -> Tuple[Any, Dict[str, str]]:
    """(source content with expanded plural groups, plural notes by dotted key path)."""
    if not find_plural_groups(content):
        return content, {}
    return (
        expand_plural_source(content, target_lang, profile),
        build_plural_contexts(content, source_lang, target_lang, profile),
    )


def _split_plural_forms(content: Any, contexts: Dict[str, str]) -> Tuple[Any, Any, List[str]]:
    """
    (first-pass content, second-pass content, second-pass dotted keys) of expanded `content`:
    the second pass holds each plural group's forms other than 'other', the first everything else.
    """
    first = copy.deepcopy(content)
    second: Dict[str, Any] = {}
    second_keys: List[str] = []
    for path, group in find_plural_groups(content):
        dotted = ".".join(str(k) for k in path)
        later = [f for f in group if f != "other" and f"{dotted}.{f}" in contexts]
        if not later:
            continue
        first_group, second_group = first, second
        for key in path:
            first_group = first_group[key]
            second_group = second_group.setdefault(key, {})
        for form in later:
            second_group[form] = first_group.pop(form)
            second_keys.append(f"{dotted}.{form}")
    return first, second, second_keys


def _merge_in_order(template: Any, first: Any, second: Any) -> Any:
    """`first` and `second` (translated parts of `template`) merged, keys in `template`'s order."""
    if not isinstance(first, dict) or not isinstance(second, dict):
        return second
    merged: Dict[Any, Any] = {}
    order = list(template) if isinstance(template, dict) else []
    order += [k for k in list(first) + list(second) if k not in order]
    for key in order:
        if key in first and key in second:
            merged[key] = _merge_in_order(
                template.get(key) if isinstance(template, dict) else None, first[key], second[key]
            )
        elif key in first:
            merged[key] = first[key]
        elif key in second:
            merged[key] = second[key]
    return merged


def translate_plural_groups_in_two_passes(translate, content: Any, contexts: Dict[str, str]) -> Any:
    """
    Translate expanded YAML `content` (prepare_for_translation) with `translate(data, contexts)`
    in two passes, as the flat formats do: first everything but the plural forms other than
    'other', then those forms, each with its group's translated 'other' quoted in its note so
    every form uses the same wording. A damaged 'other' translation is not quoted.
    """
    from algebras.utils.ios_stringsdict_handler import anchor_plural_contexts

    first, second, second_keys = _split_plural_forms(content, contexts)
    if not second_keys:
        return translate(content, contexts)
    translated_first = translate(first, contexts)
    anchored = anchor_plural_contexts(contexts, second_keys, translated_first, content)
    translated_second = translate(second, anchored)
    return _merge_in_order(content, translated_first, translated_second)


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def _type_name(value: Any) -> str:
    return {dict: "a mapping", list: "a list", bool: "a boolean", int: "a number", float: "a number"}.get(
        type(value), type(value).__name__
    )


def _coerced_finding(key: str, path: KeyPath, source: str, raw: Optional[str], value: Any, profile) -> Finding:
    written = raw if raw is not None else str(value)
    problem = Problem(
        "yaml_type_coerced",
        written,
        f"Value is {_type_name(value)} after loading, not a string (quote it: '{written}')",
    )
    fixed = None
    if raw is not None and raw.strip() and not verify(source, raw, profile):
        fixed = raw
    return Finding(key=key, source=source, target=written, problems=[problem], path=path, fixed=fixed)


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """
    Placeholder findings for a target YAML file.

    Values are paired by key path; a Rails top-level locale key (`en:` / `ru:`, or a target still
    rooted at `en:`) is paired with the target's (yaml_locale_root.align_target). Keys and paths
    are in source terms (`en.greeting`), as status and `translate --force` name them; write_fixes
    maps them to the target's root. Plural group forms are checked against plural_source_text
    with the single-count exemption; forms the target language needs but the group lacks are `missing_form`; values
    that load as something other than a string are `yaml_type_coerced`.
    """
    from algebras.services.icu_message_service import align_source_branches
    from algebras.services.placeholders.plurals import drop_allowed_for_key
    from algebras.utils.plural_rules import get_plural_categories

    source = _load(source_file)
    target = _load(target_file)
    profile = profile_for_path(source_file, config)
    if not isinstance(source, dict) or not isinstance(target, dict):
        return []

    config_source = _config_source_language(config)
    target = yaml_locale_root.align_target(source, target, config_source, target_language, config)
    source_root = yaml_locale_root.source_root(source, config_source, config)
    target_root = locale_root(_load(target_file)) if source_root is not None else None
    prefix: Tuple = ()
    if source_root is not None and source_root in target and isinstance(target[source_root], dict):
        source, target, prefix = source[source_root], target[source_root], (source_root,)

    raw_cache: Dict[str, Any] = {}

    def raw_text(path: Tuple) -> Optional[str]:
        if "nodes" not in raw_cache:
            raw_cache["nodes"] = _compose(target_file)
        text, root = raw_cache["nodes"]
        node = _find_node(root, _target_path(tuple(str(k) for k in path), source_root, target_root))
        if node is None:
            return None
        if isinstance(node, yaml.ScalarNode):
            return node.value
        return text[node.start_mark.index : node.end_mark.index].strip()

    findings: List[Finding] = []

    def check_value(path: Tuple, source_text: str, target_value: Any, plural: bool) -> None:
        key = ".".join(str(k) for k in path)
        str_path = tuple(str(k) for k in path)
        if target_value is None:
            return  # untranslated: 'status' reports it
        if not isinstance(target_value, str):
            findings.append(_coerced_finding(key, str_path, source_text, raw_text(path), target_value, profile))
            return
        if not target_value.strip():
            return
        if not plural:  # ICU YAML: plural branches the target added are copies of 'other'
            source_text = align_source_branches(source_text, target_value)
        drop = drop_allowed_for_key(key, source_text, target_language, profile) if plural else frozenset()
        problems = verify(source_text, target_value, profile, drop)
        if problems:
            findings.append(
                Finding(
                    key=key,
                    source=source_text,
                    target=target_value,
                    problems=problems,
                    path=str_path,
                    fixed=repair(source_text, target_value, profile, drop),
                )
            )

    def walk(source_node: Dict, target_node: Dict, path: Tuple) -> None:
        for name, source_value in source_node.items():
            target_value = target_node.get(name)
            current = path + (name,)
            if is_plural_group(source_value) and isinstance(target_value, dict):
                for form, text in target_value.items():
                    source_text = plural_source_text(source_value, str(form), target_language, profile)
                    if source_text is not None:
                        check_value(current + (form,), source_text, text, plural=True)
                present = [f for f, v in target_value.items() if isinstance(v, str) and v.strip()]
                missing = [f for f in get_plural_categories(target_language) if f not in present]
                if present and missing:
                    for form in missing:
                        findings.append(
                            Finding(
                                key=".".join(str(k) for k in current + (form,)),
                                source=plural_source_text(source_value, form, target_language, profile) or "",
                                target="",
                                problems=[
                                    Problem(
                                        "missing_form",
                                        form,
                                        f"Plural form '{form}' is missing ({target_language} needs "
                                        f"{', '.join(get_plural_categories(target_language))})",
                                    )
                                ],
                                path=tuple(str(k) for k in current + (form,)),
                            )
                        )
            elif isinstance(source_value, dict):
                if isinstance(target_value, dict):
                    walk(source_value, target_value, current)
            elif isinstance(source_value, str) and source_value.strip():
                check_value(current, source_value, target_value, plural=False)

    walk(source, target, prefix)
    return findings


# ---------------------------------------------------------------------------
# In-place fix writer
# ---------------------------------------------------------------------------


def _config_source_language(config) -> Optional[str]:
    if config is None:
        return None
    try:
        language = config.get_source_language()
    except Exception:
        return None
    return language if isinstance(language, str) else None


def _target_path(path: KeyPath, source_root: Optional[str], target_root: Optional[str]) -> KeyPath:
    """A key path in source terms (("en", "greeting")) as it is named in the target file."""
    if source_root and target_root and path and path[0] == source_root:
        return (target_root,) + tuple(path[1:])
    return tuple(path)


def _compose(file_path: str) -> Tuple[str, Any]:
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    return text, yaml.compose(text, Loader=yaml.SafeLoader)


_KEY_CONSTRUCTOR = yaml.constructor.SafeConstructor()


def _key_name(node: Any) -> str:
    """The key as read_language_file sees it (str of the loaded key: `no:` is "False")."""
    try:
        return str(_KEY_CONSTRUCTOR.construct_object(node, deep=True))
    except Exception:
        return str(getattr(node, "value", ""))


def _find_node(root: Any, path: KeyPath) -> Any:
    node = root
    for part in path:
        if not isinstance(node, yaml.MappingNode):
            return None
        match = None
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode) and _key_name(key_node) == part:
                match = value_node
        if match is None:
            return None
        node = match
    return node


def _double_quoted(value: str) -> str:
    escaped = json.dumps(value, ensure_ascii=False)
    for ch, esc in (("\x85", "\\N"), (" ", "\\L"), (" ", "\\P")):
        escaped = escaped.replace(ch, esc)
    return escaped


def _plain_safe(value: str) -> bool:
    if not value or value != value.strip() or any(ch in value for ch in "\n,[]{}"):
        return False
    try:
        return yaml.safe_load(f"k: {value}") == {"k": value}
    except yaml.YAMLError:
        return False


def render_scalar(value: str, style: Optional[str]) -> str:
    """
    `value` as a one-line YAML scalar that loads back as exactly this string, in the original
    style where possible: plain stays plain only if it re-parses as the same string (so
    "%{count} items", "{name}", "yes", "a: b" get quoted), quoted styles keep their quotes.
    """
    printable = all(ch.isprintable() or ch == " " for ch in value)
    if style == '"' or not printable:
        return _double_quoted(value)
    if style in (None, "") and _plain_safe(value):
        return value
    return "'" + value.replace("'", "''") + "'"


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: Optional[str] = None, config=None) -> None:
    """
    Replace only the fixed values in `target_file`, keeping comments, key order and layout.

    Each value is located by its node marks from yaml.compose and its span is replaced by a
    re-rendered scalar (see render_scalar). The result is re-parsed and every fixed path must
    load as the fixed string, otherwise nothing is written.

    Paths may name a Rails root in source terms (("en", "greeting") for ru.yml): they are mapped
    to the target's root. A target still rooted at the source locale (`en:` inside ru.yml) gets
    its root key rewritten as the target's locale code, with a notice (yaml_locale_root).
    """
    text, root = _compose(target_file)
    replacements: List[Tuple[int, int, str]] = []
    not_found: List[KeyPath] = []

    loaded = yaml.safe_load(text)
    target_root = locale_root(loaded)
    source_root = None
    new_root = None
    if target_root is not None:
        source_language = _config_source_language(config)
        roots = {p[0] for p in fixes if p}
        source_root = next(
            (r for r in roots if r != target_root and yaml_locale_root.source_root({r: {}}, source_language, config)),
            None,
        )
        if language and yaml_locale_root.misrooted(loaded, target_root, language, config) and (
            source_language is not None and yaml_locale_root.source_root(loaded, source_language, config)
        ):
            new_root = yaml_locale_root.root_code(language, config)
            key_node = root.value[0][0]
            replacements.append((key_node.start_mark.index, key_node.end_mark.index, new_root))

    mapped_fixes: Dict[KeyPath, str] = {}
    for path, value in fixes.items():
        mapped_fixes[_target_path(tuple(path), source_root, target_root)] = value

    for path, value in mapped_fixes.items():
        node = _find_node(root, tuple(path))
        if node is None:
            not_found.append(path)
            continue
        start, end = node.start_mark.index, node.end_mark.index
        span = text[start:end]
        style = node.style if isinstance(node, yaml.ScalarNode) else "'"
        if style in ("|", ">"):
            rendered = _double_quoted(value)
            stripped = span.rstrip("\r\n")
            rendered += span[len(stripped) :]  # the block scalar's line break(s)
        else:
            rendered = render_scalar(value, style)
        replacements.append((start, end, rendered))

    if not_found:
        raise ValueError(f"Could not find {', '.join('.'.join(p) for p in not_found)} in {target_file}")

    new_text = text
    for start, end, rendered in sorted(replacements, reverse=True):
        new_text = new_text[:start] + rendered + new_text[end:]

    reloaded = yaml.safe_load(new_text)
    for path, value in mapped_fixes.items():
        if new_root is not None and path and path[0] == target_root:
            path = (new_root,) + tuple(path[1:])
        node = reloaded
        for part in path:
            node = next((v for k, v in node.items() if str(k) == part), None) if isinstance(node, dict) else None
        if node != value:
            raise ValueError(f"Writing {'.'.join(path)} to {target_file} would not keep the value; not written")

    if new_root is not None:
        # stderr: `algebras placeholders --format json` keeps stdout for the report.
        print(yaml_locale_root.migration_notice(target_file, target_root, language, config), file=sys.stderr)
    with open(target_file, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)


register_profile_resolver(_EXTENSIONS, resolve_profile)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
