"""
XLSX file format handler (multi-language workbooks: a key column and one column per language).

Writes go cell by cell into the existing workbook (see update_xlsx_cells), so styles, other
sheets and column widths stay, and every value is stored as a string, never as a formula. Each
translated cell is checked against its source cell first; a cell whose placeholders were damaged
is not written (see algebras.services.placeholders.formats.xlsx.gate_values).
"""

import os
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

import click

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.xlsx_handler import (
    _safe_cell_value,
    extract_translatable_strings as extract_xlsx_strings,
    is_glossary_xlsx,
    read_xlsx_cells,
    read_xlsx_file,
    update_xlsx_cells,
)

if TYPE_CHECKING:
    from algebras.config import Config


def read_xlsx_language(file_path: str, language: Optional[str] = None, config=None) -> Dict[str, str]:
    """{key: text} of one language column; the first language column when no language is given."""
    from algebras.services.placeholders.formats.xlsx import column_name

    if is_glossary_xlsx(file_path):
        raise ValueError(f"XLSX file {file_path} appears to be a glossary file, not a translation file")
    content = read_xlsx_file(file_path)
    if language:
        column = column_name(config, language)
        if column not in content.get("languages", []) and language in content.get("languages", []):
            column = language
        return extract_xlsx_strings(content, column)
    languages = content.get("languages", [])
    return extract_xlsx_strings(content, languages[0]) if languages else {}


class XLSXHandler(FileFormatHandler):
    """Handler for XLSX translation workbooks."""

    def __init__(self, config: Optional["Config"] = None):
        self.config = config

    def read(self, file_path: str) -> Dict[str, Any]:
        return read_xlsx_file(file_path)

    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        if language is None:
            return {}
        return read_xlsx_language(file_path, language, config or self.config)

    def _column(self, language: str) -> str:
        from algebras.services.placeholders.formats.xlsx import column_name

        return column_name(self.config, language)

    def _write_column(
        self, file_path: str, column: str, values: Dict[str, str], source_file: Optional[str]
    ) -> None:
        from algebras.services.placeholders.formats.xlsx import gate_values

        # Only cells whose text changes are written; the rest of the workbook stays untouched.
        if os.path.exists(file_path):
            current = read_xlsx_cells(file_path).column(column)
            values = {
                k: v
                for k, v in values.items()
                if isinstance(v, str) and _safe_cell_value(current[k].value if k in current else "") != v.strip()
            }
        else:
            values = {k: v for k, v in values.items() if isinstance(v, str)}
        reference = source_file if source_file and os.path.exists(source_file) else None
        values, _rejected = gate_values(reference, file_path if os.path.exists(file_path) else (reference or file_path), column, values, self.config)
        report = update_xlsx_cells(file_path, column, values, template_file=reference)
        if report["runs_dropped"]:
            click.echo(
                f"  {click.style('⚠', fg='yellow')} {os.path.basename(file_path)}: rich-text formatting "
                f"was replaced by plain text in {', '.join(report['runs_dropped'])}"
            )

    def write(self, file_path: str, content: Dict[str, Any], **kwargs) -> None:
        target_language = kwargs.get("target_language")
        source_file = kwargs.get("source_file")
        if isinstance(content, dict) and "translations" in content and "languages" in content:
            # Whole-workbook content (Translator.translate_file): write the target column, or
            # every language column when no target language is given.
            translations = content["translations"]
            if target_language:
                columns = [(self._column(target_language), target_language)]
            else:
                columns = [(lang, lang) for lang in content["languages"]]
            for column, code in columns:
                values = {}
                for key, by_lang in translations.items():
                    if isinstance(by_lang, dict):
                        value = by_lang.get(column, by_lang.get(code))
                        if isinstance(value, str):
                            values[key] = value
                self._write_column(file_path, column, values, source_file)
            return
        if target_language is None:
            raise ValueError("XLSX write requires target_language in kwargs")
        self._write_column(file_path, self._column(target_language), dict(content), source_file)

    def supports_in_place(self) -> bool:
        return True

    def _write_in_place_impl(
        self, file_path: str, content: Dict[str, Any], keys_to_update: Set[str], **kwargs
    ) -> None:
        target_language = kwargs.get("target_language")
        if target_language is None:
            raise ValueError("XLSX write_in_place requires target_language in kwargs")
        values = {k: content[k] for k in keys_to_update if k in content}
        self._write_column(file_path, self._column(target_language), values, kwargs.get("source_file"))

    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        if isinstance(content, dict) and "translations" in content and "languages" in content:
            return set(content["translations"].keys())
        return set(content.keys())
