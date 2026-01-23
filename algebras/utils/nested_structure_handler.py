"""
Utilities for working with nested dictionary and list structures.
"""

from typing import Dict, Any, List


def _is_numeric_key(key: str) -> bool:
    """Check if a key represents a numeric index."""
    try:
        int(key)
        return True
    except ValueError:
        return False


def _convert_dict_to_list_if_needed(d: Dict[str, Any]) -> Any:
    """Convert a dict with only numeric keys to a list."""
    if not isinstance(d, dict) or not d:
        return d
    # Check if all keys are numeric
    all_numeric = all(_is_numeric_key(k) for k in d.keys())
    if not all_numeric:
        return d
    # Convert to list
    max_index = max(int(k) for k in d.keys())
    arr = [None] * (max_index + 1)
    for k, v in d.items():
        arr[int(k)] = v
    return arr


def get_nested_value(data: Dict[str, Any], key_parts: List[str]) -> Any:
    """
    Get a value from a nested dictionary or array using a list of key parts.
    Supports array indices (numeric keys) for accessing array elements.

    Args:
        data: Dictionary or list to get value from
        key_parts: List of key parts representing a dot-notation path (e.g., ['items', '0'] for 'items.0')

    Returns:
        Value at the specified path, or None if not found
    """
    current = data
    for part in key_parts:
        if current is None:
            return None

        # Check if current is a list and part is a numeric index
        if isinstance(current, list):
            try:
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            except ValueError:
                # Part is not a number, can't access list with non-numeric key
                return None
        # Check if current is a dict
        elif isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None
        else:
            # Current is neither dict nor list, can't traverse further
            return None

    return current


def set_nested_value(
    data: Dict[str, Any], key_parts: List[str], value: Any
) -> None:
    """
    Set a value in a nested dictionary or array using a list of key parts.
    Will create intermediate dictionaries or arrays if they don't exist.
    Supports array indices (numeric keys) for creating and accessing arrays.

    Args:
        data: Dictionary to update
        key_parts: List of key parts representing a dot-notation path (e.g., ['items', '0'] for 'items.0')
        value: Value to set
    """
    current = data
    for i, part in enumerate(key_parts):
        is_last = i == len(key_parts) - 1
        is_numeric = _is_numeric_key(part)
        next_is_numeric = not is_last and _is_numeric_key(key_parts[i + 1])

        if is_last:
            # Last part, set the value
            if is_numeric:
                index = int(part)
                if isinstance(current, list):
                    # Extend list if needed
                    while len(current) <= index:
                        current.append(None)
                    current[index] = value
                elif isinstance(current, dict):
                    # For dict, we'll store as dict with numeric key
                    # It will be converted to list later if all keys are numeric
                    current[part] = value
                else:
                    # Can't set on non-container
                    return
            else:
                # String key
                if isinstance(current, dict):
                    current[part] = value
                else:
                    return
        else:
            # Intermediate part - navigate/create
            if is_numeric:
                index = int(part)
                if isinstance(current, list):
                    while len(current) <= index:
                        current.append(None)
                    if current[index] is None:
                        current[index] = [] if next_is_numeric else {}
                    current = current[index]
                elif isinstance(current, dict):
                    if part in current:
                        existing = current[part]
                        if isinstance(existing, list):
                            current = existing
                        elif isinstance(existing, dict) and next_is_numeric:
                            # Convert to list
                            arr = _convert_dict_to_list_if_needed(existing)
                            current[part] = arr
                            current = arr if isinstance(arr, list) else existing
                        else:
                            current = existing
                    else:
                        # Create new container
                        container = [] if next_is_numeric else {}
                        current[part] = container
                        current = container
                else:
                    return
            else:
                # String key
                if isinstance(current, dict):
                    if part not in current:
                        # Create appropriate container based on next key
                        if next_is_numeric:
                            # Next key is numeric, so create a list
                            current[part] = []
                        else:
                            # Next key is string, so create a dict
                            current[part] = {}
                    elif isinstance(current[part], list) and not next_is_numeric:
                        # We have a list but next key is string - this shouldn't happen normally
                        # but we'll convert to dict to handle it
                        d = {str(idx): val for idx, val in enumerate(current[part])}
                        current[part] = d
                    elif isinstance(current[part], dict) and next_is_numeric:
                        # We have a dict but next key is numeric - check if we should convert to list
                        # Only convert if dict has numeric keys or is empty
                        if not current[part] or all(
                            _is_numeric_key(k) for k in current[part].keys()
                        ):
                            arr = _convert_dict_to_list_if_needed(current[part])
                            if isinstance(arr, list):
                                current[part] = arr
                    current = current[part]
                elif isinstance(current, list):
                    # Can't use string key on list
                    return
                else:
                    return
