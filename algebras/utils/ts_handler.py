"""
TypeScript translation file handler
"""

import re
import ast
import json
import os
import threading
from typing import Dict, Any, Optional

from algebras.utils.nested_structure_handler import set_nested_value


def read_ts_translation_file(file_path: str) -> Dict[str, Any]:
    """
    Read a TypeScript translation file and extract the exported object.

    Args:
        file_path: Path to the TypeScript file

    Returns:
        Dictionary containing the translation content
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the export statement
    # Look for patterns like: export const en = { ... }
    export_pattern = r"export\s+const\s+(\w+)\s*=\s*"
    match = re.search(export_pattern, content, re.MULTILINE)

    if not match:
        raise ValueError(f"No valid TypeScript export found in {file_path}")

    export_name = match.group(1)
    start_pos = match.end()

    # Find the opening brace
    content_from_start = content[start_pos:]
    brace_pos = content_from_start.find("{")
    if brace_pos == -1:
        raise ValueError(
            f"No opening brace found after export statement in {file_path}"
        )

    # Extract the object content by counting braces
    object_start = start_pos + brace_pos
    object_content = _extract_balanced_braces(content, object_start)

    if not object_content:
        raise ValueError(f"Could not extract balanced object content from {file_path}")

    # Convert the JavaScript object to Python dict
    # This is a simplified approach - for complex objects, you might want to use a proper JS parser
    try:
        # Replace JavaScript object syntax with Python dict syntax
        python_content = _js_object_to_python_dict(object_content)

        # Safely evaluate the Python dict
        translation_dict = ast.literal_eval(python_content)
        return translation_dict
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Failed to parse TypeScript object in {file_path}: {str(e)}")


def write_ts_translation_file(
    file_path: str, content: Dict[str, Any], export_name: str = None
) -> None:
    """
    Write a dictionary to a TypeScript translation file.

    Args:
        file_path: Path to the TypeScript file
        content: Dictionary to write
        export_name: Name of the exported constant (defaults to language code from filename)
    """
    if export_name is None:
        # Extract export name from filename (e.g., en.ts -> en)
        import os

        basename = os.path.basename(file_path)
        export_name = basename.split(".")[0]

    # Convert Python dict to TypeScript object
    ts_object = _python_dict_to_ts_object(content, indent=2)

    # Create the TypeScript export
    ts_content = f"export const {export_name} = {ts_object};\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(ts_content)


def _js_object_to_python_dict(js_content: str) -> str:
    """
    Convert JavaScript object syntax to Python dict syntax.

    Args:
        js_content: JavaScript object string

    Returns:
        Python dict string
    """
    # Remove comments (single-line and multi-line)
    js_content = re.sub(r"//.*?$", "", js_content, flags=re.MULTILINE)
    js_content = re.sub(r"/\*.*?\*/", "", js_content, flags=re.DOTALL)

    # Replace unquoted keys with quoted keys
    # Pattern to match unquoted object keys
    js_content = re.sub(
        r"(\n\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:", r'\1"\2":', js_content
    )

    # Replace JavaScript boolean/null values with Python equivalents
    js_content = js_content.replace("true", "True")
    js_content = js_content.replace("false", "False")
    js_content = js_content.replace("null", "None")

    return js_content


def _python_dict_to_ts_object(obj: Any, indent: int = 0) -> str:
    """
    Convert Python dictionary to TypeScript object syntax.

    Args:
        obj: Python object to convert
        indent: Current indentation level

    Returns:
        TypeScript object string
    """
    spaces = "  " * indent
    inner_spaces = "  " * (indent + 1)

    if isinstance(obj, dict):
        if not obj:
            return "{}"

        lines = ["{"]
        for key, value in obj.items():
            ts_value = _python_dict_to_ts_object(value, indent + 1)
            # Check if key needs to be quoted for TypeScript
            formatted_key = _format_ts_key(key)
            lines.append(f"{inner_spaces}{formatted_key}: {ts_value},")
        lines.append(f"{spaces}}}")
        return "\n".join(lines)

    elif isinstance(obj, list):
        if not obj:
            return "[]"

        lines = ["["]
        for item in obj:
            ts_value = _python_dict_to_ts_object(item, indent + 1)
            lines.append(f"{inner_spaces}{ts_value},")
        lines.append(f"{spaces}]")
        return "\n".join(lines)

    elif isinstance(obj, str):
        # Escape quotes and handle multiline strings
        escaped = obj.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'

    elif isinstance(obj, bool):
        return "true" if obj else "false"

    elif obj is None:
        return "null"

    else:
        # For numbers and other types
        return str(obj)


def _format_ts_key(key: str) -> str:
    """
    Format a key for TypeScript object syntax, adding quotes if necessary.

    Args:
        key: The object key

    Returns:
        Formatted key, quoted if necessary
    """
    # Check if the key is a valid JavaScript identifier
    # Valid identifiers: start with letter, $, or _, followed by letters, digits, $, or _
    if re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$", key):
        return key
    else:
        # Key contains special characters, needs to be quoted
        escaped = key.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'


def _extract_balanced_braces(content: str, start_pos: int) -> str:
    """
    Extract content between balanced braces starting from start_pos.

    Args:
        content: Full content string
        start_pos: Position of the opening brace

    Returns:
        Content between balanced braces including the braces
    """
    if start_pos >= len(content) or content[start_pos] != "{":
        return ""

    brace_count = 0
    in_string = False
    escape_next = False
    string_delimiter = None

    for i, char in enumerate(content[start_pos:], start_pos):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if not in_string:
            if char in ['"', "'", "`"]:
                in_string = True
                string_delimiter = char
            elif char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return content[start_pos : i + 1]
        else:
            if char == string_delimiter:
                in_string = False
                string_delimiter = None

    return ""  # Unbalanced braces


def write_ts_translation_file_in_place(
    file_path: str,
    translations: Dict[str, str],
    export_name: Optional[str] = None,
    lock: Optional[threading.Lock] = None,
) -> None:
    """
    Incrementally update a TypeScript translation file with new translations.
    Updates existing keys and adds new keys if they don't exist.
    Supports both flat keys and nested keys (dot notation).

    Args:
        file_path: Path to the TypeScript file
        translations: Dictionary of key -> translation to update/add
        export_name: Name of the exported constant (defaults to language code from filename)
        lock: Optional lock for thread-safe file access
    """
    if lock:
        lock.acquire()
    try:
        # Read existing file or create new structure
        if os.path.exists(file_path):
            try:
                existing_content = read_ts_translation_file(file_path)
            except Exception:
                # If reading fails, start with empty dict
                existing_content = {}
        else:
            existing_content = {}

        # Determine export name
        if export_name is None:
            basename = os.path.basename(file_path)
            export_name = basename.split(".")[0]

        # Merge translations: update existing keys and add new keys
        # Handle both flat keys and nested keys (dot notation)
        for key, value in translations.items():
            if "." in key:
                # Nested key (dot notation) - create nested structure
                key_parts = key.split(".")
                set_nested_value(existing_content, key_parts, value)
            else:
                # Flat key - update or add directly
                existing_content[key] = value

        # Convert any dicts with only numeric keys to lists before writing
        existing_content = convert_numeric_dicts_to_lists(existing_content)

        # Write back to file
        write_ts_translation_file(file_path, existing_content, export_name)
    finally:
        if lock:
            lock.release()


def convert_numeric_dicts_to_lists(obj: Any) -> Any:
    """
    Recursively convert dictionaries with only numeric keys to lists.
    This ensures that arrays are properly represented as lists in Python.

    Args:
        obj: Object to convert (dict, list, or primitive)

    Returns:
        Converted object with numeric-key dicts converted to lists
    """
    if isinstance(obj, dict):
        # First, recursively process all values to convert nested structures
        processed_dict = {k: convert_numeric_dicts_to_lists(v) for k, v in obj.items()}

        # Then check if all keys are numeric (after processing)
        if processed_dict:
            all_numeric = all(
                isinstance(k, str) and k.isdigit() for k in processed_dict.keys()
            )

            if all_numeric:
                # Convert to list
                max_index = max(int(k) for k in processed_dict.keys())
                arr = [None] * (max_index + 1)
                for k, v in processed_dict.items():
                    arr[int(k)] = v
                return arr

        # Return processed dict (not all keys were numeric)
        return processed_dict
    elif isinstance(obj, list):
        # Recursively process list items
        return [convert_numeric_dicts_to_lists(item) for item in obj]
    else:
        # Primitive value, return as is
        return obj
