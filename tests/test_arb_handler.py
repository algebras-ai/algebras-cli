"""
Tests for ARB handler
"""

import os
import tempfile
import json
import pytest
from algebras.utils.arb_handler import (
    read_arb_file, write_arb_file, extract_translatable_strings,
    create_arb_from_translations, get_arb_metadata, is_valid_arb_file,
    get_arb_language_code
)


class TestARBHandler:
    """Test cases for ARB handler functions."""
    
    def test_read_arb_file(self):
        """Test reading ARB files."""
        # Create a temporary ARB file
        arb_content = {
            "@@locale": "en",
            "appTitle": "My App",
            "@appTitle": {
                "description": "The title of the application"
            },
            "welcomeMessage": "Welcome!",
            "@welcomeMessage": {
                "description": "A welcome message"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.arb', delete=False) as f:
            json.dump(arb_content, f, indent=2)
            temp_file = f.name
        
        try:
            result = read_arb_file(temp_file)
            assert result == arb_content
        finally:
            os.unlink(temp_file)
    
    def test_read_arb_file_not_found(self):
        """Test reading non-existent ARB file."""
        with pytest.raises(FileNotFoundError):
            read_arb_file("nonexistent.arb")
    
    def test_read_arb_file_invalid_json(self):
        """Test reading invalid JSON ARB file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.arb', delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError):
                read_arb_file(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_write_arb_file(self):
        """Test writing ARB files."""
        arb_content = {
            "@@locale": "en",
            "appTitle": "My App",
            "@appTitle": {
                "description": "The title of the application"
            }
        }
        
        with tempfile.NamedTemporaryFile(suffix='.arb', delete=False) as f:
            temp_file = f.name
        
        try:
            write_arb_file(temp_file, arb_content)
            
            # Read it back to verify
            result = read_arb_file(temp_file)
            assert result == arb_content
        finally:
            os.unlink(temp_file)
    
    def test_write_arb_file_invalid_content(self):
        """Test writing invalid ARB content."""
        with tempfile.NamedTemporaryFile(suffix='.arb', delete=False) as f:
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError):
                write_arb_file(temp_file, "not a dict")
        finally:
            os.unlink(temp_file)
    
    def test_extract_translatable_strings(self):
        """Test extracting translatable strings from ARB content."""
        arb_content = {
            "@@locale": "en",
            "appTitle": "My App",
            "@appTitle": {
                "description": "The title of the application"
            },
            "welcomeMessage": "Welcome!",
            "@welcomeMessage": {
                "description": "A welcome message"
            },
            "nested": {
                "key": "value"
            }
        }
        
        result = extract_translatable_strings(arb_content)
        expected = {
            "appTitle": "My App",
            "welcomeMessage": "Welcome!"
        }
        assert result == expected
    
    def test_create_arb_from_translations(self):
        """Test creating ARB content from translations."""
        translations = {
            "appTitle": "My App",
            "welcomeMessage": "Welcome!"
        }
        metadata = {
            "@@locale": "en",
            "@appTitle": {
                "description": "The title of the application"
            }
        }
        
        result = create_arb_from_translations(translations, metadata)
        
        assert result["appTitle"] == "My App"
        assert result["welcomeMessage"] == "Welcome!"
        assert result["@@locale"] == "en"
        assert "@appTitle" in result
    
    def test_get_arb_metadata(self):
        """Test extracting metadata from ARB content."""
        arb_content = {
            "@@locale": "en",
            "appTitle": "My App",
            "@appTitle": {
                "description": "The title of the application"
            },
            "welcomeMessage": "Welcome!"
        }
        
        result = get_arb_metadata(arb_content)
        expected = {
            "@@locale": "en",
            "@appTitle": {
                "description": "The title of the application"
            }
        }
        assert result == expected
    
    def test_is_valid_arb_file(self):
        """Test ARB file validation."""
        # Valid ARB file
        arb_content = {"appTitle": "My App"}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.arb', delete=False) as f:
            json.dump(arb_content, f)
            temp_file = f.name
        
        try:
            assert is_valid_arb_file(temp_file) is True
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_arb_file("nonexistent.arb") is False
    
    def test_get_arb_language_code_from_filename(self):
        """Test extracting language code from ARB filename."""
        assert get_arb_language_code("app_en.arb") == "en"
        assert get_arb_language_code("app_de.arb") == "de"
        assert get_arb_language_code("app_en_US.arb") == "en_US"
        assert get_arb_language_code("app.arb") is None
    
    def test_get_arb_language_code_from_content(self):
        """Test extracting language code from ARB content."""
        arb_content = {
            "@@locale": "en",
            "@locale": {
                "locale": "en_US"
            },
            "appTitle": "My App"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.arb', delete=False) as f:
            json.dump(arb_content, f)
            temp_file = f.name
        
        try:
            result = get_arb_language_code(temp_file)
            assert result == "en_US"
        finally:
            os.unlink(temp_file)
