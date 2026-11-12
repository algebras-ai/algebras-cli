"""
iOS .strings: placeholder profile and in-place fix writer.

Values are Objective-C/Swift `String(format:)` strings: %@, %d, %ld, %lld, %lu, %.2f, %1$@, %%.
Markup tags occasionally appear as text (`<a href="%@">link</a>`, `<b>`), so tags are masked too:
the whole opening tag, attributes included, is one token, and the text between tags stays
translatable.

The profile is registered for ".strings" only; ".stringsdict" is a separate format with its own
module. The registries match the longest extension first, so ".stringsdict" files never fall back
to this one.

Projects that put other placeholder styles in .strings files (e.g. `{name}` replaced in code) can
override the profile per source file in the config: `placeholders: [printf, xml_tag, icu_simple]`.
"""

from typing import Dict

from algebras.services.placeholders.fix_writers import KeyPath, register_fix_writer
from algebras.services.placeholders.profiles import PlaceholderProfile, register_profile
from algebras.utils.ios_strings_handler import update_ios_strings_file_in_place

IOS_STRINGS_PROFILE = PlaceholderProfile(name="ios_strings", syntax_names=("xml_tag", "printf"))


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: str = "", config=None) -> None:
    """Write fixed values back, changing only those entries (comments, order and spacing are kept)."""
    updates = {path[0]: value for path, value in fixes.items() if len(path) == 1}
    update_ios_strings_file_in_place(target_file, updates)


register_profile([".strings"], IOS_STRINGS_PROFILE)
register_fix_writer([".strings"], write_fixes)
