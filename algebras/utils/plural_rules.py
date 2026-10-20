"""
CLDR plural rules lookup, backed by Babel's bundled CLDR data.
"""

from decimal import Decimal
from functools import lru_cache
from typing import List, Optional

from babel import Locale, UnknownLocaleError

PLURAL_CATEGORY_ORDER = ("zero", "one", "two", "few", "many", "other")

_EXAMPLE_RANGE = 201
_MAX_EXAMPLES = 8
_LARGE_SAMPLES = (1000, 10000, 100000, 1000000)
_FRACTION_SAMPLES = (Decimal("0.5"), Decimal("1.5"), Decimal("2.5"))


@lru_cache(maxsize=None)
def _plural_rule(language_code: str):
    try:
        return Locale.parse(language_code.replace("_", "-"), sep="-").plural_form
    except (UnknownLocaleError, ValueError):
        return None


def is_known_language(language_code: str) -> bool:
    return _plural_rule(language_code) is not None


def get_plural_categories(language_code: str) -> List[str]:
    """
    Plural categories the language uses, in CLDR order (e.g. ru -> one, few, many, other).
    Unknown locales fall back to English-like ["one", "other"].
    """
    rule = _plural_rule(language_code)
    if rule is None:
        return ["one", "other"]
    # Babel omits "other" from tags since every language has it.
    tags = set(rule.tags) | {"other"}
    return [c for c in PLURAL_CATEGORY_ORDER if c in tags]


@lru_cache(maxsize=None)
def get_category_examples(language_code: str, category: str) -> Optional[str]:
    """
    Human-readable sample counts that select `category`, e.g. ru few ->
    "2, 3, 4, 22, 23, 24, 32, 33…", fr many -> "1000000", ru other -> "fractions such as 1.5".
    Returns None for unknown locales.
    """
    rule = _plural_rule(language_code)
    if rule is None:
        return None
    matches = [str(n) for n in range(_EXAMPLE_RANGE) if rule(n) == category]
    if matches:
        shown = ", ".join(matches[:_MAX_EXAMPLES])
        return shown + ("…" if len(matches) > _MAX_EXAMPLES else "")
    large = [str(n) for n in _LARGE_SAMPLES if rule(n) == category]
    if large:
        return ", ".join(large)
    fractions = [str(d) for d in _FRACTION_SAMPLES if rule(d) == category]
    if fractions:
        return "fractions such as " + ", ".join(fractions)
    return None


def get_language_name(language_code: str) -> str:
    try:
        return Locale.parse(language_code.replace("_", "-"), sep="-").english_name
    except (UnknownLocaleError, ValueError):
        return language_code
