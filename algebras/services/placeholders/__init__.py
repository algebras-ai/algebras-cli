"""Placeholder protection: keep %1$s, {name}, <b> … intact through translation."""

from algebras.services.placeholders.engine import (
    Masked,
    Placeholder,
    PlaceholderError,
    Problem,
    combine_context,
    count_drop_allowed,
    extract,
    mask,
    placeholder_context,
    repair,
    rewrite_context,
    token,
    unmask,
    verify,
)
from algebras.services.placeholders.profiles import (
    GENERIC_PROFILE,
    PlaceholderProfile,
    profile_for_path,
    register_profile,
)

# Register format-specific profiles and fix writers.
from algebras.services.placeholders.formats import load_all as _load_formats

_load_formats()

__all__ = [
    "GENERIC_PROFILE",
    "Masked",
    "Placeholder",
    "PlaceholderError",
    "PlaceholderProfile",
    "Problem",
    "combine_context",
    "count_drop_allowed",
    "extract",
    "mask",
    "placeholder_context",
    "profile_for_path",
    "register_profile",
    "repair",
    "rewrite_context",
    "token",
    "unmask",
    "verify",
]
