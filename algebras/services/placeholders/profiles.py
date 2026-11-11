"""
Placeholder profiles: which syntaxes apply to a file.

A profile is chosen per file. Format-specific profiles are registered by file extension; anything
else gets the generic profile, which covers the common syntaxes and is safe to apply to any text
(a false positive is only masked and put back unchanged).

Config override, per source file:

    source_files:
      res/values/strings.xml:
        destination_path: ...
        placeholders: [printf, xml_tag]
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple

from algebras.services.placeholders.syntaxes import Syntax, get_syntax


@dataclass(frozen=True)
class PlaceholderProfile:
    name: str
    syntax_names: Tuple[str, ...]
    # Placeholder values that never need masking in this profile (e.g. "%%" where it is literal).
    literal_values: frozenset = field(default_factory=frozenset)

    @property
    def syntaxes(self) -> Tuple[Syntax, ...]:
        return tuple(get_syntax(n) for n in self.syntax_names)

    @property
    def cache_id(self) -> str:
        return f"{self.name}:{','.join(self.syntax_names)}"


GENERIC_PROFILE = PlaceholderProfile(
    name="generic",
    syntax_names=(
        "xml_tag",
        "objc_variable",
        "printf",
        "python_percent",
        "ruby",
        "i18next",
        "js_template",
        "icu_simple",
    ),
)

_PROFILES_BY_EXTENSION: Dict[str, PlaceholderProfile] = {}


def register_profile(extensions: Iterable[str], profile: PlaceholderProfile) -> None:
    """Use `profile` for files with these extensions (e.g. [".xml"])."""
    for ext in extensions:
        _PROFILES_BY_EXTENSION[ext.lower()] = profile


def _extension(file_path: str) -> str:
    lower = file_path.lower()
    # Longest registered extension wins (".stringsdict" before ".strings").
    for ext in sorted(_PROFILES_BY_EXTENSION, key=len, reverse=True):
        if lower.endswith(ext):
            return ext
    return os.path.splitext(lower)[1]


def profile_for_path(file_path: Optional[str], config=None) -> PlaceholderProfile:
    """Profile for a source file: config override, then the format's profile, then generic."""
    if not file_path:
        return GENERIC_PROFILE

    if config is not None:
        try:
            source_files = config.get_source_files() or {}
        except Exception:
            source_files = {}
        file_config = source_files.get(file_path) or {}
        names = file_config.get("placeholders") if isinstance(file_config, dict) else None
        if names:
            names = tuple(names)
            for n in names:
                get_syntax(n)  # fail early on typos
            return PlaceholderProfile(name=f"config:{file_path}", syntax_names=names)

    return _PROFILES_BY_EXTENSION.get(_extension(file_path), GENERIC_PROFILE)
