"""
JSON file format handler
"""

import json
from typing import Dict, Any

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ts_handler import convert_numeric_dicts_to_lists


class JSONHandler(FileFormatHandler):
    """Handler for JSON files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read JSON file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write JSON file"""
        # Convert numeric-key dicts to lists to preserve arrays
        content = convert_numeric_dicts_to_lists(content)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
