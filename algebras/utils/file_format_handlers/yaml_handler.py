"""
YAML file format handler
"""

import yaml
from typing import Dict, Any

from algebras.utils.file_format_handlers.base import FileFormatHandler
from algebras.utils.ts_handler import convert_numeric_dicts_to_lists


class YAMLHandler(FileFormatHandler):
    """Handler for YAML files"""
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """Read YAML file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """Write YAML file"""
        # Convert numeric-key dicts to lists to preserve arrays
        content = convert_numeric_dicts_to_lists(content)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                content,
                f,
                default_flow_style=False,
                allow_unicode=True,
            )
