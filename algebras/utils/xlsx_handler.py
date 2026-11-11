"""
XLSX translation file handler for multi-language translations
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from openpyxl import load_workbook, Workbook


def read_xlsx_file(file_path: str) -> Dict[str, Any]:
    """
    Read an XLSX translation file and return its content as a dictionary.
    
    Args:
        file_path: Path to the XLSX file
        
    Returns:
        Dictionary containing the XLSX file content with language columns
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file is not valid XLSX format
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"XLSX file not found: {file_path}")
    
    try:
        wb = load_workbook(filename=file_path, read_only=True, data_only=True)
        ws = wb.active
        
        if ws is None:
            raise ValueError(f"No active worksheet found in XLSX file {file_path}")
        
        # Get all rows as a list
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        
        if not rows:
            raise ValueError(f"XLSX file {file_path} is empty")
        
        # First row should be headers
        headers = [_safe_cell_value(cell) for cell in rows[0]]
        if len(headers) < 2:
            raise ValueError(f"XLSX file {file_path} must have at least 2 columns (key and at least one language)")
        
        # First column is the key, rest are language codes
        key_column = headers[0]
        language_columns = headers[1:]
        
        # Validate language codes
        for lang in language_columns:
            if not lang or not str(lang).strip():
                raise ValueError(f"Empty language code found in header: {headers}")
        
        # Parse data rows
        translations = {}
        for row in rows[1:]:
            if not row:  # Skip empty rows
                continue
            
            # Convert all cells to safe values
            safe_row = [_safe_cell_value(cell) for cell in row]
            
            # Skip completely empty rows
            if all(not cell for cell in safe_row):
                continue
            
            if len(safe_row) != len(headers):
                continue  # Skip malformed rows
            
            key = safe_row[0].strip() if safe_row[0] else ""
            if not key:
                continue  # Skip rows without keys
            
            # Create language translations
            lang_translations = {}
            for i, lang in enumerate(language_columns):
                value = safe_row[i + 1].strip() if i + 1 < len(safe_row) and safe_row[i + 1] else ""
                if value:  # Only include non-empty translations
                    lang_translations[lang] = value
            
            if lang_translations:  # Only include keys with at least one translation
                translations[key] = lang_translations
        
        return {
            'key_column': key_column,
            'languages': language_columns,
            'translations': translations
        }
    
    except Exception as e:
        raise ValueError(f"Failed to parse XLSX file {file_path}: {str(e)}")


def write_xlsx_file(file_path: str, content: Dict[str, Any]) -> None:
    """
    Write content to an XLSX translation file.
    
    Args:
        file_path: Path where to write the XLSX file
        content: Dictionary containing the XLSX content
        
    Raises:
        ValueError: If content is not a valid dictionary
    """
    if not isinstance(content, dict):
        raise ValueError("XLSX content must be a dictionary")
    
    if 'translations' not in content or 'languages' not in content:
        raise ValueError("XLSX content must contain 'translations' and 'languages' keys")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    key_column = content.get('key_column', 'key')
    languages = content['languages']
    translations = content['translations']
    
    # Create workbook and worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Translations"
    
    # Write header
    header_row = [key_column] + languages
    ws.append(header_row)
    
    # Write data rows
    for key, lang_translations in translations.items():
        if isinstance(lang_translations, dict):
            row = [key]
            for lang in languages:
                row.append(lang_translations.get(lang, ""))
            ws.append(row)

    # Translations are text: a value starting with "=" must never become a formula.
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
    
    # Save the workbook
    wb.save(file_path)


def extract_translatable_strings(xlsx_content: Dict[str, Any], 
                               target_language: str) -> Dict[str, str]:
    """
    Extract translatable strings from XLSX content for a specific language.
    
    Args:
        xlsx_content: XLSX file content as dictionary
        target_language: Target language code
        
    Returns:
        Dictionary of key-value pairs for translatable strings
    """
    if 'translations' not in xlsx_content:
        return {}
    
    translatable = {}
    translations = xlsx_content['translations']
    
    for key, lang_translations in translations.items():
        if isinstance(lang_translations, dict) and target_language in lang_translations:
            translatable[key] = lang_translations[target_language]
    
    return translatable


