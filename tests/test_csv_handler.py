"""
Tests for CSV handler
"""

import os
import tempfile
import pytest
from algebras.utils.csv_handler import (
    read_csv_file, write_csv_file, extract_translatable_strings,
    create_csv_from_translations, add_language_to_csv, get_csv_language_codes,
    is_valid_csv_file, get_csv_language_code, is_glossary_csv
)


class TestCSVHandler:
    """Test cases for CSV handler functions."""
    
    def test_read_csv_file(self):
        """Test reading CSV files."""
        csv_content = """key,en,de,fr
app.title,My Application,Meine Anwendung,Mon Application
welcome.message,Welcome!,Willkommen!,Bienvenue!
login.button,Log In,Anmelden,Se connecter
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            result = read_csv_file(temp_file)
            assert result['key_column'] == 'key'
            assert result['languages'] == ['en', 'de', 'fr']
            assert 'translations' in result
            assert 'app.title' in result['translations']
            assert result['translations']['app.title']['en'] == 'My Application'
        finally:
            os.unlink(temp_file)
    
    def test_read_csv_file_not_found(self):
        """Test reading non-existent CSV file."""
        with pytest.raises(FileNotFoundError):
            read_csv_file("nonexistent.csv")
    
    def test_read_csv_file_invalid_format(self):
        """Test reading CSV file with invalid format."""
        csv_content = "key\n"  # Only one column
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError):
                read_csv_file(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_write_csv_file(self):
        """Test writing CSV files."""
        csv_content = {
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
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            temp_file = f.name
        
        try:
            write_csv_file(temp_file, csv_content)
            
            # Read it back to verify
            result = read_csv_file(temp_file)
            assert result['key_column'] == 'key'
            assert result['languages'] == ['en', 'de', 'fr']
        finally:
            os.unlink(temp_file)
    
    def test_extract_translatable_strings(self):
        """Test extracting translatable strings for a specific language."""
        csv_content = {
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
        
        result = extract_translatable_strings(csv_content, 'en')
        expected = {
            'app.title': 'My Application',
            'welcome.message': 'Welcome!'
        }
        assert result == expected
    
    def test_create_csv_from_translations(self):
        """Test creating CSV content from translations."""
        translations = {
            "appTitle": "My App",
            "welcomeMessage": "Welcome!"
        }
        languages = ['en', 'de']
        
        result = create_csv_from_translations(translations, languages)
        
        assert result['key_column'] == 'key'
        assert result['languages'] == ['en', 'de']
        assert 'appTitle' in result['translations']
        assert result['translations']['appTitle']['en'] == 'My App'
    
    def test_add_language_to_csv(self):
        """Test adding a new language to existing CSV content."""
        csv_content = {
            'languages': ['en'],
            'translations': {
                'app.title': {'en': 'My Application'}
            }
        }
        
        new_translations = {'app.title': 'Meine Anwendung'}
        result = add_language_to_csv(csv_content, 'de', new_translations)
        
        assert 'de' in result['languages']
        assert result['translations']['app.title']['de'] == 'Meine Anwendung'
    
    def test_get_csv_language_codes(self):
        """Test getting language codes from CSV content."""
        csv_content = {
            'languages': ['en', 'de', 'fr']
        }
        
        result = get_csv_language_codes(csv_content)
        assert result == ['en', 'de', 'fr']
    
    def test_is_valid_csv_file(self):
        """Test CSV file validation."""
        # Valid CSV file
        csv_content = "key,en,de\napp.title,My App,Meine App"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            assert is_valid_csv_file(temp_file) is True
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_csv_file("nonexistent.csv") is False
    
    def test_get_csv_language_code(self):
        """Test getting language code from CSV file (should return None for multi-language files)."""
        assert get_csv_language_code("strings.csv") is None
    
    def test_is_glossary_csv(self):
        """Test detecting glossary CSV files."""
        # Translation CSV
        csv_content = "key,en,de\napp.title,My App,Meine App"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            assert is_glossary_csv(temp_file) is False
        finally:
            os.unlink(temp_file)
        
        # Glossary CSV
        csv_content = "Record ID,en,de\n1,term1,term1_de"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            assert is_glossary_csv(temp_file) is True
        finally:
            os.unlink(temp_file)
