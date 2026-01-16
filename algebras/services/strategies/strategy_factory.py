"""
Factory for creating translation strategies based on file format.
"""

from typing import TYPE_CHECKING

from algebras.services.strategies.flat_dict_strategy import FlatDictTranslationStrategy
from algebras.services.strategies.nested_dict_strategy import NestedDictTranslationStrategy
from algebras.services.strategies.csv_strategy import CsvTranslationStrategy
from algebras.services.strategies.xlsx_strategy import XlsxTranslationStrategy
from algebras.services.strategies.base import TranslationStrategy

if TYPE_CHECKING:
    from algebras.services.translator import Translator


class TranslationStrategyFactory:
    """Factory for creating translation strategies."""

    @staticmethod
    def get_strategy(file_path: str, translator: "Translator") -> TranslationStrategy:
        """
        Get appropriate translation strategy for the given file path.

        Args:
            file_path: Path to the file to translate
            translator: Translator instance for accessing dependencies

        Returns:
            TranslationStrategy instance appropriate for the file format
        """
        # Get dependencies from translator
        batch_processor = translator._get_batch_processor()
        api_config = translator.api_config

        # Determine strategy based on file extension
        if file_path.endswith((".html", ".properties")):
            # HTML and properties files are flat dictionaries
            return FlatDictTranslationStrategy(
                config=translator.config,
                batch_processor=batch_processor,
                string_normalizer=translator.string_normalizer,
                batch_size=translator.batch_size,
                api_config=api_config,
            )
        elif file_path.endswith((".csv", ".tsv")):
            # CSV/TSV files need special handling
            return CsvTranslationStrategy(
                config=translator.config,
                batch_processor=batch_processor,
                string_normalizer=translator.string_normalizer,
                batch_size=translator.batch_size,
                api_config=api_config,
            )
        elif file_path.endswith((".xlsx", ".xls")):
            # XLSX files need special handling
            return XlsxTranslationStrategy(
                config=translator.config,
                batch_processor=batch_processor,
                string_normalizer=translator.string_normalizer,
                batch_size=translator.batch_size,
                api_config=api_config,
            )
        else:
            # Default to nested dict strategy for JSON, YAML, TS, XML, strings, etc.
            return NestedDictTranslationStrategy(
                config=translator.config,
                batch_processor=batch_processor,
                string_normalizer=translator.string_normalizer,
                batch_size=translator.batch_size,
                api_config=api_config,
            )

    @staticmethod
    def get_flat_dict_strategy(translator: "Translator") -> FlatDictTranslationStrategy:
        """
        Get flat dict strategy (useful for special cases like ARB, XLIFF).

        Args:
            translator: Translator instance

        Returns:
            FlatDictTranslationStrategy instance
        """
        batch_processor = translator._get_batch_processor()
        return FlatDictTranslationStrategy(
            config=translator.config,
            batch_processor=batch_processor,
            string_normalizer=translator.string_normalizer,
            batch_size=translator.batch_size,
            api_config=translator.api_config,
        )

    @staticmethod
    def get_nested_dict_strategy(translator: "Translator") -> NestedDictTranslationStrategy:
        """
        Get nested dict strategy (useful for special cases).

        Args:
            translator: Translator instance

        Returns:
            NestedDictTranslationStrategy instance
        """
        batch_processor = translator._get_batch_processor()
        return NestedDictTranslationStrategy(
            config=translator.config,
            batch_processor=batch_processor,
            string_normalizer=translator.string_normalizer,
            batch_size=translator.batch_size,
            api_config=translator.api_config,
        )