def create_xlsx_from_translations(translations: Dict[str, str], 
                                languages: List[str],
                                key_column: str = "key") -> Dict[str, Any]:
    """
    Create XLSX content from translations.
    
    Args:
        translations: Dictionary of key-value translation pairs
        languages: List of language codes
        key_column: Name of the key column
        
    Returns:
        XLSX content dictionary
    """
    # For single language translations, we need to create a structure
    # that can be extended with more languages
    xlsx_translations = {}
    
    for key, value in translations.items():
        # Create a single-language translation structure
        lang_translations = {languages[0]: value} if languages else {}
        xlsx_translations[key] = lang_translations
    
    return {
        'key_column': key_column,
        'languages': languages,
        'translations': xlsx_translations
    }


def add_language_to_xlsx(xlsx_content: Dict[str, Any], 
                        language: str, 
                        translations: Dict[str, str]) -> Dict[str, Any]:
    """
    Add a new language to existing XLSX content.
    
    Args:
        xlsx_content: Existing XLSX content
        language: New language code to add
        translations: Translations for the new language
        
    Returns:
        Updated XLSX content dictionary
    """
    if 'translations' not in xlsx_content:
        xlsx_content['translations'] = {}
    
    if language not in xlsx_content['languages']:
        xlsx_content['languages'].append(language)
    
    for key, value in translations.items():
        if key not in xlsx_content['translations']:
            xlsx_content['translations'][key] = {}
        xlsx_content['translations'][key][language] = value
    
    return xlsx_content


def get_xlsx_language_codes(xlsx_content: Dict[str, Any]) -> List[str]:
    """
    Get all language codes from XLSX content.
    
    Args:
        xlsx_content: XLSX file content as dictionary
        
    Returns:
        List of language codes
    """
    return xlsx_content.get('languages', [])


def is_valid_xlsx_file(file_path: str) -> bool:
    """
    Check if a file is a valid XLSX translation file.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file is a valid XLSX file, False otherwise
    """
    try:
        content = read_xlsx_file(file_path)
        return 'translations' in content and 'languages' in content
    except (FileNotFoundError, ValueError):
        return False


def get_xlsx_language_code(file_path: str) -> Optional[str]:
    """
    Extract language code from XLSX file path.
    
    Args:
        file_path: Path to the XLSX file
        
    Returns:
        Language code if found, None otherwise
    """
    # For XLSX files, we typically don't extract language from filename
    # since they contain multiple languages. Return None to indicate
    # this is a multi-language file.
    return None


def is_glossary_xlsx(file_path: str) -> bool:
    """
    Check if an XLSX file is a glossary file (vs translation file).
    
    Args:
        file_path: Path to the XLSX file
        
    Returns:
        True if the file appears to be a glossary file, False otherwise
    """
    try:
        wb = load_workbook(filename=file_path, read_only=True, data_only=True)
        ws = wb.active
        
        if ws is None:
            wb.close()
            return False
        
        # Get first row
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        
        if not rows:
            return False
        
        headers = [_safe_cell_value(cell) for cell in rows[0]]
        
        # Glossary files typically have "Record ID" as first column
        # Translation files typically have "key" as first column
        if headers and len(headers) > 0:
            first_header = str(headers[0]).lower().strip()
            return first_header in ['record id', 'record_id', 'id']
    except Exception:
        pass
    
    return False


def _safe_cell_value(cell_value) -> str:
    """
    Convert a cell value to a safe string representation.
    
    Args:
        cell_value: The cell value to convert
        
    Returns:
        String representation of the cell value
    """
    if cell_value is None:
        return ""
    
    if isinstance(cell_value, bool):
        return "TRUE" if cell_value else "FALSE"
    
    if isinstance(cell_value, (int, float)):
        if isinstance(cell_value, float):
            if cell_value != cell_value:  # NaN check
                return ""
            if cell_value.is_integer():
                return str(int(cell_value))
        return str(cell_value)
    
    if isinstance(cell_value, str):
        return cell_value.strip()

    return str(cell_value)


# ---------------------------------------------------------------------------
# Cell-level access: read cells with their coordinates, update single cells in place
# ---------------------------------------------------------------------------
#
# read_xlsx_file/write_xlsx_file work on a plain dict and rebuild the workbook, which loses styles,
# other sheets and column widths. The functions below open the existing workbook, change only the
# given cells and save it, so everything else stays as it was. Like read_xlsx_file they work on the
# active sheet: row 1 holds the headers, column A the keys.


class XlsxCell:
    """A translation cell: its coordinate (e.g. "D14") and its text."""

    __slots__ = ("coordinate", "value")

    def __init__(self, coordinate: str, value: str):
        self.coordinate = coordinate
        self.value = value

    def __repr__(self) -> str:
        return f"XlsxCell({self.coordinate!r}, {self.value!r})"


