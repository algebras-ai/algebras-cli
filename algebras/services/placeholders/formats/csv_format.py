"""
CSV / TSV translation tables: one key column, then one column per language.

The format has no placeholder syntax of its own. Its cells hold whatever the consuming app uses,
and one table is often exported from Android, iOS and web at once, so a file can mix {0}, %1$s,
{{name}}, %{name} and ${0}. The profile is detected from the source-language column of the file
(detect_profile; extraction takes the longest match first, so mixed syntaxes do not overlap),
unless pinned in the config (`placeholders: [printf, icu_simple]`). Glossary tables are not
translated through this path and get the generic profile.

The source and the target are usually the same file: the check compares, row by row, the target
language's column with the source language's column and reports the row key and the column. The
fix writer replaces only the fixed cells and keeps column order, delimiter, quoting style and line
endings byte-for-byte.
"""

import csv
import io
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Tuple

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

KeyPath = Tuple[str, ...]

_EXTENSIONS = (".csv", ".tsv")

# Every syntax a table exported from Android, iOS or a web app may use. Order matters only for
# equal spans; longer matches win anyway ("{{name}}" over "{name}", "%1$s" over "%1").
CSV_CANDIDATES = (
    "i18next",
    "js_template",
    "objc_variable",
    "python_percent",
    "ruby",
    "printf",
    "icu_simple",
    "xml_tag",
)


# ---------------------------------------------------------------------------
# Reading the raw table
# ---------------------------------------------------------------------------


def _delimiter(file_path: str) -> str:
    return "\t" if file_path.lower().endswith(".tsv") else ","


def _read_text(file_path: str) -> Tuple[str, str]:
    """(text, encoding), with line endings untouched. Same fallback as csv_handler."""
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {file_path}")


@dataclass
class Table:
    headers: List[str]
    rows: List[List[str]]  # data rows, as csv.reader returns them (values not stripped)

    def column(self, language: Optional[str], config=None) -> Optional[int]:
        """Index of the column for `language` (locale mapping, exact or "(code)" header match)."""
        from algebras.utils.csv_handler import _find_matching_column

        languages = self.headers[1:]
        if not languages:
            return None
        if language is None:
            return 1
        mapped = config.get_destination_locale_code(language) if config is not None else language
        name = _find_matching_column(languages, mapped)
        if name is None and mapped != language:
            name = _find_matching_column(languages, language)
        return None if name is None else languages.index(name) + 1

    def keyed_rows(self) -> Dict[str, List[str]]:
        """{row key: row}; like csv_handler, rows of the wrong width are skipped and the last
        duplicate wins."""
        result: Dict[str, List[str]] = {}
        for row in self.rows:
            if len(row) != len(self.headers):
                continue
            key = row[0].strip()
            if key:
                result[key] = row
        return result


def read_table(file_path: str) -> Table:
    text, _ = _read_text(file_path)
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(file_path)))
    if not rows:
        raise ValueError(f"CSV file {file_path} is empty")
    return Table(headers=rows[0], rows=rows[1:])


def _source_language(config) -> Optional[str]:
    if config is None:
        return None
    try:
        return config.get_source_language()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Profile detection
# ---------------------------------------------------------------------------


def resolve_profile(file_path: str, config=None) -> PlaceholderProfile:
    """The syntaxes used in the source-language column (the first language column without config)."""
    from algebras.utils.csv_handler import is_glossary_csv

    try:
        if is_glossary_csv(file_path):
            return GENERIC_PROFILE
        table = read_table(file_path)
    except (OSError, ValueError, csv.Error):
        return GENERIC_PROFILE
    column = table.column(_source_language(config), config)
    if column is None:
        column = table.column(None)
    if column is None:
        return GENERIC_PROFILE
    texts = (row[column] for row in table.keyed_rows().values())
    return detect_profile(texts, CSV_CANDIDATES, "csv")


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def cell_label(key: str, column: str) -> str:
    """How a cell is reported: the row key and the column header."""
    return f"{key} [{column}]"


def _pairs(
    source_file: str, target_file: str, source_language: str, target_language: str, config
) -> Iterator[Tuple[str, str, str, str]]:
    """(row key, target column header, source cell, target cell) for every row of the source."""
    source = read_table(source_file)
    target = source if target_file == source_file else read_table(target_file)
    source_column = source.column(source_language, config)
    target_column = target.column(target_language, config)
    if source_column is None or target_column is None:
        return
    header = target.headers[target_column]
    target_rows = target.keyed_rows()
    for key, row in source.keyed_rows().items():
        target_row = target_rows.get(key)
        if target_row is not None:
            yield key, header, row[source_column], target_row[target_column]


