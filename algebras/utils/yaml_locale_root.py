"""
Rails-style YAML locale files: the locale is the file's single top-level key.

    # config/locales/en.yml          # config/locales/ru.yml
    en:                               ru:
      greeting: "Hello %{name}"         greeting: "Привет, %{name}"

Rails merges every locale file by that root key, so a translated file must be rooted at its own
locale: a ru.yml rooted at `en:` loads as English and leaves `ru` empty.

The CLI handles this in two places:

- Comparing: a target is keyed under the *source* root before its keys are compared with the
  source's (align_target), so `en.greeting` matches `ru.greeting` and every key name the CLI shows
  or accepts (--force, --retranslate, status, missing/outdated keys) is in source terms.
- Writing: content keyed under the source root is re-rooted at the target's locale code
  (reroot_for_target) before it is written.

A file is Rails-style when it has exactly one top-level key, that key's value is a mapping and the
key names the source language: the language code itself or its mapped locale code
(Config.get_destination_locale_code), compared case-insensitively with `_` and `-` treated alike.
YAML with several top-level keys, or one top-level key that is not the source locale, is left as
it is.

The target root is the same locale code that goes into the destination path
(Config.get_destination_locale_code): `ru`, or `pt-BR` for a `{"pt_BR": "pt-BR"}` mapping. Rails
itself uses `pt-BR`-style codes, so a project whose files are named that way gets matching roots;
a mapped code that is not a locale (e.g. an Android `b+uz+Cyrl` folder name) falls back to the
language code.

A target already rooted at the source locale (`en:` inside ru.yml, written by older versions) is
read as the target locale and rewritten with the correct root on the next write.
"""

import re
from typing import Any, Optional, Set

# A top-level key that names a locale: en, pt-BR, zh_Hant, sr-Latn-RS.
LOCALE_KEY = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$")


def is_yaml_path(file_path: Optional[str]) -> bool:
    return bool(file_path) and str(file_path).lower().endswith((".yaml", ".yml"))


def locale_root(data: Any) -> Optional[str]:
    """The top-level locale key of a Rails-style file (`en:` holding everything), or None."""
    if isinstance(data, dict) and len(data) == 1:
        (key,) = data
        if isinstance(key, str) and LOCALE_KEY.match(key) and isinstance(data[key], dict):
            return key
    return None


def _norm(code: Any) -> str:
    return str(code).replace("_", "-").lower()


def _mapped(language: str, config: Any) -> Optional[str]:
    if config is None:
        return None
    try:
        mapped = config.get_destination_locale_code(language)
    except Exception:
        return None
    return mapped if isinstance(mapped, str) else None


def _codes(language: Optional[str], config: Any) -> Set[str]:
    if not language:
        return set()
    codes = {_norm(language)}
    mapped = _mapped(language, config)
    if mapped:
        codes.add(_norm(mapped))
    return codes


def root_code(language: str, config: Any = None) -> str:
    """The root key a target file gets: its destination locale code (as in the path)."""
    mapped = _mapped(language, config)
    if mapped and LOCALE_KEY.match(mapped):
        return mapped
    return language


def source_root(source_data: Any, source_language: Optional[str] = None, config: Any = None) -> Optional[str]:
    """
    The root key of a Rails-style source file, or None.

    Without a source language (callers that do not know it) any single top-level locale key
    holding a mapping counts.
    """
    root = locale_root(source_data)
    if root is None:
        return None
    if source_language is None or _norm(root) in _codes(source_language, config):
        return root
    return None


def target_root(
    target_data: Any,
    s_root: Optional[str],
    source_language: Optional[str] = None,
    target_language: Optional[str] = None,
    config: Any = None,
) -> Optional[str]:
    """
    The root key of a target paired with a Rails source rooted at `s_root`: the target's own locale
    or, in a file written by older versions, the source's. None if the target is not Rails-style.
    """
    if s_root is None:
        return None
    root = locale_root(target_data)
    if root is None:
        return None
    if root == s_root or target_language is None:
        return root
    if _norm(root) in _codes(target_language, config) | _codes(source_language, config) | {_norm(s_root)}:
        return root
    return None


def align_target(
    source_data: Any,
    target_data: Any,
    source_language: Optional[str] = None,
    target_language: Optional[str] = None,
    config: Any = None,
) -> Any:
    """`target_data` keyed under the source's root, so its keys compare with the source's."""
    s_root = source_root(source_data, source_language, config)
    t_root = target_root(target_data, s_root, source_language, target_language, config)
    if t_root is None or t_root == s_root:
        return target_data
    return {s_root: target_data[t_root]}


def target_key(key: str, s_root: Optional[str], t_root: Optional[str]) -> str:
    """A dotted key in source terms (`en.greeting`) as it is named in the target file."""
    if s_root and t_root and s_root != t_root and (key == s_root or key.startswith(s_root + ".")):
        return t_root + key[len(s_root):]
    return key


def reroot_for_target(
    content: Any,
    source_data: Any,
    source_language: Optional[str],
    target_language: str,
    config: Any = None,
) -> Any:
    """Content keyed under the source's root, re-rooted at the target's locale code for writing."""
    s_root = source_root(source_data, source_language, config)
    if s_root is None or not isinstance(content, dict) or list(content) != [s_root]:
        return content
    code = root_code(target_language, config)
    if code == s_root:
        return content
    return {code: content[s_root]}


def misrooted(target_data: Any, s_root: Optional[str], target_language: str, config: Any = None) -> bool:
    """True if an existing target is rooted at the source locale instead of its own."""
    return (
        s_root is not None
        and locale_root(target_data) == s_root
        and _norm(s_root) not in _codes(target_language, config) | {_norm(root_code(target_language, config))}
    )


def migration_notice(target_file: str, s_root: str, target_language: str, config: Any = None) -> str:
    return (
        f"{target_file}: root key '{s_root}:' is the source locale; "
        f"rewriting it as '{root_code(target_language, config)}:' so Rails loads it as {target_language}"
    )
