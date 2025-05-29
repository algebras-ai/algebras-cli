"""
TypeScript translation file handler
"""

import re
import ast
import json
from typing import Dict, Any


def read_ts_translation_file(file_path: str) -> Dict[str, Any]:
    """
    Read a TypeScript translation file and extract the exported object.
    
    Args:
        file_path: Path to the TypeScript file
        
    Returns:
        Dictionary containing the translation content
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the export statement
    # Look for patterns like: export const en = { ... }
    export_pattern = r'export\s+const\s+(\w+)\s*=\s*({.*?});?$'
    match = re.search(export_pattern, content, re.DOTALL | re.MULTILINE)
    
    if not match:
        raise ValueError(f"No valid TypeScript export found in {file_path}")
    
    export_name = match.group(1)
    object_content = match.group(2)
    
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


def write_ts_translation_file(file_path: str, content: Dict[str, Any], export_name: str = None) -> None:
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
        export_name = basename.split('.')[0]
    
    # Convert Python dict to TypeScript object
    ts_object = _python_dict_to_ts_object(content, indent=2)
    
    # Create the TypeScript export
    ts_content = f"export const {export_name} = {ts_object};\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
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
    js_content = re.sub(r'//.*?$', '', js_content, flags=re.MULTILINE)
    js_content = re.sub(r'/\*.*?\*/', '', js_content, flags=re.DOTALL)
    
    # Replace unquoted keys with quoted keys
    # Pattern to match unquoted object keys
    js_content = re.sub(r'(\n\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:', r'\1"\2":', js_content)
    
    # Replace JavaScript boolean/null values with Python equivalents
    js_content = js_content.replace('true', 'True')
    js_content = js_content.replace('false', 'False')
    js_content = js_content.replace('null', 'None')
    
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
    spaces = '  ' * indent
    inner_spaces = '  ' * (indent + 1)
    
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        
        lines = ['{']
        for key, value in obj.items():
            ts_value = _python_dict_to_ts_object(value, indent + 1)
            lines.append(f'{inner_spaces}{key}: {ts_value},')
        lines.append(f'{spaces}}}')
        return '\n'.join(lines)
    
    elif isinstance(obj, list):
        if not obj:
            return '[]'
        
        lines = ['[']
        for item in obj:
            ts_value = _python_dict_to_ts_object(item, indent + 1)
            lines.append(f'{inner_spaces}{ts_value},')
        lines.append(f'{spaces}]')
        return '\n'.join(lines)
    
    elif isinstance(obj, str):
        # Escape quotes and handle multiline strings
        escaped = obj.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return f'"{escaped}"'
    
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    
    elif obj is None:
        return 'null'
    
    else:
        # For numbers and other types
        return str(obj) 