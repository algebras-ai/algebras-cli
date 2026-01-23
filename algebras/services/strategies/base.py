"""
Base translation strategy interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable

from algebras.config import Config as ConfigClass
from algebras.services.batch_processor import BatchProcessor
from algebras.services.string_normalizer import StringNormalizer


class TranslationStrategy(ABC):
    """Abstract base class for translation strategies."""

    def __init__(
        self,
        config: ConfigClass,
        batch_processor: BatchProcessor,
        string_normalizer: StringNormalizer,
        batch_size: int,
        api_config: Dict[str, Any],
    ):
        """
        Initialize translation strategy.

        Args:
            config: Config instance for accessing settings
            batch_processor: BatchProcessor for batch translation
            string_normalizer: StringNormalizer for normalizing translations
            batch_size: Batch size for processing
            api_config: API configuration dictionary
        """
        self.config = config
        self.batch_processor = batch_processor
        self.string_normalizer = string_normalizer
        self.batch_size = batch_size
        self.api_config = api_config

    @abstractmethod
    def translate(
        self,
        data: Dict[str, Any],
        source_lang: str,
        target_lang: str,
        ui_safe: bool = False,
        glossary_id: Optional[str] = None,
        on_batch_complete: Optional[Callable[[Dict[str, str], int], None]] = None,
        translate_text_func: Optional[Callable[[str, str, str, bool, str], str]] = None,
    ) -> Dict[str, Any]:
        """
        Translate data using this strategy.

        Args:
            data: Data to translate (format depends on strategy)
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensures translation will be no more characters than original text
            glossary_id: Glossary ID to use for translation (if None, will check config)
            on_batch_complete: Optional callback function called after each batch completes

        Returns:
            Translated data in the same format as input
        """
        pass

    def _resolve_glossary_id(self, glossary_id: Optional[str]) -> str:
        """
        Resolve glossary_id from config if not provided.

        Args:
            glossary_id: Optional glossary ID

        Returns:
            Glossary ID string (empty if not set)
        """
        if glossary_id is None:
            return self.config.get_setting("api.glossary_id", "")
        return glossary_id
