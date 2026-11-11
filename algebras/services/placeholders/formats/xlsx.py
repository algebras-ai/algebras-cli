"""
XLSX translation workbooks: one row per key, one column per language (row 1 holds the headers).

A spreadsheet has no placeholder syntax of its own; the cells hold strings for whatever app reads
them, and one sheet may mix syntaxes ({0}, %1$s, {{name}}, ${x} …). The profile is detected from
the source-language column of every translation sheet (detect_profile over every candidate
syntax), unless pinned in the config (`placeholders: [...]`). A workbook's translation sheets are
the sheets with a key + language header row (see algebras.utils.xlsx_handler._data_sheets); other
sheets (notes, lookups) are never translated. With several translation sheets, keys are
"<sheet>!<key>".

Formatted (rich-text) source cells are read with their runs as paired <runN>…</runN> tags (see
algebras.utils.xlsx_handler.runs_to_tagged), so the profile detected from them includes the
xml_tag syntax: the tags are masked like any markup placeholder and checked by the write gate.

Writing (see algebras.utils.xlsx_handler.update_xlsx_cells):

- the cells are written straight into the workbook package: every other part (images, charts,
  shapes, styles, other sheets) stays byte-identical, and a written cell keeps its style;
- cells are written as strings (inline strings), so a translation that starts with "=", "+", "-"
  or "@" is never taken for a formula;
- a translation of a formatted source cell gets the source runs' fonts; a repaired rich-text
  target cell keeps its runs when the change fits inside them.

Before a translated cell is written it is checked against the source cell (gate_values). A cell
whose placeholders were lost or damaged is not written: it stays empty or keeps its old value, and
is reported with its Excel reference (Sheet1!D14).

`algebras placeholders` compares each target cell with the source cell of the same row, reports
`key [Sheet1!D14]`, repairs with the engine's Tier-1 repair and writes the fixes cell by cell.
"""

from typing import Dict, List, Optional, Tuple

import click

from algebras.services.placeholders.engine import repair, verify
from algebras.services.placeholders.file_checks import Finding, register_file_check
from algebras.services.placeholders.fix_writers import register_fix_writer
from algebras.services.placeholders.profiles import (
    GENERIC_PROFILE,
    PlaceholderProfile,
    detect_profile,
    profile_for_path,
    register_profile_resolver,
)

_EXTENSIONS = [".xlsx", ".xls"]

# Every syntax of the generic profile, more specific ones first (i18next before icu_simple).
XLSX_CANDIDATES = GENERIC_PROFILE.syntax_names


def column_name(config, language: Optional[str]) -> Optional[str]:
    """Header of a language's column: the config's locale mapping, else the code itself."""
    if config is not None and language:
        try:
            mapped = config.get_destination_locale_code(language)
        except Exception:
            mapped = None
        if isinstance(mapped, str) and mapped:
            return mapped
    return language


def source_column(config, languages: List[str], source_language: Optional[str] = None) -> Optional[str]:
    """The source-language column of a sheet (the first language column if it cannot be found)."""
    if source_language is None and config is not None:
        try:
            source_language = config.get_source_language()
        except Exception:
            source_language = None
        if not isinstance(source_language, str):
            source_language = None
    for name in (column_name(config, source_language), source_language):
        if name and name in languages:
            return name
    return languages[0] if languages else None


def resolve_profile(file_path: str, config=None) -> PlaceholderProfile:
    """The syntaxes that occur in the source-language column (formatted cells with their run tags)."""
    from algebras.utils.xlsx_handler import read_xlsx_book

    try:
        book = read_xlsx_book(file_path, config)
    except Exception:
        return GENERIC_PROFILE
    column = source_column(config, book.languages)
    if column is None:
        return GENERIC_PROFILE
    values = [cell.tagged for cell in book.column(column).values()]
    return detect_profile(values, XLSX_CANDIDATES, "xlsx")


def _is_glossary(file_path: str) -> bool:
    from algebras.utils.xlsx_handler import is_glossary_xlsx

    return is_glossary_xlsx(file_path)


