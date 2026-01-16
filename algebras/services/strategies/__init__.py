"""
Translation strategies module.
"""

from algebras.services.strategies.base import TranslationStrategy
from algebras.services.strategies.flat_dict_strategy import FlatDictTranslationStrategy
from algebras.services.strategies.nested_dict_strategy import NestedDictTranslationStrategy
from algebras.services.strategies.csv_strategy import CsvTranslationStrategy
from algebras.services.strategies.xlsx_strategy import XlsxTranslationStrategy
from algebras.services.strategies.strategy_factory import TranslationStrategyFactory

__all__ = [
    "TranslationStrategy",
    "FlatDictTranslationStrategy",
    "NestedDictTranslationStrategy",
    "CsvTranslationStrategy",
    "XlsxTranslationStrategy",
    "TranslationStrategyFactory",
]
