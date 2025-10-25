"""
Tests for XLSX handler
"""

import os
import tempfile
import pytest
from algebras.utils.xlsx_handler import (
    read_xlsx_file, write_xlsx_file, extract_translatable_strings,
    create_xlsx_from_translations, add_language_to_xlsx, get_xlsx_language_codes,
    is_valid_xlsx_file, get_xlsx_language_code, is_glossary_xlsx
)


class TestXLSXHandler:
    """Test cases for XLSX handler functions."""
    
    def test_read_xlsx_file(self):
        """Test reading XLSX files."""
        xlsx_content = {
            'key_column': 'key',
            'languages': ['en', 'de', 'fr'],
            'translations': {
                'app.title': {
                    'en': 'My Application',
                    'de': 'Meine Anwendung',
                    'fr': 'Mon Application'
                },
                'welcome.message': {
                    'en': 'Welcome!',
                    'de': 'Willkommen!',
                    'fr': 'Bienvenue!'
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write the file first
            write_xlsx_file(temp_file, xlsx_content)
            
            # Read it back
            result = read_xlsx_file(temp_file)
            assert result['key_column'] == 'key'
            assert result['languages'] == ['en', 'de', 'fr']
            assert 'translations' in result
        finally:
            os.unlink(temp_file)
    
    def test_read_xlsx_file_not_found(self):
        """Test reading non-existent XLSX file."""
        with pytest.raises(FileNotFoundError):
            read_xlsx_file("nonexistent.xlsx")
    
    def test_write_xlsx_file(self):
        """Test writing XLSX files."""
        xlsx_content = {
            'key_column': 'key',
            'languages': ['en', 'de'],
            'translations': {
                'app.title': {
                    'en': 'My Application',
                    'de': 'Meine Anwendung'
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xlsx_file(temp_file, xlsx_content)
            
            # Read it back to verify
            result = read_xlsx_file(temp_file)
            assert result['key_column'] == 'key'
            assert result['languages'] == ['en', 'de']
        finally:
            os.unlink(temp_file)
    
    def test_extract_translatable_strings(self):
        """Test extracting translatable strings for a specific language."""
        xlsx_content = {
            'translations': {
                'app.title': {
                    'en': 'My Application',
                    'de': 'Meine Anwendung',
                    'fr': 'Mon Application'
                },
                'welcome.message': {
                    'en': 'Welcome!',
                    'de': 'Willkommen!',
                    'fr': 'Bienvenue!'
                }
            }
        }
        
        result = extract_translatable_strings(xlsx_content, 'en')
        expected = {
            'app.title': 'My Application',
            'welcome.message': 'Welcome!'
        }
        assert result == expected
    
    def test_create_xlsx_from_translations(self):
        """Test creating XLSX content from translations."""
        translations = {
            "appTitle": "My App",
            "welcomeMessage": "Welcome!"
        }
        languages = ['en', 'de']
        
        result = create_xlsx_from_translations(translations, languages)
        
        assert result['key_column'] == 'key'
        assert result['languages'] == ['en', 'de']
        assert 'appTitle' in result['translations']
        assert result['translations']['appTitle']['en'] == 'My App'
    
    def test_add_language_to_xlsx(self):
        """Test adding a new language to existing XLSX content."""
        xlsx_content = {
            'languages': ['en'],
            'translations': {
                'app.title': {'en': 'My Application'}
            }
        }
        
        new_translations = {'app.title': 'Meine Anwendung'}
        result = add_language_to_xlsx(xlsx_content, 'de', new_translations)
        
        assert 'de' in result['languages']
        assert result['translations']['app.title']['de'] == 'Meine Anwendung'
    
    def test_get_xlsx_language_codes(self):
        """Test getting language codes from XLSX content."""
        xlsx_content = {
            'languages': ['en', 'de', 'fr']
        }
        
        result = get_xlsx_language_codes(xlsx_content)
        assert result == ['en', 'de', 'fr']
    
    def test_is_valid_xlsx_file(self):
        """Test XLSX file validation."""
        # Valid XLSX file
        xlsx_content = {
            'key_column': 'key',
            'languages': ['en', 'de'],
            'translations': {
                'app.title': {
                    'en': 'My Application',
                    'de': 'Meine Anwendung'
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xlsx_file(temp_file, xlsx_content)
            assert is_valid_xlsx_file(temp_file) is True
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_xlsx_file("nonexistent.xlsx") is False
    
    def test_get_xlsx_language_code(self):
        """Test getting language code from XLSX file (should return None for multi-language files)."""
        assert get_xlsx_language_code("strings.xlsx") is None
    
    def test_is_glossary_xlsx(self):
        """Test detecting glossary XLSX files."""
        # Translation XLSX
        xlsx_content = {
            'key_column': 'key',
            'languages': ['en', 'de'],
            'translations': {
                'app.title': {
                    'en': 'My Application',
                    'de': 'Meine Anwendung'
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xlsx_file(temp_file, xlsx_content)
            assert is_glossary_xlsx(temp_file) is False
        finally:
            os.unlink(temp_file)
        
        # Glossary XLSX (would need to be created with Record ID column)
        # This test would require creating a proper glossary XLSX file
        # For now, we'll just test the function exists
        assert callable(is_glossary_xlsx)
