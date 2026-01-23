"""
Base file format handler
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from algebras.config import Config


class FileFormatHandler(ABC):
    """Base abstract class for file format handlers"""
    
    @abstractmethod
    def read(self, file_path: str) -> Dict[str, Any]:
        """
        Read file and return its contents as a dictionary.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary containing the file contents
        """
        pass
    
    def read_for_translation(
        self,
        file_path: str,
        language: Optional[str] = None,
        config: Optional["Config"] = None,
    ) -> Dict[str, Any]:
        """
        Read file for translation purposes.
        For most formats, this is the same as read(), but some formats
        (like CSV/XLIFF) may need special handling.
        
        Args:
            file_path: Path to the file
            language: Optional language code (for CSV files)
            config: Optional Config object (for CSV files)
            
        Returns:
            Dictionary containing translatable strings
        """
        return self.read(file_path)
    
    @abstractmethod
    def write(
        self,
        file_path: str,
        content: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Write content to file.
        
        Args:
            file_path: Path to the file
            content: Dictionary containing content to write
            **kwargs: Additional format-specific parameters
        """
        pass
    
    def write_in_place(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """
        Write content to file using in-place update (if supported).
        If not supported, falls back to regular write.
        
        Args:
            file_path: Path to the file
            content: Dictionary containing content to write
            keys_to_update: Set of keys that were updated
            **kwargs: Additional format-specific parameters
        """
        if self.supports_in_place():
            self._write_in_place_impl(file_path, content, keys_to_update, **kwargs)
        else:
            self.write(file_path, content, **kwargs)
    
    def _write_in_place_impl(
        self,
        file_path: str,
        content: Dict[str, Any],
        keys_to_update: Set[str],
        **kwargs
    ) -> None:
        """
        Internal implementation of in-place write.
        Override this method in subclasses that support in-place updates.
        
        Args:
            file_path: Path to the file
            content: Dictionary containing content to write
            keys_to_update: Set of keys that were updated
            **kwargs: Additional format-specific parameters
        """
        # Default implementation falls back to regular write
        self.write(file_path, content, **kwargs)
    
    def supports_in_place(self) -> bool:
        """
        Check if format supports in-place updates.
        
        Returns:
            True if format supports in-place updates, False otherwise
        """
        return False
    
    def extract_keys(self, content: Dict[str, Any]) -> Set[str]:
        """
        Extract all keys from content.
        For flat formats, returns content.keys().
        For nested formats, extracts all nested keys using dot notation.
        
        Args:
            content: Dictionary containing file content
            
        Returns:
            Set of all keys (using dot notation for nested keys)
        """
        from algebras.utils.lang_validator import extract_all_keys
        return extract_all_keys(content)
    
    def get_nested_value(self, content: Dict[str, Any], key: str) -> Any:
        """
        Get value from content by key (supports nested keys with dot notation).
        
        Args:
            content: Dictionary containing file content
            key: Key to retrieve (can use dot notation for nested keys)
            
        Returns:
            Value associated with the key, or None if not found
        """
        from algebras.utils.nested_structure_handler import get_nested_value
        key_parts = key.split(".")
        return get_nested_value(content, key_parts)
    
    def set_nested_value(self, content: Dict[str, Any], key: str, value: Any) -> None:
        """
        Set value in content by key (supports nested keys with dot notation).
        
        Args:
            content: Dictionary containing file content
            key: Key to set (can use dot notation for nested keys)
            value: Value to set
        """
        from algebras.utils.nested_structure_handler import set_nested_value
        key_parts = key.split(".")
        set_nested_value(content, key_parts, value)
