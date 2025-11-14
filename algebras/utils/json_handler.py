"""
JSON localization file handler with in-place update support.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from typing import Any, Dict, Iterable, Optional, Sequence, Set, Tuple, Union


def write_json_file(file_path: str, content: Dict[str, Any], indent: int = 2) -> None:
    """
    Write JSON content to disk using a consistent style.

    Args:
        file_path: Path to the JSON file.
        content: Dictionary to serialize.
        indent: Number of spaces to indent by (default: 2).
    """
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def write_json_file_in_place(
    file_path: str,
    content: Dict[str, Any],
    keys_to_update: Optional[Set[str]] = None,
) -> None:
    """
    Update an existing JSON file in-place, preserving indentation, ordering, and line endings.

    Args:
        file_path: Path to the JSON file.
        content: Dictionary containing the updated translations.
        keys_to_update: Optional set of dot-notation keys to update. If None, all keys are updated.
    """
    if not os.path.exists(file_path):
        write_json_file(file_path, content)
        return

    with open(file_path, "r", encoding="utf-8") as f:
        original_text = f.read()

    try:
        original_data = json.loads(original_text, object_pairs_hook=OrderedDict)
    except json.JSONDecodeError:
        # Fall back to rewriting the file if parsing fails
        write_json_file(file_path, content)
        return

    keys_to_apply: Set[str]
    if keys_to_update is None:
        keys_to_apply = _extract_all_keys(content)
    else:
        keys_to_apply = set(keys_to_update)

    updated_keys: Set[str] = set()
    for key in keys_to_apply:
        new_value = _get_nested_value(content, key)
        if new_value is None:
            continue
        _set_nested_value(original_data, key.split("."), _convert_to_ordered(new_value))
        updated_keys.add(key)

    if not updated_keys:
        # Nothing to update, keep original file
        return

    indent_token, line_ending, trailing_newline = _detect_json_style(original_text)
    serialized = json.dumps(
        original_data,
        ensure_ascii=False,
        indent=indent_token,
        separators=(",", ": ") if indent_token else (",", ":"),
    )

    if line_ending != "\n":
        serialized = serialized.replace("\n", line_ending)

    if trailing_newline:
        if not serialized.endswith(line_ending):
            serialized += line_ending
    else:
        serialized = serialized.rstrip(line_ending)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(serialized)


def _extract_all_keys(data: Any, prefix: str = "") -> Set[str]:
    keys: Set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)
            keys.update(_extract_all_keys(value, full_key))
    return keys


def _get_nested_value(data: Dict[str, Any], dotted_key: str) -> Any:
    parts = dotted_key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _set_nested_value(data: OrderedDict, key_parts: Sequence[str], value: Any) -> None:
    current: OrderedDict = data
    for index, part in enumerate(key_parts):
        is_last = index == len(key_parts) - 1
        if is_last:
            current[part] = value
        else:
            next_value = current.get(part)
            if not isinstance(next_value, OrderedDict):
                next_value = OrderedDict()
                current[part] = next_value
            current = next_value


def _convert_to_ordered(value: Any) -> Any:
    if isinstance(value, dict) and not isinstance(value, OrderedDict):
        ordered = OrderedDict()
        for key, nested in value.items():
            ordered[key] = _convert_to_ordered(nested)
        return ordered
    if isinstance(value, list):
        return [_convert_to_ordered(item) for item in value]
    return value


def _detect_json_style(text: str) -> Tuple[Union[int, str, None], str, bool]:
    """
    Detect indentation token (spaces count or tab), line ending, and trailing newline usage.
    """
    indent_token: Union[int, str, None] = 2
    line_ending = "\n"
    trailing_newline = text.endswith("\n")

    if "\r\n" in text:
        line_ending = "\r\n"
        trailing_newline = text.endswith("\r\n")

    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith('"'):
            continue
        prefix = line[: len(line) - len(stripped)]
        if not prefix:
            continue
        if set(prefix) == {"\t"}:
            indent_token = "\t"
            break
        if set(prefix) == {" "}:
            indent_token = len(prefix)
            break

    # If the original file was minified (no line breaks), indent_token should be None
    if "\n" not in text and "\r" not in text:
        indent_token = None

    return indent_token, line_ending, trailing_newline

