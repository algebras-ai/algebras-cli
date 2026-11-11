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
from typing import Callable, Dict, Iterable, Optional, Tuple

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


# (file_path, config) -> profile, for formats whose syntax depends on the file's content
# (JSON, YAML, CSV …). Checked after the config override, before registered profiles.
ProfileResolver = Callable[[str, object], PlaceholderProfile]
_RESOLVERS_BY_EXTENSION: Dict[str, ProfileResolver] = {}
_RESOLVED: Dict[Tuple[str, float], PlaceholderProfile] = {}


def register_profile_resolver(extensions: Iterable[str], resolver: ProfileResolver) -> None:
    """Pick the profile per file by looking at it (see detect_profile)."""
    for ext in extensions:
        _RESOLVERS_BY_EXTENSION[ext.lower()] = resolver


def _extension(file_path: str) -> str:
    lower = file_path.lower()
    # Longest registered extension wins (".stringsdict" before ".strings").
    known = set(_PROFILES_BY_EXTENSION) | set(_RESOLVERS_BY_EXTENSION)
    for ext in sorted(known, key=len, reverse=True):
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

    ext = _extension(file_path)
    resolver = _RESOLVERS_BY_EXTENSION.get(ext)
    if resolver is not None:
        try:
            cache_key = (os.path.abspath(file_path), os.path.getmtime(file_path))
        except OSError:
            cache_key = None
        if cache_key is not None and cache_key in _RESOLVED:
            return _RESOLVED[cache_key]
        profile = resolver(file_path, config)
        if cache_key is not None:
            _RESOLVED[cache_key] = profile
        return profile

    return _PROFILES_BY_EXTENSION.get(ext, GENERIC_PROFILE)


def detect_profile(
    texts: Iterable[str],
    candidates: Iterable[str],
    name: str,
    always: Iterable[str] = (),
    min_count: int = 1,
) -> PlaceholderProfile:
    """
    Profile with the candidate syntaxes that actually occur in `texts` (a source file's values),
    plus `always`. Candidate order is kept, so list more specific syntaxes first
    (e.g. "i18next" before "icu_simple").
    """
    from algebras.services.placeholders.engine import extract  # avoid import cycle

    candidates = tuple(candidates)
    full = PlaceholderProfile(name=f"{name}:all", syntax_names=tuple(dict.fromkeys(tuple(always) + candidates)))
    counts: Dict[str, int] = {}
    for text in texts:
        for p in extract(text, full):
            counts[p.syntax] = counts.get(p.syntax, 0) + 1
    found = tuple(n for n in candidates if counts.get(n, 0) >= min_count)
    names = tuple(dict.fromkeys(tuple(always) + found))
    return PlaceholderProfile(name=f"{name}:{'+'.join(found) or 'none'}", syntax_names=names)
