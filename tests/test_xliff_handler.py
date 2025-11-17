"""
Tests for XLIFF handler
"""

import os
import tempfile
import xml.etree.ElementTree as ET
import pytest
from algebras.utils.xliff_handler import (
    read_xliff_file, write_xliff_file, extract_translatable_strings,
    create_xliff_from_translations, is_valid_xliff_file, get_xliff_language_code
)


class TestXLIFFHandler:
    """Test cases for XLIFF handler functions."""
    
    def test_read_xliff_file(self):
        """Test reading XLIFF files."""
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="en" datatype="plaintext">
    <body>
      <trans-unit id="app.title">
        <source>My App</source>
        <target>My App</target>
      </trans-unit>
      <trans-unit id="welcome.message">
        <source>Welcome!</source>
        <target>Welcome!</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            assert 'files' in result
            assert len(result['files']) == 1
            assert 'trans-units' in result['files'][0]
            assert len(result['files'][0]['trans-units']) == 2
        finally:
            os.unlink(temp_file)
    
    def test_read_xliff_file_not_found(self):
        """Test reading non-existent XLIFF file."""
        with pytest.raises(FileNotFoundError):
            read_xliff_file("nonexistent.xlf")
    
    def test_read_xliff_file_invalid_xml(self):
        """Test reading invalid XML XLIFF file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write("invalid xml content")
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError):
                read_xliff_file(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_write_xliff_file(self):
        """Test writing XLIFF files."""
        xliff_content = {
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'en',
                'trans-units': [
                    {
                        'id': 'app.title',
                        'source': 'My App',
                        'target': 'My App'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "en")
            
            # Read it back to verify
            result = read_xliff_file(temp_file)
            assert 'files' in result
        finally:
            os.unlink(temp_file)
    
    def test_extract_translatable_strings(self):
        """Test extracting translatable strings from XLIFF content."""
        xliff_content = {
            'files': [{
                'trans-units': [
                    {
                        'id': 'app.title',
                        'source': 'My App',
                        'target': 'My App'
                    },
                    {
                        'id': 'welcome.message',
                        'source': 'Welcome!',
                        'target': 'Welcome!'
                    }
                ]
            }]
        }
        
        result = extract_translatable_strings(xliff_content)
        expected = {
            'app.title': 'My App',
            'welcome.message': 'Welcome!'
        }
        assert result == expected
    
    def test_create_xliff_from_translations(self):
        """Test creating XLIFF content from translations."""
        translations = {
            "appTitle": "My App",
            "welcomeMessage": "Welcome!"
        }
        
        result = create_xliff_from_translations(translations, "en", "en")
        
        assert 'files' in result
        assert len(result['files']) == 1
        assert result['files'][0]['source-language'] == 'en'
        assert result['files'][0]['target-language'] == 'en'
        assert len(result['files'][0]['trans-units']) == 2
    
    def test_is_valid_xliff_file(self):
        """Test XLIFF file validation."""
        # Valid XLIFF file
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="en" datatype="plaintext">
    <body>
      <trans-unit id="app.title">
        <source>My App</source>
        <target>My App</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            assert is_valid_xliff_file(temp_file) is True
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_xliff_file("nonexistent.xlf") is False
    
    def test_get_xliff_language_code_from_filename(self):
        """Test extracting language code from XLIFF filename."""
        assert get_xliff_language_code("messages.en.xlf") == "en"
        assert get_xliff_language_code("messages.de.xlf") == "de"
        assert get_xliff_language_code("messages.en_US.xlf") == "en_US"
        assert get_xliff_language_code("messages.xlf") is None
    
    def test_get_xliff_language_code_from_content(self):
        """Test extracting language code from XLIFF content."""
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="de" datatype="plaintext">
    <body>
      <trans-unit id="app.title">
        <source>My App</source>
        <target>Meine App</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = get_xliff_language_code(temp_file)
            assert result == "de"
        finally:
            os.unlink(temp_file)

    def test_read_xliff_file_2_0(self):
        """Test reading XLIFF 2.0 files."""
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en-US">
  <file id="ngi18n" original="ng.template">
    <unit id="6439365426343089851">
      <segment>
        <source>General</source>
      </segment>
    </unit>
    <unit id="6812930637022637485">
      <segment>
        <source>Display</source>
        <target>Affichage</target>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            assert 'files' in result
            assert result['version'] == '2.0'
            assert len(result['files']) == 1
            assert 'trans-units' in result['files'][0]
            assert len(result['files'][0]['trans-units']) == 2
            assert result['files'][0]['trans-units'][0]['id'] == '6439365426343089851'
            assert result['files'][0]['trans-units'][0]['source'] == 'General'
            assert result['files'][0]['trans-units'][1]['id'] == '6812930637022637485'
            assert result['files'][0]['trans-units'][1]['source'] == 'Display'
            assert result['files'][0]['trans-units'][1]['target'] == 'Affichage'
        finally:
            os.unlink(temp_file)

    def test_extract_translatable_strings_xliff_2_0(self):
        """Test extracting translatable strings from XLIFF 2.0 content."""
        xliff_content = {
            'version': '2.0',
            'files': [{
                'trans-units': [
                    {
                        'id': '6439365426343089851',
                        'source': 'General',
                        'target': ''
                    },
                    {
                        'id': '6812930637022637485',
                        'source': 'Display',
                        'target': 'Affichage'
                    }
                ]
            }]
        }
        
        result = extract_translatable_strings(xliff_content)
        expected = {
            '6439365426343089851': 'General',
            '6812930637022637485': 'Display'
        }
        assert result == expected

    def test_is_valid_xliff_file_2_0(self):
        """Test XLIFF 2.0 file validation."""
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en-US">
  <file id="ngi18n" original="ng.template">
    <unit id="6439365426343089851">
      <segment>
        <source>General</source>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            assert is_valid_xliff_file(temp_file) is True
        finally:
            os.unlink(temp_file)
