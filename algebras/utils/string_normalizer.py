"""
String normalization utilities for glossary processing.

This module provides helpers to sanitize strings before sending them to
backend glossary validators that may reject certain Unicode characters.
"""

from typing import Optional


def normalize_for_glossary(text: Optional[str]) -> Optional[str]:
    """
    Normalize a string for glossary upload compatibility.

    - Replace Unicode ellipsis (\u2026, …) with three ASCII dots "..."
    - Replace non-breaking space (\u00A0) with a regular space " "

    Args:
        text: The input string (or None)

    Returns:
        The normalized string (or None if input was None)
    """
    if text is None:
        return None

    # Use literal characters to avoid confusion and ensure readability
    ELLIPSIS = "…"  # \u2026
    NBSP = "\u00A0"

    normalized = text.replace(ELLIPSIS, "...")
    normalized = normalized.replace(NBSP, " ")
    return normalized