class XlsxSheet:
    """The translation sheet of a workbook: rows[key][language column] -> XlsxCell."""

    def __init__(
        self,
        title: str,
        key_column: str,
        languages: List[str],
        rows: Dict[str, Dict[str, XlsxCell]],
        row_of: Optional[Dict[str, int]] = None,
        letters: Optional[Dict[str, str]] = None,
    ):
        self.title = title
        self.key_column = key_column
        self.languages = languages
        self.rows = rows
        self.row_of = row_of or {}  # key -> row number
        self.letters = letters or {}  # language column -> column letter

    def ref(self, coordinate: str) -> str:
        """Excel reference such as Sheet1!D14 ('My sheet'!D14 when the title needs quotes)."""
        title = self.title
        if not title.replace("_", "").isalnum():
            title = "'" + title.replace("'", "''") + "'"
        return f"{title}!{coordinate}"

    def coordinate(self, key: str, language: str) -> Optional[str]:
        """Coordinate of a key's cell in a language column, also when the cell is empty."""
        if key not in self.row_of or language not in self.letters:
            return None
        return f"{self.letters[language]}{self.row_of[key]}"

    def column(self, language: str) -> Dict[str, XlsxCell]:
        """{key: cell} for one language column (empty cells left out)."""
        return {key: cells[language] for key, cells in self.rows.items() if language in cells}


def _is_rich_text(value) -> bool:
    return type(value).__name__ == "CellRichText"


