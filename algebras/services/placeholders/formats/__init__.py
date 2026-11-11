"""
Format-specific placeholder support.

Each module in this package registers what one file format needs, at import time:

    from algebras.services.placeholders.profiles import PlaceholderProfile, register_profile
    from algebras.services.placeholders.fix_writers import register_fix_writer

    register_profile([".xml"], PlaceholderProfile(name="android", syntax_names=("printf", "xml_tag")))
    register_fix_writer([".xml"], write_fixes)

All modules here are imported automatically (see load_all), so adding a format means adding a file.
"""

import importlib
import pkgutil

_loaded = False


def load_all() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
