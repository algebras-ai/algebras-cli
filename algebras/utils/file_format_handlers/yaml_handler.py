"""
YAML file format handler
"""

import os
import sys
from typing import Any, Dict, Optional, Set

import yaml

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ts_handler import convert_numeric_dicts_to_lists


class YAMLHandler(FileFormatHandler):
    """
    Handler for YAML files.

    write_in_place keeps the file's layout (algebras.utils.yaml_layout): an existing target gets
    only its changed values replaced and new keys inserted at their source position; a new target
    is made from the source file as a template. write() dumps the content from scratch
    (--regenerate-from-scratch, and the fallback when the layout cannot be kept).
    """

    def read(self, file_path: str) -> Dict[str, Any]:
        """Read YAML file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write YAML file from scratch (yaml.dump: keys sorted, comments dropped)"""
        # Convert numeric-key dicts to lists to preserve arrays
        content = convert_numeric_dicts_to_lists(content)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                content,
                f,
                default_flow_style=False,
                allow_unicode=True,
            )

    def supports_in_place(self) -> bool:
        return True

    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """Write `content` (the target's full content) keeping the file's or the source's layout"""
        write_yaml_keeping_layout(file_path, content, kwargs.get("source_file"))


def _read(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_yaml_keeping_layout(file_path: str, content: Dict[str, Any], source_file: Optional[str] = None) -> None:
    """
    Write `content` into `file_path` as text edits (algebras.utils.yaml_layout): over the existing
    file, or over the source file as a template when the target does not exist yet. Falls back to
    yaml.dump, with a notice, if the layout cannot be kept (aliases, merge keys, a value where
    the target has a mapping, ...); a file that does not load back as `content` is never written.
    """
    from algebras.utils.yaml_layout import YAMLLayoutError, render_yaml_update

    if not content and not os.path.exists(file_path):
        YAMLHandler().write(file_path, content)  # nothing was translated: an empty mapping
        return
    try:
        new_text = render_yaml_update(_read(file_path), _read(source_file), content)
    except YAMLLayoutError as e:
        print(
            f"  Note: {os.path.basename(file_path)}: could not keep the file layout ({e}); writing it from scratch",
            file=sys.stderr,
        )
        YAMLHandler().write(file_path, content)
        return
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
