"""
Tests for the resolve_destination_path function
"""

import os
from algebras.utils.path_utils import resolve_destination_path


def test_resolve_destination_path():
    """Test that destination paths are correctly resolved"""
    # Test basic replacement
    pattern = "src/locales/%algebras_locale_code%/common.json"
    result = resolve_destination_path(pattern, "fr")
    expected = "src/locales/fr/common.json"
    assert result == expected
    
    # Test with different locale codes
    pattern = "public/locales/%algebras_locale_code%/translation.json"
    result = resolve_destination_path(pattern, "es")
    expected = "public/locales/es/translation.json"
    assert result == expected
    
    # Test Android values pattern
    pattern = "app/src/main/res/values-%algebras_locale_code%/strings.xml"
    result = resolve_destination_path(pattern, "de")
    expected = "app/src/main/res/values-de/strings.xml"
    assert result == expected
    
    # Test with complex locale codes
    pattern = "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
    result = resolve_destination_path(pattern, "pt_BR")
    expected = "locale/pt_BR/LC_MESSAGES/django.po"
    assert result == expected
    
    # Test with filename suffix pattern
    pattern = "html_files/index.%algebras_locale_code%.html"
    result = resolve_destination_path(pattern, "ja")
    expected = "html_files/index.ja.html"
    assert result == expected
    
    # Test with multiple placeholders (should replace all)
    pattern = "locales/%algebras_locale_code%/%algebras_locale_code%.json"
    result = resolve_destination_path(pattern, "ru")
    expected = "locales/ru/ru.json"
    assert result == expected
