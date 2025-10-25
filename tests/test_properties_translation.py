"""
Integration tests for Java Properties translation
"""

import os
import tempfile
import pytest
from algebras.utils.properties_handler import (
    read_properties_file, write_properties_file, extract_translatable_strings,
    create_properties_from_translations, is_valid_properties_file, get_properties_language_code
)


class TestPropertiesTranslation:
    """Integration tests for Java Properties translation."""
    
    def test_translate_properties_file(self):
        """Test end-to-end Properties file translation."""
        # Create a temporary Properties file
        properties_content = """# English messages for Java application
app.title=My Java Application
welcome.message=Welcome to our amazing Java application!
login.button=Log In
register.button=Register
error.message=Something went wrong. Please try again.
settings.title=Settings
language.selection=Select Language
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            # Test that the file can be read
            content = read_properties_file(temp_file)
            expected = {
                "app.title": "My Java Application",
                "welcome.message": "Welcome to our amazing Java application!",
                "login.button": "Log In",
                "register.button": "Register",
                "error.message": "Something went wrong. Please try again.",
                "settings.title": "Settings",
                "language.selection": "Select Language"
            }
            assert content == expected
            
            # Test that translatable strings can be extracted
            translatable = extract_translatable_strings(content)
            assert translatable == expected
            
            # Test that Properties content can be created from translations
            new_translations = {
                "app.title": "Meine Java-Anwendung",
                "welcome.message": "Willkommen zu unserer erstaunlichen Java-Anwendung!",
                "login.button": "Anmelden"
            }
            
            new_properties = create_properties_from_translations(new_translations)
            assert new_properties == new_translations
            
        finally:
            os.unlink(temp_file)
    
    def test_properties_file_validation(self):
        """Test Properties file validation."""
        # Valid Properties file
        properties_content = "app.title=My Application\nwelcome.message=Welcome!"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            assert is_valid_properties_file(temp_file) is True
            assert get_properties_language_code(temp_file) is None  # No language in filename
        finally:
            os.unlink(temp_file)
        
        # Test with language in filename
        with tempfile.NamedTemporaryFile(mode='w', suffix='_en.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            assert is_valid_properties_file(temp_file) is True
            assert get_properties_language_code(temp_file) == "en"
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_properties_file("nonexistent.properties") is False
    
    def test_properties_unicode_handling(self):
        """Test Properties file Unicode handling."""
        properties_content = """app.title=My Application
welcome.message=Welcome to our amazing application!
special.chars=Hello \\u00E4\\u00F6\\u00FC
unicode.text=Unicode: \\u0048\\u0065\\u006C\\u006C\\u006F
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            content = read_properties_file(temp_file)
            assert content["special.chars"] == "Hello äöü"
            assert content["unicode.text"] == "Unicode: Hello"
        finally:
            os.unlink(temp_file)
    
    def test_properties_escaping(self):
        """Test Properties file escaping."""
        properties_content = {
            "app.title": "My Application",
            "welcome.message": "Welcome to our amazing application!",
            "special.key": "Value with = and : and spaces",
            "quoted.value": "Value with \"quotes\" and 'apostrophes'"
        }
        
        with tempfile.NamedTemporaryFile(suffix='.properties', delete=False) as f:
            temp_file = f.name
        
        try:
            write_properties_file(temp_file, properties_content, "Test properties")
            
            # Read it back to verify escaping worked
            result = read_properties_file(temp_file)
            assert result == properties_content
        finally:
            os.unlink(temp_file)
