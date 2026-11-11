"""
Flutter ARB file format handler
"""

import os
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

from algebras.utils.arb_handler import (
    extract_translatable_strings,
    read_arb_file,
    update_arb_preserving,
    write_arb_content,
    write_arb_from_template,
)
from algebras.utils.file_format_handlers.base import FileFormatHandler

if TYPE_CHECKING:
    from algebras.config import Config


def _layout_source(kwargs) -> Optional[str]:
    """The source file to take the layout from, unless regenerating from scratch."""
    source_file = kwargs.get("source_file")
    if kwargs.get("regenerate_from_scratch") or not source_file or not os.path.exists(source_file):
        return None
    return source_file


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
        """
        An existing target keeps its layout (only translated messages change); a new one is built
        from the source file as a template. regenerate_from_scratch rewrites it from `content`.
        """
        source_file = _layout_source(kwargs)
        if kwargs.get("regenerate_from_scratch"):
            write_arb_content(file_path, content)
        elif os.path.exists(file_path):
            update_arb_preserving(file_path, content, None, source_file)
        elif source_file is not None:
            write_arb_from_template(file_path, content, source_file, kwargs.get("target_language"))
        else:
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
        update_arb_preserving(file_path, content, set(keys_to_update), _layout_source(kwargs))
