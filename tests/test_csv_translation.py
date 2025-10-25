"""
Integration tests for CSV translation
"""

import os
import tempfile
import pytest
from algebras.utils.csv_handler import (
    read_csv_file, write_csv_file, extract_translatable_strings,
    create_csv_from_translations, add_language_to_csv, get_csv_language_codes,
    is_valid_csv_file, is_glossary_csv
)


class TestCSVTranslation:
    """Integration tests for CSV translation."""
    
    def test_translate_csv_file(self):
        """Test end-to-end CSV file translation."""
        # Create a temporary CSV file
        csv_content = """key,en,de,fr
app.title,My Application,Meine Anwendung,Mon Application
welcome.message,Welcome to our amazing application!,Willkommen zu unserer erstaunlichen Anwendung!,Bienvenue dans notre application incroyable!
login.button,Log In,Anmelden,Se connecter
register.button,Register,Registrieren,S'inscrire
error.message,Something went wrong. Please try again.,Etwas ist schief gelaufen. Bitte versuchen Sie es erneut.,Quelque chose s'est mal passé. Veuillez réessayer.
settings.title,Settings,Einstellungen,Paramètres
language.selection,Select Language,Sprache auswählen,Sélectionner la langue
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            # Test that the file can be read
            content = read_csv_file(temp_file)
            assert content['key_column'] == 'key'
            assert content['languages'] == ['en', 'de', 'fr']
            assert 'translations' in content
            assert 'app.title' in content['translations']
            assert content['translations']['app.title']['en'] == 'My Application'
            assert content['translations']['app.title']['de'] == 'Meine Anwendung'
            assert content['translations']['app.title']['fr'] == 'Mon Application'
            
            # Test that translatable strings can be extracted for a specific language
            en_strings = extract_translatable_strings(content, 'en')
            expected_en = {
                'app.title': 'My Application',
                'welcome.message': 'Welcome to our amazing application!',
                'login.button': 'Log In',
                'register.button': 'Register',
                'error.message': 'Something went wrong. Please try again.',
                'settings.title': 'Settings',
                'language.selection': 'Select Language'
            }
            assert en_strings == expected_en
            
            # Test that CSV content can be created from translations
            new_translations = {
                "app.title": "My New Application",
                "welcome.message": "Welcome to our new application!"
            }
            languages = ['en', 'es']
            
            new_csv = create_csv_from_translations(new_translations, languages)
            assert new_csv['key_column'] == 'key'
            assert new_csv['languages'] == ['en', 'es']
            assert 'app.title' in new_csv['translations']
            assert new_csv['translations']['app.title']['en'] == 'My New Application'
            
        finally:
            os.unlink(temp_file)
    
    def test_csv_file_validation(self):
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
    
    def test_glossary_vs_translation_csv(self):
        """Test distinction between glossary and translation CSV files."""
        # Translation CSV
        translation_csv = "key,en,de\napp.title,My App,Meine App"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(translation_csv)
            temp_file = f.name
        
        try:
            assert is_glossary_csv(temp_file) is False
        finally:
            os.unlink(temp_file)
        
        # Glossary CSV
        glossary_csv = "Record ID,en,de\n1,term1,term1_de\n2,term2,term2_de"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(glossary_csv)
            temp_file = f.name
        
        try:
            assert is_glossary_csv(temp_file) is True
        finally:
            os.unlink(temp_file)
    
    def test_add_language_to_csv(self):
        """Test adding a new language to existing CSV content."""
        csv_content = {
            'key_column': 'key',
            'languages': ['en'],
            'translations': {
                'app.title': {'en': 'My Application'},
                'welcome.message': {'en': 'Welcome!'}
            }
        }
        
        # Add German translations
        new_translations = {
            'app.title': 'Meine Anwendung',
            'welcome.message': 'Willkommen!'
        }
        
        result = add_language_to_csv(csv_content, 'de', new_translations)
        
        assert 'de' in result['languages']
        assert result['translations']['app.title']['de'] == 'Meine Anwendung'
        assert result['translations']['welcome.message']['de'] == 'Willkommen!'
        # Original English should still be there
        assert result['translations']['app.title']['en'] == 'My Application'
    
    def test_csv_language_codes(self):
        """Test getting language codes from CSV content."""
        csv_content = {
            'languages': ['en', 'de', 'fr', 'es']
        }
        
        result = get_csv_language_codes(csv_content)
        assert result == ['en', 'de', 'fr', 'es']
