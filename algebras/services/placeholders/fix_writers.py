"""
Registry of writers that apply placeholder fixes to a target file in place.

A writer receives the target file and {key path: fixed value}, where the key path is the tuple of
keys leading to the string in the dict returned by `read_language_file` (plural dicts included,
e.g. ("Quiz.points.__plurals__", "one")). It must change only those values and keep the rest of the
file as it is.
"""

from typing import Callable, Dict, Iterable, Optional, Tuple

KeyPath = Tuple[str, ...]
FixWriter = Callable[..., None]  # (target_file, fixes: Dict[KeyPath, str], language: str, config) -> None

_WRITERS: Dict[str, FixWriter] = {}


def register_fix_writer(extensions: Iterable[str], writer: FixWriter) -> None:
    for ext in extensions:
        _WRITERS[ext.lower()] = writer


def get_fix_writer(file_path: str) -> Optional[FixWriter]:
    lower = file_path.lower()
    for ext in sorted(_WRITERS, key=len, reverse=True):
        if lower.endswith(ext):
            return _WRITERS[ext]
    return None


def unregister_fix_writer(extensions: Iterable[str]) -> None:
    for ext in extensions:
        _WRITERS.pop(ext.lower(), None)
