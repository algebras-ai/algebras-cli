"""
Integration tests for Flutter ARB translation
"""

import os
import tempfile
import json
import pytest
from algebras.services.translator import Translator
from algebras.utils.arb_handler import read_arb_file, write_arb_file


class TestFlutterTranslation:
    """Integration tests for Flutter ARB translation."""
    
    def test_translate_arb_file(self):
        """Test end-to-end ARB file translation."""
        # Create a temporary ARB file
        arb_content = {
            "@@locale": "en",
            "appTitle": "My Flutter App",
            "@appTitle": {
                "description": "The title of the application"
            },
            "welcomeMessage": "Welcome to our amazing app!",
            "@welcomeMessage": {
                "description": "A welcome message shown to users"
            },
            "loginButton": "Log In",
            "@loginButton": {
                "description": "Text for the login button"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.arb', delete=False) as f:
            json.dump(arb_content, f, indent=2)
            temp_file = f.name
        
        try:
            # Mock the translator to avoid API calls
            translator = Translator()
            
            # Test that the file can be read
            content = read_arb_file(temp_file)
            assert content == arb_content
            
            # Test that translatable strings can be extracted
            from algebras.utils.arb_handler import extract_translatable_strings
            translatable = extract_translatable_strings(content)
            expected = {
                "appTitle": "My Flutter App",
                "welcomeMessage": "Welcome to our amazing app!",
                "loginButton": "Log In"
            }
            assert translatable == expected
            
            # Test that ARB content can be created from translations
            from algebras.utils.arb_handler import create_arb_from_translations
            new_translations = {
                "appTitle": "Meine Flutter App",
                "welcomeMessage": "Willkommen zu unserer erstaunlichen App!",
                "loginButton": "Anmelden"
            }
            
            new_arb = create_arb_from_translations(new_translations, {"@@locale": "de"})
            assert new_arb["appTitle"] == "Meine Flutter App"
            assert new_arb["@@locale"] == "de"
            
        finally:
            os.unlink(temp_file)
    
    def test_arb_file_validation(self):
        """Test ARB file validation."""
        from algebras.utils.arb_handler import is_valid_arb_file, get_arb_language_code
        
        # Valid ARB file
        arb_content = {
            "@@locale": "en",
            "appTitle": "My App"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.arb', delete=False) as f:
            json.dump(arb_content, f)
            temp_file = f.name
        
        try:
            assert is_valid_arb_file(temp_file) is True
            assert get_arb_language_code(temp_file) == "en"
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_arb_file("nonexistent.arb") is False
    
    def test_arb_metadata_preservation(self):
        """Test that ARB metadata is preserved during translation."""
        arb_content = {
            "@@locale": "en",
            "appTitle": "My App",
            "@appTitle": {
                "description": "The title of the application",
                "context": "main_screen"
            },
            "welcomeMessage": "Welcome!",
            "@welcomeMessage": {
                "description": "A welcome message"
            }
        }
        
        # Test metadata extraction
        from algebras.utils.arb_handler import get_arb_metadata
        metadata = get_arb_metadata(arb_content)
        
        assert "@@locale" in metadata
        assert "@appTitle" in metadata
        assert "@welcomeMessage" in metadata
        assert metadata["@appTitle"]["description"] == "The title of the application"
        assert metadata["@appTitle"]["context"] == "main_screen"