def _cell_text(value) -> str:
    """Cell value as text, without stripping (rich text is joined into one string)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if _is_rich_text(value):
        return str(value)
    return _safe_cell_value(value)


def read_xlsx_cells(file_path: str) -> XlsxSheet:
    """
    The translation sheet with each cell's coordinate. Keys and headers are stripped as in
    read_xlsx_file; values are kept exactly as stored (whitespace-only values are left out).
    """
    from openpyxl.utils import get_column_letter

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"XLSX file not found: {file_path}")
    wb = load_workbook(filename=file_path, read_only=True, data_only=True)
    try:
        ws = wb.active
        if ws is None:
            raise ValueError(f"No active worksheet found in XLSX file {file_path}")
        title = ws.title
        rows_iter = ws.iter_rows(values_only=True)
        header_row = next(rows_iter, None)
        if not header_row:
            raise ValueError(f"XLSX file {file_path} is empty")
        headers = [_safe_cell_value(c) for c in header_row]
        rows: Dict[str, Dict[str, XlsxCell]] = {}
        row_of: Dict[str, int] = {}
        letters = {h: get_column_letter(i) for i, h in enumerate(headers, start=1) if h and i > 1}
        for row_index, row in enumerate(rows_iter, start=2):
            if not row:
                continue
            key = _safe_cell_value(row[0])
            if not key:
                continue
            if key in rows:
                continue  # duplicate key: the first row is the one update_xlsx_cells writes
            cells = rows[key] = {}
            row_of[key] = row_index
            for col_index, language in enumerate(headers[1:], start=2):
                if not language or col_index > len(row):
                    continue
                text = _cell_text(row[col_index - 1])
                if text.strip():
                    cells[language] = XlsxCell(f"{get_column_letter(col_index)}{row_index}", text)
    finally:
        wb.close()
    return XlsxSheet(title, headers[0] if headers else "key", [h for h in headers[1:] if h], rows, row_of, letters)


def _load_for_edit(file_path: str):
    """Workbook opened for editing; rich-text runs are loaded so that saving keeps them."""
    try:
        return load_workbook(filename=file_path, rich_text=True)
    except TypeError:  # openpyxl < 3.1 has no rich text support
        return load_workbook(filename=file_path)


def _runs_with_edit(rich, new_text: str):
    """
    `rich` (a CellRichText) with its text changed to `new_text`, keeping the runs, or None when a
    change crosses a run boundary (then the run structure cannot be kept).
    """
    from difflib import SequenceMatcher

    from openpyxl.cell.rich_text import CellRichText, TextBlock

    runs = list(rich)
    texts = [r if isinstance(r, str) else r.text for r in runs]
    starts = []
    pos = 0
    for t in texts:
        starts.append(pos)
        pos += len(t)
    old_text = "".join(texts)

    def run_of(i1: int, i2: int) -> Optional[int]:
        for idx, (start, t) in enumerate(zip(starts, texts)):
            end = start + len(t)
            if i1 == i2:  # insertion: goes to the run it follows (or the first run)
                if start < i1 <= end or (i1 == 0 and idx == 0):
                    return idx
            elif start <= i1 and i2 <= end:
                return idx
        return None

    new_texts = list(texts)
    opcodes = SequenceMatcher(None, old_text, new_text, autojunk=False).get_opcodes()
    kept = sum(i2 - i1 for tag, i1, i2, _, _ in opcodes if tag == "equal")
    if kept * 2 < len(old_text):
        return None  # mostly new text (a translation, not a repair): the runs no longer apply
    for tag, i1, i2, j1, j2 in reversed(opcodes):
        if tag == "equal":
            continue
        idx = run_of(i1, i2)
        if idx is None:
            return None
        local1, local2 = i1 - starts[idx], i2 - starts[idx]
        new_texts[idx] = new_texts[idx][:local1] + new_text[j1:j2] + new_texts[idx][local2:]
    out = []
    for run, text in zip(runs, new_texts):
        out.append(text if isinstance(run, str) else TextBlock(run.font, text))
    return CellRichText(out)


def set_cell_text(cell, text: str, keep_runs: bool = False) -> bool:
    """
    Write `text` to `cell` as an explicit string, so that "=…", "+…", "-…" or "@…" never turns into
    a formula. The cell's style stays. With `keep_runs`, a rich-text cell keeps its runs when the
    change fits inside them (e.g. a repaired placeholder). Returns False when a rich-text cell was
    written as plain text (its runs were dropped).
    """
    old = cell.value
    if _is_rich_text(old) and text:
        edited = _runs_with_edit(old, text) if keep_runs else None
        if edited is not None:
            cell.value = edited
            return True
        cell.value = text
        cell.data_type = "s"
        return False
    cell.value = text if text else None
    if text:
        cell.data_type = "s"
    return True


def update_xlsx_cells(
    file_path: str,
    language: str,
    values: Dict[str, str],
    template_file: Optional[str] = None,
    add_missing: bool = True,
    keep_runs: bool = False,
) -> Dict[str, List[str]]:
    """
    Write `values` ({key: text}) to the `language` column of the workbook and save it. Only those
    cells change: styles, other sheets, column widths and comments stay. A missing target file is
    created as a copy of `template_file` (the source workbook) when given. A missing language column
    is added after the last one, with the style and width of the column before it. With
    `keep_runs`, rich-text cells keep their runs where the change fits inside them (small edits,
    such as repaired placeholders); a translation replaces the whole text and is written plain.

    Returns {"written": [coordinates], "missing": [keys not found], "runs_dropped": [coordinates of
    rich-text cells written as plain text]}.
    """
    import shutil
    from copy import copy

    from openpyxl.utils import get_column_letter

    report: Dict[str, List[str]] = {"written": [], "missing": [], "runs_dropped": []}
    if not os.path.exists(file_path):
        same = template_file and os.path.abspath(template_file) == os.path.abspath(file_path)
        if template_file and os.path.exists(template_file) and not same:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            shutil.copyfile(template_file, file_path)
        else:
            write_xlsx_file(file_path, {"key_column": "key", "languages": [language], "translations": {}})
    if not values:
        return report

    wb = _load_for_edit(file_path)
    ws = wb.active
    if ws is None:
        raise ValueError(f"No active worksheet found in XLSX file {file_path}")

    max_col = ws.max_column
    column = None
    for col in range(1, max_col + 1):
        if _safe_cell_value(_cell_text(ws.cell(row=1, column=col).value)) == language:
            column = col
            break
    if column is None:
        column = max_col + 1
        header = ws.cell(row=1, column=column)
        set_cell_text(header, language)
        previous = ws.cell(row=1, column=max_col)
        if previous.has_style:
            header._style = copy(previous._style)
        width = ws.column_dimensions[get_column_letter(max_col)].width
        if width:
            ws.column_dimensions[get_column_letter(column)].width = width

    rows: Dict[str, int] = {}
    for row in range(2, ws.max_row + 1):
        key = _safe_cell_value(_cell_text(ws.cell(row=row, column=1).value))
        if key and key not in rows:
            rows[key] = row

    for key, text in values.items():
        row = rows.get(key)
        if row is None:
            if not add_missing:
                report["missing"].append(key)
                continue
            row = ws.max_row + 1
            set_cell_text(ws.cell(row=row, column=1), key)
            rows[key] = row
        cell = ws.cell(row=row, column=column)
        if not set_cell_text(cell, text, keep_runs):
            report["runs_dropped"].append(cell.coordinate)
        report["written"].append(cell.coordinate)

    wb.save(file_path)
    return report
