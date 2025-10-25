"""
Tests for Properties handler
"""

import os
import tempfile
import pytest
from algebras.utils.properties_handler import (
    read_properties_file, write_properties_file, extract_translatable_strings,
    create_properties_from_translations, is_valid_properties_file, get_properties_language_code
)


class TestPropertiesHandler:
    """Test cases for Properties handler functions."""
    
    def test_read_properties_file(self):
        """Test reading Properties files."""
        properties_content = """# English messages
app.title=My Application
welcome.message=Welcome to our amazing application!
login.button=Log In
error.message=Something went wrong. Please try again.
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            result = read_properties_file(temp_file)
            expected = {
                "app.title": "My Application",
                "welcome.message": "Welcome to our amazing application!",
                "login.button": "Log In",
                "error.message": "Something went wrong. Please try again."
            }
            assert result == expected
        finally:
            os.unlink(temp_file)
    
    def test_read_properties_file_not_found(self):
        """Test reading non-existent Properties file."""
        with pytest.raises(FileNotFoundError):
            read_properties_file("nonexistent.properties")
    
    def test_read_properties_file_with_unicode(self):
        """Test reading Properties files with Unicode escapes."""
        properties_content = """app.title=My Application
welcome.message=Welcome to our amazing application!
special.chars=Hello \\u00E4\\u00F6\\u00FC
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            result = read_properties_file(temp_file)
            assert result["special.chars"] == "Hello äöü"
        finally:
            os.unlink(temp_file)
    
    def test_write_properties_file(self):
        """Test writing Properties files."""
        properties_content = {
            "app.title": "My Application",
            "welcome.message": "Welcome to our amazing application!",
            "login.button": "Log In"
        }
        
        with tempfile.NamedTemporaryFile(suffix='.properties', delete=False) as f:
            temp_file = f.name
        
        try:
            write_properties_file(temp_file, properties_content, "English messages")
            
            # Read it back to verify
            result = read_properties_file(temp_file)
            assert result == properties_content
        finally:
            os.unlink(temp_file)
    
    def test_write_properties_file_invalid_content(self):
        """Test writing invalid Properties content."""
        with tempfile.NamedTemporaryFile(suffix='.properties', delete=False) as f:
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError):
                write_properties_file(temp_file, "not a dict")
        finally:
            os.unlink(temp_file)
    
    def test_extract_translatable_strings(self):
        """Test extracting translatable strings from Properties content."""
        properties_content = {
            "app.title": "My Application",
            "welcome.message": "Welcome!",
            "login.button": "Log In"
        }
        
        result = extract_translatable_strings(properties_content)
        assert result == properties_content
    
    def test_create_properties_from_translations(self):
        """Test creating Properties content from translations."""
        translations = {
            "appTitle": "My App",
            "welcomeMessage": "Welcome!"
        }
        
        result = create_properties_from_translations(translations)
        assert result == translations
    
    def test_is_valid_properties_file(self):
        """Test Properties file validation."""
        # Valid Properties file
        properties_content = "app.title=My Application\nwelcome.message=Welcome!"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            f.write(properties_content)
            temp_file = f.name
        
        try:
            assert is_valid_properties_file(temp_file) is True
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_properties_file("nonexistent.properties") is False
    
    def test_get_properties_language_code_from_filename(self):
        """Test extracting language code from Properties filename."""
        assert get_properties_language_code("messages_en.properties") == "en"
        assert get_properties_language_code("messages_de.properties") == "de"
        assert get_properties_language_code("messages_en_US.properties") == "en_US"
        assert get_properties_language_code("messages.properties") is None
