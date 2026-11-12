"""
XLIFF file format handler
"""

import os
from typing import Dict, Any, Optional, Set, TYPE_CHECKING

from algebras.utils.file_format_handlers.base import FileFormatHandler

if TYPE_CHECKING:
    from algebras.config import Config
from algebras.utils.xliff_handler import (
    read_xliff_file,
    write_xliff_file,
    extract_translatable_strings as extract_xliff_strings,
    update_xliff_targets,
)


class XLIFFHandler(FileFormatHandler):
    """
    Handler for XLIFF files.

    In place (an existing target): only the <target> of changed units is rewritten, and units the
    source gained are copied in; notes, context, attributes and layout stay as they are.
    write() (a new target, or --regenerate-from-scratch): the target is built from the source
    file as a template, keeping its notes, context and unit attributes.
    """

    def read(self, file_path: str) -> Dict[str, Any]:
        """Read XLIFF file (returns raw structure)"""
        return read_xliff_file(file_path)

    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        """
        Read XLIFF file and extract translatable strings.

        For a target-language file this returns the existing translations (non-empty <target>
        values), not the unit sources: the result is what is already translated, and writing it back
        must not replace other units' targets with their source text. Units with translate="no"
        are left out.
        """
        raw_content = read_xliff_file(file_path)
        source_language = None
        if config is not None:
            try:
                source_language = config.get_source_language()
            except Exception:
                source_language = None
        if language and source_language and language != source_language:
            return {
                unit["id"]: unit["target"]
                for file_data in raw_content.get("files", [])
                for unit in file_data.get("trans-units", [])
                if unit.get("id")
                and unit.get("translate") is not False
                and (unit.get("target") or "").strip()
            }
        return extract_xliff_strings(raw_content)

    def supports_in_place(self) -> bool:
        return True

    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        self._write(file_path, content, in_place=True, **kwargs)

    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write XLIFF file built from the source file (see the class docstring)."""
        self._write(file_path, content, in_place=False, **kwargs)

    def _write(self, file_path: str, content: Dict[str, Any], in_place: bool, **kwargs) -> None:
        source_language = kwargs.get("source_language")
        target_language = kwargs.get("target_language")
        xlf_target_state = kwargs.get("xlf_target_state", "translated")

        if source_language is None or target_language is None:
            raise ValueError(
                "XLIFF write requires source_language and target_language in kwargs"
            )

        # content is the flat dict of translations (key -> target)
        source_raw_content = kwargs.get("source_raw_content")
        if source_raw_content is None and kwargs.get("source_file"):
            source_raw_content = read_xliff_file(kwargs["source_file"])

        if in_place and os.path.exists(file_path):
            raw_content = kwargs.get("raw_content")
            if raw_content is None or getattr(raw_content, "text", None) is None:
                raw_content = read_xliff_file(file_path)
        else:
            # A new target: built from the source file (the template), or from scratch.
            xlf_version = kwargs.get("xlf_version", "1.2")
            if source_raw_content and "version" in source_raw_content:
                xlf_version = source_raw_content["version"]
            raw_content = {
                "version": xlf_version,
                "files": [],
            }

        # Update the raw structure with translations
        updated_content = update_xliff_targets(
            raw_content,
            content,
            source_raw_content,
            xlf_target_state,
        )

        write_xliff_file(
            file_path,
            updated_content,
            source_language,
            target_language,
            xlf_target_state,
        )

    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        """Extract keys from XLIFF content (flat dictionary)"""
        return set(content.keys())
