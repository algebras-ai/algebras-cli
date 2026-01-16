"""
String normalizer for translation strings.
"""

from algebras.config import Config as ConfigClass


class StringNormalizer:
    """Normalizes translated strings by removing escaped characters if they weren't present in the source text."""

    def __init__(self, config: ConfigClass):
        """
        Initialize StringNormalizer with a Config instance.

        Args:
            config: Config instance for reading normalization settings
        """
        self.config = config

    def normalize(self, source_text: str, translated_text: str) -> str:
        """
        Normalize a translated string by removing escaped characters if they weren't
        present in the source text.

        Args:
            source_text: The original source text
            translated_text: The translated text from the API

        Returns:
            Normalized translated text
        """
        # Check if normalization is enabled
        if not self.config.get_setting("api.normalize_strings", True):
            return translated_text

        # Common escaped characters to normalize
        escape_mappings = {
            "\\'": "'",  # Escaped apostrophe
            '\\"': '"',  # Escaped quote
            "\\\\": "\\",  # Escaped backslash
            "\\n": "\n",  # Escaped newline (keep as actual newline)
            "\\t": "\t",  # Escaped tab (keep as actual tab)
            "\\r": "\r",  # Escaped carriage return (keep as actual carriage return)
        }

        # Only normalize if the source text doesn't contain these escaped characters
        normalized_text = translated_text
        for escaped_char, unescaped_char in escape_mappings.items():
            # Only normalize if the source text doesn't contain the escaped version
            if escaped_char not in source_text and escaped_char in normalized_text:
                normalized_text = normalized_text.replace(escaped_char, unescaped_char)

        return normalized_text
