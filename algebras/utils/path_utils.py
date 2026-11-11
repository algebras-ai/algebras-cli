import os
import re
from typing import Iterable, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from algebras.config import Config

LOCALE_PLACEHOLDER = "%algebras_locale_code%"


def _split_locale(code: str) -> List[str]:
    return [p for p in re.split(r"[-_]", code.strip()) if p]


def android_qualifier(locale_code: str) -> str:
    """
    The Android resource-folder qualifier for a BCP-47 locale code (the part after "values-").

    "ru" -> "ru", "pt-BR"/"pt_BR" -> "pt-rBR", "zh-Hans" -> "b+zh+Hans", "zh-Hans-CN" ->
    "b+zh+Hans+CN", "es-419" -> "b+es+419". Android ignores folders such as "values-pt-BR" or
    "values-uz-Cyrl"; a region needs the "r" prefix and anything else needs the "b+" form.
    A code that already is a qualifier ("b+...", "xx-rYY") is returned unchanged.
    """
    if not locale_code or "+" in locale_code or locale_code.startswith("%"):
        return locale_code
    parts = _split_locale(locale_code)
    if not parts:
        return locale_code
    if len(parts) == 2 and re.fullmatch(r"r[A-Za-z]{2}", parts[1]) and parts[1][1:].isupper():
        return f"{parts[0].lower()}-{parts[1]}"  # already "xx-rYY"
    out = [parts[0].lower()]
    has_region = False
    other = False
    for part in parts[1:]:
        if len(part) == 4 and part.isalpha():
            out.append(part.title())  # script
            other = True
        elif (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit()):
            out.append(part.upper())  # region
            has_region = True
        else:
            out.append(part.lower())  # variant
            other = True
    if len(out) == 1:
        return out[0]
    # The legacy "-rYY" form only takes a two-letter region; a UN M.49 region (419) needs "b+".
    if len(out) == 2 and has_region and not other and out[1].isalpha():
        return f"{out[0]}-r{out[1]}"
    return "b+" + "+".join(out)


def locale_from_android_qualifier(qualifier: str) -> str:
    """Reverse of android_qualifier: "b+uz+Cyrl" -> "uz-Cyrl", "pt-rBR" -> "pt-BR", "ru" -> "ru"."""
    if qualifier.startswith("b+"):
        return "-".join(p for p in qualifier[2:].split("+") if p)
    m = re.fullmatch(r"([A-Za-z]{2,3})-r([A-Za-z]{2})", qualifier)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return qualifier


def _normalized_locale(code: str) -> str:
    return "-".join(_split_locale(code)).lower()


def match_android_qualifier(qualifier: str, languages: Iterable[str]) -> Optional[str]:
    """The configured language that an Android values-<qualifier> folder stands for, if any."""
    wanted = _normalized_locale(locale_from_android_qualifier(qualifier))
    for lang in languages:
        if lang and _normalized_locale(lang) == wanted:
            return lang
    return None


def is_android_resource_pattern(destination_pattern: str) -> bool:
    """A .xml destination with a values-%algebras_locale_code% folder (Android string resources)."""
    if not destination_pattern.lower().endswith(".xml"):
        return False
    segments = re.split(r"[\\/]", destination_pattern)
    return any(seg.startswith("values-" + LOCALE_PLACEHOLDER) for seg in segments[:-1])


def _explicit_mapping(locale_code: str, config: Optional['Config']) -> Optional[str]:
    if config is None:
        return None
    mapped = config.get_destination_locale_code(locale_code)
    return mapped if mapped != locale_code else None


def destination_locale_code(destination_pattern: str, locale_code: str, config: Optional['Config'] = None) -> str:
    """
    The value that replaces %algebras_locale_code% in destination_pattern.

    An explicit mapping in the config wins and is used unchanged. Otherwise Android resource paths
    get an Android qualifier (pt-BR -> pt-rBR, uz-Cyrl -> b+uz+Cyrl); other paths use the code as is.
    """
    mapped = _explicit_mapping(locale_code, config)
    if mapped is not None:
        return mapped
    if is_android_resource_pattern(destination_pattern):
        return android_qualifier(locale_code)
    return locale_code


