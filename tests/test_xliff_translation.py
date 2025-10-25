"""
Integration tests for XLIFF translation
"""

import os
import tempfile
import pytest
from algebras.utils.xliff_handler import read_xliff_file, write_xliff_file, extract_translatable_strings


class TestXLIFFTranslation:
    """Integration tests for XLIFF translation."""
    
    def test_translate_xliff_file(self):
        """Test end-to-end XLIFF file translation."""
        # Create a temporary XLIFF file
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="en" datatype="plaintext">
    <body>
      <trans-unit id="app.title">
        <source>My Angular App</source>
        <target>My Angular App</target>
      </trans-unit>
      <trans-unit id="welcome.message">
        <source>Welcome to our amazing Angular application!</source>
        <target>Welcome to our amazing Angular application!</target>
      </trans-unit>
      <trans-unit id="login.button">
        <source>Log In</source>
        <target>Log In</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            # Test that the file can be read
            content = read_xliff_file(temp_file)
            assert 'files' in content
            assert len(content['files']) == 1
            assert 'trans-units' in content['files'][0]
            assert len(content['files'][0]['trans-units']) == 3
            
            # Test that translatable strings can be extracted
            translatable = extract_translatable_strings(content)
            expected = {
                "app.title": "My Angular App",
                "welcome.message": "Welcome to our amazing Angular application!",
                "login.button": "Log In"
            }
            assert translatable == expected
            
            # Test that XLIFF content can be created from translations
            from algebras.utils.xliff_handler import create_xliff_from_translations
            new_translations = {
                "app.title": "Meine Angular App",
                "welcome.message": "Willkommen zu unserer erstaunlichen Angular-Anwendung!",
                "login.button": "Anmelden"
            }
            
            new_xliff = create_xliff_from_translations(new_translations, "en", "de")
            assert 'files' in new_xliff
            assert new_xliff['files'][0]['target-language'] == 'de'
            
        finally:
            os.unlink(temp_file)
    
    def test_xliff_file_validation(self):
        """Test XLIFF file validation."""
        from algebras.utils.xliff_handler import is_valid_xliff_file, get_xliff_language_code
        
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
            assert get_xliff_language_code(temp_file) == "en"
        finally:
            os.unlink(temp_file)
        
        # Invalid file
        assert is_valid_xliff_file("nonexistent.xlf") is False
    
    def test_xliff_structure_preservation(self):
        """Test that XLIFF structure is preserved during translation."""
        xliff_content = {
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'en',
                'datatype': 'plaintext',
                'trans-units': [
                    {
                        'id': 'app.title',
                        'source': 'My App',
                        'target': 'My App'
                    }
                ]
            }]
        }
        
        # Test writing and reading back
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "en")
            result = read_xliff_file(temp_file)
            
            assert 'files' in result
            assert len(result['files']) == 1
            assert result['files'][0]['original'] == 'messages'
            assert result['files'][0]['source-language'] == 'en'
            assert result['files'][0]['target-language'] == 'en'
        finally:
            os.unlink(temp_file)
