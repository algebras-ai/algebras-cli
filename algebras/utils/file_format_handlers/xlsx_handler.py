"""
XLSX file format handler (multi-language workbooks: a key column and one column per language).

Writes go cell by cell into the existing workbook package (see update_xlsx_cells), so images,
charts, styles, other sheets and column widths stay, and every value is stored as a string, never
as a formula. Each translated cell is checked against its source cell first; a cell whose
placeholders were damaged is not written (see algebras.services.placeholders.formats.xlsx.gate_values).

Every translation sheet of the workbook is read (keys "<sheet>!<key>" when there are several, see
XlsxBook). A formatted (rich-text) source cell is read for translation with its runs as paired
<runN> tags, and the translation is written back with the source runs' fonts. An .xls workbook is
read with xlrd and written to the .xlsx next to it.
"""

import os
from typing import Any, Dict, Optional, Set, TYPE_CHECKING

import click

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.xlsx_handler import (
    extract_translatable_strings as extract_xlsx_strings,
    is_glossary_xlsx,
    read_xlsx_book,
    read_xlsx_file,
    update_xlsx_cells,
    xlsx_output_path,
)

if TYPE_CHECKING:
    from algebras.config import Config


def read_xlsx_language(
    file_path: str, language: Optional[str] = None, config=None, tagged: bool = False
) -> Dict[str, str]:
    """
    {key: text} of one language column; the first language column when no language is given.
    With `tagged`, formatted cells come with their runs as <runN> tags (see runs_to_tagged).
    """
    from algebras.services.placeholders.formats.xlsx import column_name

    if is_glossary_xlsx(file_path):
        raise ValueError(f"XLSX file {file_path} appears to be a glossary file, not a translation file")
    content = read_xlsx_file(file_path, config)
    languages = content.get("languages", [])
    if language:
        column = column_name(config, language)
        if column not in languages and language in languages:
            column = language
    else:
        column = languages[0] if languages else None
    if column is None:
        return {}
    values = extract_xlsx_strings(content, column)
    if tagged:
        for key, by_lang in content.get("rich_text", {}).items():
            if key in values and column in by_lang:
                values[key] = by_lang[column]
    return values


class XLSXHandler(FileFormatHandler):
    """Handler for XLSX translation workbooks."""

    def __init__(self, config: Optional["Config"] = None):
        self.config = config

    def read(self, file_path: str) -> Dict[str, Any]:
        return read_xlsx_file(file_path, self.config)

    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        if language is None:
            return {}
        return read_xlsx_language(file_path, language, config or self.config, tagged=True)

    def _column(self, language: str) -> str:
        from algebras.services.placeholders.formats.xlsx import column_name

        return column_name(self.config, language)

    def _write_column(
        self,
        file_path: str,
        column: str,
        values: Dict[str, str],
        source_file: Optional[str],
        force: bool = False,
    ) -> None:
        from algebras.services.placeholders.formats.xlsx import gate_values, source_column

        written_path = xlsx_output_path(file_path)  # an .xls target is written to the .xlsx next to it
        # Only cells whose text changes are written; the rest of the workbook stays untouched.
        if os.path.exists(written_path):
            current = read_xlsx_book(written_path, self.config).column(column)
            values = {
                k: v
                for k, v in values.items()
                if isinstance(v, str) and (current[k].tagged.strip() if k in current else "") != v.strip()
            }
        else:
            values = {k: v for k, v in values.items() if isinstance(v, str)}
        reference = source_file if source_file and os.path.exists(source_file) else None
        if reference is None and not os.path.exists(written_path) and os.path.exists(file_path):
            reference = file_path  # a new .xlsx next to an .xls: the .xls is the template
        gate_target = written_path if os.path.exists(written_path) else (reference or written_path)
        values, _rejected = gate_values(reference, gate_target, column, values, self.config)

        # A formatted source cell gives its runs to the translation (see update_xlsx_cells).
        rich_sources: Dict[str, Any] = {}
        rich_reference = reference or (written_path if os.path.exists(written_path) else None)
        if values and rich_reference:
            try:
                book = read_xlsx_book(rich_reference, self.config)
            except Exception:
                book = None
            src_col = source_column(self.config, book.languages) if book else None
            if book is not None and src_col and src_col != column:
                rich_sources = {
                    k: cell.rich
                    for k, cell in book.column(src_col).items()
                    if cell.rich is not None and k in values
                }
        report = update_xlsx_cells(
            file_path,
            column,
            values,
            template_file=reference,
            rich_sources=rich_sources,
            force=force,
            config=self.config,
        )
        if report["runs_dropped"]:
            click.echo(
                f"  {click.style('⚠', fg='yellow')} {os.path.basename(report['path'])}: rich-text "
                f"formatting was replaced by plain text in {', '.join(report['runs_dropped'])}"
            )

    def write(self, file_path: str, content: Dict[str, Any], **kwargs) -> None:
        target_language = kwargs.get("target_language")
        source_file = kwargs.get("source_file")
        force = bool(kwargs.get("regenerate_from_scratch"))
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
                self._write_column(file_path, column, values, source_file, force)
            return
        if target_language is None:
            raise ValueError("XLSX write requires target_language in kwargs")
        self._write_column(file_path, self._column(target_language), dict(content), source_file, force)

    def supports_in_place(self) -> bool:
        return True

    def _write_in_place_impl(
        self, file_path: str, content: Dict[str, Any], keys_to_update: Set[str], **kwargs
    ) -> None:
        target_language = kwargs.get("target_language")
        if target_language is None:
            raise ValueError("XLSX write_in_place requires target_language in kwargs")
        values = {k: content[k] for k in keys_to_update if k in content}
        self._write_column(
            file_path,
            self._column(target_language),
            values,
            kwargs.get("source_file"),
            bool(kwargs.get("regenerate_from_scratch")),
        )

    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        if isinstance(content, dict) and "translations" in content and "languages" in content:
            return set(content["translations"].keys())
        return set(content.keys())