def resolve_destination_path(destination_pattern: str, locale_code: str, config: Optional['Config'] = None) -> str:
    """
    Resolve a destination path pattern by replacing placeholders with actual locale code.

    Args:
        destination_pattern: Path pattern with %algebras_locale_code% placeholder
        locale_code: The actual locale code to substitute (used for API calls)
        config: Optional Config instance to get mapped locale code for destination paths

    Returns:
        Resolved destination path
    """
    code = destination_locale_code(destination_pattern, locale_code, config)
    return destination_pattern.replace(LOCALE_PLACEHOLDER, code)


_warned_legacy_folders: Set[str] = set()


def warn_legacy_android_folder(destination_pattern: str, locale_code: str, config: Optional['Config'] = None) -> None:
    """
    Warn once when a target folder exists under the old raw-code name (values-uz-Cyrl), which
    Android ignores, so the user can rename it. Files are never moved automatically.
    """
    if not is_android_resource_pattern(destination_pattern) or _explicit_mapping(locale_code, config) is not None:
        return
    legacy = destination_pattern.replace(LOCALE_PLACEHOLDER, locale_code)
    current = resolve_destination_path(destination_pattern, locale_code, config)
    if legacy == current:
        return
    legacy_dir = os.path.dirname(os.path.normpath(legacy))
    if os.path.isfile(os.path.normpath(legacy)):
        _warn_legacy_dir(legacy_dir, os.path.dirname(os.path.normpath(current)))


def warn_legacy_android_dir(values_dir: str, locale_code: str) -> None:
    """Same warning for a values-<raw code> folder found while scanning (no destination pattern)."""
    qualifier = android_qualifier(locale_code)
    folder = os.path.basename(os.path.normpath(values_dir))
    if folder != f"values-{qualifier}":
        _warn_legacy_dir(values_dir, os.path.join(os.path.dirname(os.path.normpath(values_dir)), f"values-{qualifier}"))


def _warn_legacy_dir(legacy_dir: str, expected_dir: str) -> None:
    key = os.path.abspath(legacy_dir)
    if key in _warned_legacy_folders:
        return
    _warned_legacy_folders.add(key)
    import click

    click.echo(
        click.style(
            f"Warning: Android ignores the folder '{legacy_dir}'; rename it to '{expected_dir}'.",
            fg="yellow",
        ),
        err=True,
    )


def determine_target_path(source_path: str, source_lang: str, target_lang: str) -> str:
    """
    Determine the target file path by replacing the source language folder with target language folder.
    
    Args:
        source_path: The source file path
        source_lang: Source language code
        target_lang: Target language code
        
    Returns:
        Target file path
    """
    # Replace the source language folder with target language folder if present
    target_path = source_path
    
    # Handle Android values directory structure first (highest priority)
    # Pattern: .../values/*.xml -> .../values-{lang}/*.xml
    if source_path.endswith('.xml'):
        path_parts = os.path.normpath(source_path).split(os.sep)
        
        # Look for values directory in the path
        for i, part in enumerate(path_parts):
            if part == "values":
                # Convert /values/ to /values-{target_lang}/
                path_parts[i] = f"values-{android_qualifier(target_lang)}"
                target_path = os.path.join(*path_parts)
                return target_path
            elif part.startswith("values-"):
                # Replace /values-{source_lang}/ with /values-{target_lang}/
                path_parts[i] = f"values-{android_qualifier(target_lang)}"
                target_path = os.path.join(*path_parts)
                return target_path
    
    # Handle path separators for different operating systems
    if f"/{source_lang}/" in source_path or f"\\{source_lang}\\" in source_path:
        target_path = source_path.replace(f"/{source_lang}/", f"/{target_lang}/")
        target_path = target_path.replace(f"\\{source_lang}\\", f"\\{target_lang}\\")
    elif source_path.endswith(f"/{source_lang}") or source_path.endswith(f"\\{source_lang}"):
        target_path = source_path[:-len(source_lang)] + target_lang
    
    # Check for language-specific naming patterns in directories
    path_parts = os.path.normpath(source_path).split(os.sep)
    for i, part in enumerate(path_parts):
        if part == source_lang or part.lower() == source_lang.lower():
            path_parts[i] = target_lang
            target_path = os.path.join(*path_parts)
            break
        # Check for locale directories like 'en-US', 'es-ES', etc.
        if part.startswith(f"{source_lang}-") or part.startswith(f"{source_lang}_"):
            prefix = part[:len(source_lang)]
            suffix = part[len(source_lang):]
            path_parts[i] = f"{target_lang}{suffix}"
            target_path = os.path.join(*path_parts)
            break
    
    return target_path 