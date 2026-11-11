"""
JSON file format handler
"""

import json
import os
from typing import Any, Dict, Optional, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ts_handler import convert_numeric_dicts_to_lists


def _layout_source(kwargs) -> Optional[str]:
    """The source file to take the layout from, unless regenerating from scratch."""
    source_file = kwargs.get("source_file")
    if kwargs.get("regenerate_from_scratch") or not source_file or not os.path.exists(source_file):
        return None
    return source_file


def _read_order(source_file: Optional[str]) -> Optional[Dict[str, Any]]:
    if not source_file:
        return None
    try:
        with open(source_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class JSONHandler(FileFormatHandler):
    """Handler for JSON files"""

    def read(self, file_path: str) -> Dict[str, Any]:
        """Read JSON file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Write JSON file. An existing target keeps its layout (only changed values are rewritten);
        a new one is built from the source file as a template (order, indentation, line endings),
        leaving out keys `content` lacks. regenerate_from_scratch rewrites it from `content`.
        """
        from algebras.utils.json_layout import merge_json_file

        source_file = _layout_source(kwargs)
        if not kwargs.get("regenerate_from_scratch"):
            try:
                if os.path.exists(file_path):
                    merge_json_file(file_path, content, order=_read_order(source_file))
                    return
                if source_file is not None:
                    merge_json_file(
                        file_path, content, order=_read_order(source_file), template_path=source_file
                    )
                    return
            except ValueError:
                pass  # not a JSON object: write it from scratch
        # Convert numeric-key dicts to lists to preserve arrays
        content = convert_numeric_dicts_to_lists(content)
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

    def supports_in_place(self) -> bool:
        return True

    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """Change only the values that differ; new keys go to their position in the source."""
        self.write(file_path, content, **{**kwargs, "regenerate_from_scratch": False})
