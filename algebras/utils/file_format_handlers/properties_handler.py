"""
Java .properties file format handler
"""

import os
from typing import Any, Dict, Set

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.properties_handler import (
    read_properties_file,
    update_properties_values,
    write_properties_file,
)


class PropertiesHandler(FileFormatHandler):
    """Handler for Java .properties resource bundles (flat key/value)."""

    def read(self, file_path: str) -> Dict[str, Any]:
        return read_properties_file(file_path)

    def write(self, file_path: str, content: Dict[str, Any], **kwargs) -> None:
        # New files use \uXXXX escapes, which every Java version reads (Java 8 reads ISO-8859-1).
        values = {k: v for k, v in content.items() if isinstance(v, str)}
        write_properties_file(file_path, values)

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
        # Empty values are translations that failed the placeholder gate: leave those keys missing.
        values = {k: content[k] for k in content if k in keys_to_update and isinstance(content[k], str) and content[k]}
        update_properties_values(file_path, values, add_missing=True)
