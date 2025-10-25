import pytest

from algebras.utils.string_normalizer import normalize_for_glossary


class TestGlossaryNormalization:
    def test_nbsp_is_converted_to_space(self):
        s = "a\u00A0b"
        assert normalize_for_glossary(s) == "a b"

    def test_ellipsis_is_converted_to_three_dots(self):
        s = "wait…"
        assert normalize_for_glossary(s) == "wait..."

    def test_none_returns_none(self):
        assert normalize_for_glossary(None) is None