# ---------------------------------------------------------------------------
# Translation write gate
# ---------------------------------------------------------------------------


def gate_values(
    source_file: Optional[str],
    target_file: str,
    target_column: str,
    values: Dict[str, str],
    config=None,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Split translated `values` ({key: text}) into the ones safe to write and the rejected keys.
    A value is rejected when its placeholders do not match the source cell of the same row (a
    value with <runN> tags is compared with the tagged source, so the tags must pair up too). The
    rejected cells are reported with their Excel reference and left as they are.
    """
    from algebras.utils.xlsx_handler import has_run_tags, read_xlsx_book

    reference = source_file or target_file
    try:
        source_book = read_xlsx_book(reference, config)
    except Exception:
        return dict(values), []
    column = source_column(config, source_book.languages)
    if column is None or column == target_column:
        return dict(values), []
    sources = source_book.column(column)
    profile = profile_for_path(reference, config)

    try:
        target_book = read_xlsx_book(target_file, config)
    except Exception:
        target_book = source_book

    accepted: Dict[str, str] = {}
    rejected: List[str] = []
    for key, text in values.items():
        source = sources.get(key)
        problems = []
        if source is not None and isinstance(text, str) and text:
            source_text = source.tagged if has_run_tags(text) else source.value
            problems = verify(source_text, text, profile)
        if not problems:
            accepted[key] = text
            continue
        rejected.append(key)
        where = target_book.ref(key, target_column) or f"{source.ref} row"
        codes = ", ".join(sorted({p.code for p in problems}))
        click.echo(
            f"  {click.style('✗', fg='red')} {where} ({key}): placeholders {codes} in the translation; "
            "the cell was not written"
        )
    return accepted, rejected


# ---------------------------------------------------------------------------
# Check and fix
# ---------------------------------------------------------------------------


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """Compare each target cell with the source cell of the same row; key is `key [Sheet1!D14]`."""
    from algebras.utils.xlsx_handler import read_xlsx_book

    if _is_glossary(source_file):
        return []
    source_book = read_xlsx_book(source_file, config)
    target_book = source_book if target_file == source_file else read_xlsx_book(target_file, config)
    src_col = source_column(config, source_book.languages, source_language)
    tgt_col = column_name(config, target_language)
    if src_col is None or tgt_col not in target_book.languages or tgt_col == src_col:
        return []
    profile = profile_for_path(source_file, config)
    targets = target_book.column(tgt_col)

    findings: List[Finding] = []
    for key, source_cell in source_book.column(src_col).items():
        target_cell = targets.get(key)
        if target_cell is None:
            continue  # untranslated: 'status' reports it
        problems = verify(source_cell.value, target_cell.value, profile)
        if not problems:
            continue
        label = key.split("!", 1)[1] if target_book.multi and "!" in key else key
        findings.append(
            Finding(
                key=f"{label} [{target_cell.ref}]",
                source=source_cell.value,
                target=target_cell.value,
                problems=problems,
                path=(key,),
                fixed=repair(source_cell.value, target_cell.value, profile),
            )
        )
    return findings


def write_fixes(target_file: str, fixes: Dict[Tuple[str, ...], str], language: Optional[str] = None, config=None) -> None:
    """Write only the fixed cells of the language's column into the workbook package."""
    from algebras.utils.xlsx_handler import update_xlsx_cells

    column = column_name(config, language)
    if not column:
        raise ValueError(f"A language is needed to fix {target_file}")
    report = update_xlsx_cells(
        target_file,
        column,
        {path[0]: value for path, value in fixes.items()},
        add_missing=False,
        keep_runs=True,
        config=config,
    )
    if report["missing"]:
        raise ValueError(f"Could not find {', '.join(report['missing'])} in {target_file}")
    if report["runs_dropped"]:
        click.echo(
            f"  {click.style('⚠', fg='yellow')} {target_file}: rich-text formatting could not be kept in "
            + ", ".join(report["runs_dropped"])
        )


register_profile_resolver(_EXTENSIONS, resolve_profile)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
