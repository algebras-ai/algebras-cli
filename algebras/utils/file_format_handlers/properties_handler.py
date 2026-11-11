"""
Java .properties file format handler
"""

import os
from typing import Any, Dict, List, Optional, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.properties_handler import (
    read_properties_file,
    update_properties_values,
    write_properties_file,
    write_properties_from_template,
)


def _layout_source(kwargs) -> Optional[str]:
    """The source file to take the layout and key order from, unless regenerating from scratch."""
    source_file = kwargs.get("source_file")
    if kwargs.get("regenerate_from_scratch") or not source_file or not os.path.exists(source_file):
        return None
    return source_file


def _translated(content: Dict[str, Any], source: Dict[str, str], keys=None) -> Dict[str, str]:
    """
    Values to write. An empty value for a non-empty source text is a translation that failed the
    placeholder gate: the key is left missing, not written empty or in the source language.
    """
    return {
        k: v
        for k, v in content.items()
        if isinstance(v, str) and (keys is None or k in keys) and (v or source.get(k) == "")
    }


class PropertiesHandler(FileFormatHandler):
    """Handler for Java .properties resource bundles (flat key/value)."""

    def read(self, file_path: str) -> Dict[str, Any]:
        return read_properties_file(file_path)

    def write(self, file_path: str, content: Dict[str, Any], **kwargs) -> None:
        """
        An existing target keeps its layout (only changed values are rewritten); a new one is built
        from the source file as a template, comments included. regenerate_from_scratch writes it
        from `content` alone (\\uXXXX escapes, which every Java version reads).
        """
        source_file = _layout_source(kwargs)
        if kwargs.get("regenerate_from_scratch") or (source_file is None and not os.path.exists(file_path)):
            values = {k: v for k, v in content.items() if isinstance(v, str)}
            write_properties_file(file_path, values)
            return
        source = read_properties_file(source_file) if source_file else {}
        values = _translated(content, source)
        if os.path.exists(file_path):
            update_properties_values(file_path, values, add_missing=True, order=list(source) or None)
        else:
            write_properties_from_template(file_path, source_file, values)

    def supports_in_place(self) -> bool:
        return True

    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs,
    ) -> None:
        if not os.path.exists(file_path):
            self.write(file_path, content, **kwargs)
            return
        source_file = _layout_source(kwargs)
        source = read_properties_file(source_file) if source_file else {}
        values = _translated(content, source, set(keys_to_update))
        order: Optional[List[str]] = list(source) or None
        update_properties_values(file_path, values, add_missing=True, order=order)
