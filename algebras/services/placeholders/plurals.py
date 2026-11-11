"""Plural-form exemption: which count placeholders a plural form may leave out."""

from typing import FrozenSet

from algebras.services.placeholders.engine import count_drop_allowed
from algebras.services.placeholders.profiles import GENERIC_PROFILE, PlaceholderProfile
from algebras.utils.plural_rules import PLURAL_CATEGORY_ORDER, covers_single_count


def drop_allowed_for_key(
    key_path: str,
    source_text: str,
    target_lang: str,
    profile: PlaceholderProfile = GENERIC_PROFILE,
) -> FrozenSet[str]:
    """
    Count placeholders the target may omit for this key. Only plural forms (last key segment is a
    CLDR category other than "other") that cover a single count in the target language qualify:
    German "one" may read "Ein Element", Russian "one" may not (it also covers 21, 31 …).
    """
    form = str(key_path).rsplit(".", 1)[-1]
    if form in PLURAL_CATEGORY_ORDER and form != "other" and covers_single_count(target_lang, form):
        return count_drop_allowed(source_text, profile)
    return frozenset()