def check_file(
    source_file: str,
    target_file: str,
    source_language: str,
    target_language: str,
    config=None,
) -> List[Finding]:
    """
    Placeholder findings for one target-language column: each row's target cell compared with
    the same row's source cell. Reported as "<row key> [<column>]"; the fix path is (row key,).
    """
    profile = profile_for_path(source_file, config)
    findings: List[Finding] = []
    for key, header, source_text, target_text in _pairs(
        source_file, target_file, source_language, target_language, config
    ):
        if not source_text.strip() or not target_text.strip():
            continue  # untranslated: 'status' reports it
        problems = verify(source_text, target_text, profile)
        if problems:
            findings.append(
                Finding(
                    key=cell_label(key, header),
                    source=source_text,
                    target=target_text,
                    problems=problems,
                    path=(key,),
                    fixed=repair(source_text, target_text, profile),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Fix writer: replace only the fixed cells
# ---------------------------------------------------------------------------


@dataclass
class _Cell:
    start: int
    end: int
    quoted: bool


def cell_spans(text: str, delimiter: str, quotechar: str = '"') -> List[List[_Cell]]:
    """
    Source spans of every cell, row by row, read the way csv.reader (default dialect) reads them:
    a quote opens a quoted field only at the start of a cell, "" is an escaped quote inside it,
    and \\r\\n, \\n or \\r end a row outside quotes.
    """
    rows: List[List[_Cell]] = []
    row: List[_Cell] = []
    i, n = 0, len(text)
    while i < n:
        start = i
        quoted = text[i] == quotechar
        if quoted:
            i += 1
            while i < n:
                if text[i] == quotechar:
                    if i + 1 < n and text[i + 1] == quotechar:
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
        while i < n and text[i] not in (delimiter, "\r", "\n"):
            i += 1
        row.append(_Cell(start, i, quoted))
        if i < n and text[i] == delimiter:
            i += 1
            if i == n:
                row.append(_Cell(i, i, False))
            continue
        if len(row) == 1 and not quoted and start == i:
            row = []  # a blank line: csv.reader returns []
        rows.append(row)
        row = []
        if text.startswith("\r\n", i):
            i += 2
        elif i < n:
            i += 1
    if row:
        rows.append(row)
    return rows


def _render(value: str, delimiter: str, quoted: bool, quotechar: str = '"') -> str:
    """A cell as csv.writer (QUOTE_MINIMAL) writes it, kept quoted if the original was."""
    if quoted or any(c in value for c in (delimiter, quotechar, "\r", "\n")):
        return quotechar + value.replace(quotechar, quotechar * 2) + quotechar
    return value


def write_fixes(target_file: str, fixes: Dict[KeyPath, str], language: str = None, config=None) -> None:
    """
    Replace the fixed cells of `language`'s column in place. Column order, the delimiter, quoting
    style, line endings, the encoding and every other cell stay byte-for-byte.
    """
    text, encoding = _read_text(target_file)
    delimiter = _delimiter(target_file)
    table = read_table(target_file)
    column = table.column(language, config)
    if column is None:
        raise ValueError(f"No column for {language} in {target_file}")
    spans = [row for row in cell_spans(text, delimiter) if row]
    parsed = [row for row in [table.headers] + table.rows if row]
    if len(spans) != len(parsed) or any(len(s) != len(p) for s, p in zip(spans, parsed)):
        raise ValueError(f"Could not map the cells of {target_file}")

    # Last row wins for duplicate keys, as in csv_handler.write_csv_file_in_place.
    rows_by_key: Dict[str, int] = {}
    for index, row in enumerate(parsed[1:], start=1):
        if len(row) == len(table.headers) and row[0].strip():
            rows_by_key[row[0].strip()] = index

    edits: List[Tuple[_Cell, str]] = []
    for path, value in fixes.items():
        key = path[0].strip()
        index = rows_by_key.get(key)
        if index is None or len(spans[index]) <= column:
            raise ValueError(f"Could not find row {key} in {target_file}")
        cell = spans[index][column]
        # The span must hold exactly the value csv.reader read, or the file is not what we think.
        raw = text[cell.start : cell.end]
        current = next(csv.reader(io.StringIO(raw, newline=""), delimiter=delimiter), [""])
        if (current[0] if current else "") != parsed[index][column]:
            raise ValueError(f"Could not map row {key} in {target_file}")
        edits.append((cell, _render(value, delimiter, cell.quoted)))

    for cell, rendered in sorted(edits, key=lambda e: e[0].start, reverse=True):
        text = text[: cell.start] + rendered + text[cell.end :]
    with open(target_file, "w", encoding=encoding, newline="") as f:
        f.write(text)


register_profile_resolver(_EXTENSIONS, resolve_profile)
register_file_check(_EXTENSIONS, check_file)
register_fix_writer(_EXTENSIONS, write_fixes)
