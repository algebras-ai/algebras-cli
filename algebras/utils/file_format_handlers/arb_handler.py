"""
Flutter ARB file format handler
"""

import os
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

from algebras.utils.arb_handler import (
    extract_translatable_strings,
    read_arb_file,
    update_arb_values,
    write_arb_content,
)
from algebras.utils.file_format_handlers.base import FileFormatHandler

if TYPE_CHECKING:
    from algebras.config import Config


class ARBHandler(FileFormatHandler):
    """Handler for Flutter .arb files: messages are translated, `@` metadata is kept as is."""

    def read(self, file_path: str) -> Dict[str, Any]:
        return read_arb_file(file_path)

    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        """Messages only: `@key` metadata and `@@locale` are not translatable."""
        return extract_translatable_strings(read_arb_file(file_path))

    def write(self, file_path: str, content: Dict[str, Any], **kwargs) -> None:
        write_arb_content(file_path, content)

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
        values = {k: content[k] for k in keys_to_update if isinstance(content.get(k), str) and content[k]}
        update_arb_values(file_path, values, add_missing=True)
