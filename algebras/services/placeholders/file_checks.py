"""
Registry of format-specific file checks for `algebras placeholders`.

By default the command compares every string of the target with the same key in the source. A
format whose target strings do not map one-to-one to source strings (e.g. .stringsdict plural forms
the source lacks, or metadata keys that are not translatable text) registers its own check, which
then replaces the default comparison for that file.

A check receives (source_file, target_file, source_language, target_language, config) and returns
a list of Finding.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from algebras.services.placeholders.engine import Problem

KeyPath = Tuple[str, ...]


@dataclass
class Finding:
    key: str
    source: str
    target: str
    problems: List[Problem]
    # Key path passed to the format's fix writer (and used for --retranslate). Defaults to (key,).
    path: KeyPath = field(default=())
    fixed: Optional[str] = None


FileCheck = Callable[..., List[Finding]]

_CHECKS: Dict[str, FileCheck] = {}


def register_file_check(extensions: Iterable[str], check: FileCheck) -> None:
    for ext in extensions:
        _CHECKS[ext.lower()] = check


def get_file_check(file_path: str) -> Optional[FileCheck]:
    lower = file_path.lower()
    for ext in sorted(_CHECKS, key=len, reverse=True):
        if lower.endswith(ext):
            return _CHECKS[ext]
    return None
