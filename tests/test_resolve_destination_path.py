"""
Tests for the resolve_destination_path function
"""

import os
import tempfile
import yaml
from algebras.utils.path_utils import resolve_destination_path
from algebras.config import Config


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


def test_resolve_destination_path_with_mapping():
    """Test that destination paths use mapped locale codes when Config is provided"""
    # Create a temporary config file with mappings
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config_data = {
            'languages': [
                'en',
                {'es': 'es%sda'}
            ],
            'source_files': {}
        }
        yaml.dump(config_data, f)
        config_path = f.name
    
    try:
        config = Config(config_path)
        config.load()
        
        # Test with mapped locale code
        pattern = "locale/messages.%algebras_locale_code%.xlf"
        result = resolve_destination_path(pattern, "es", config)
        expected = "locale/messages.es%sda.xlf"
        assert result == expected
        
        # Test with unmapped locale code (should use original)
        pattern = "locale/messages.%algebras_locale_code%.xlf"
        result = resolve_destination_path(pattern, "en", config)
        expected = "locale/messages.en.xlf"
        assert result == expected
        
        # Test with multiple placeholders using mapped code
        pattern = "locales/%algebras_locale_code%/%algebras_locale_code%.json"
        result = resolve_destination_path(pattern, "es", config)
        expected = "locales/es%sda/es%sda.json"
        assert result == expected
    finally:
        os.unlink(config_path)


def test_resolve_destination_path_backward_compatibility():
    """Test that resolve_destination_path works without Config (backward compatibility)"""
    # Should work exactly as before when no Config is provided
    pattern = "src/locales/%algebras_locale_code%/common.json"
    result = resolve_destination_path(pattern, "fr")
    expected = "src/locales/fr/common.json"
    assert result == expected


def test_config_locale_mapping():
    """Test Config locale mapping methods"""
    # Create a temporary config file with mixed format
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config_data = {
            'languages': [
                'en',
                'fr',
                {'es': 'es%sda'},
                {'de': 'de-DE'}
            ],
            'source_files': {}
        }
        yaml.dump(config_data, f)
        config_path = f.name
    
    try:
        config = Config(config_path)
        config.load()
        
        # Test get_languages() returns language codes
        languages = config.get_languages()
        assert 'en' in languages
        assert 'fr' in languages
        assert 'es' in languages
        assert 'de' in languages
        
        # Test get_locale_mapping() returns full mapping
        mapping = config.get_locale_mapping()
        assert mapping['en'] == 'en'  # Unmapped defaults to itself
        assert mapping['fr'] == 'fr'  # Unmapped defaults to itself
        assert mapping['es'] == 'es%sda'  # Mapped value
        assert mapping['de'] == 'de-DE'  # Mapped value
        
        # Test get_destination_locale_code()
        assert config.get_destination_locale_code('en') == 'en'
        assert config.get_destination_locale_code('fr') == 'fr'
        assert config.get_destination_locale_code('es') == 'es%sda'
        assert config.get_destination_locale_code('de') == 'de-DE'
        assert config.get_destination_locale_code('nonexistent') == 'nonexistent'  # Defaults to input
    finally:
        os.unlink(config_path)
