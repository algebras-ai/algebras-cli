"""
Tests for XLIFF handler
"""

import os
import tempfile
import xml.etree.ElementTree as ET
import pytest
from algebras.utils.xliff_handler import (
    read_xliff_file, write_xliff_file, extract_translatable_strings,
    create_xliff_from_translations, is_valid_xliff_file, get_xliff_language_code,
    update_xliff_targets
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            assert is_valid_xliff_file(temp_file) is True
        finally:
            os.unlink(temp_file)

    def test_update_xliff_targets(self):
        """Test updating XLIFF targets while preserving source text."""
        xliff_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'vi',
                'trans-units': [
                    {
                        'id': '1009606887419612072',
                        'source': 'Patient management',
                        'target': ''
                    },
                    {
                        'id': '6439365426343089851',
                        'source': 'General',
                        'target': 'Tổng quát'
                    }
                ]
            }]
        }
        
        translations = {
            '1009606887419612072': 'Quản lý bệnh nhân',
            '6439365426343089851': 'Tổng quát mới'  # Update existing translation
        }
        
        result = update_xliff_targets(xliff_content, translations)
        
        # Verify source text is preserved
        assert result['files'][0]['trans-units'][0]['source'] == 'Patient management'
        assert result['files'][0]['trans-units'][1]['source'] == 'General'
        
        # Verify target text is updated
        assert result['files'][0]['trans-units'][0]['target'] == 'Quản lý bệnh nhân'
        assert result['files'][0]['trans-units'][1]['target'] == 'Tổng quát mới'
        
        # Verify structure is preserved
        assert result['version'] == '2.0'
        assert result['files'][0]['original'] == 'messages'
        assert result['files'][0]['source-language'] == 'en'
        assert result['files'][0]['target-language'] == 'vi'

    def test_update_xliff_targets_preserves_untranslated(self):
        """Test that update_xliff_targets preserves units not in translations."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Source 1',
                        'target': 'Target 1'
                    },
                    {
                        'id': 'key2',
                        'source': 'Source 2',
                        'target': ''
                    },
                    {
                        'id': 'key3',
                        'source': 'Source 3',
                        'target': 'Target 3'
                    }
                ]
            }]
        }
        
        translations = {
            'key2': 'New Target 2'
        }
        
        result = update_xliff_targets(xliff_content, translations)
        
        # Verify all units are preserved
        assert len(result['files'][0]['trans-units']) == 3
        
        # Verify key1 is unchanged
        assert result['files'][0]['trans-units'][0]['source'] == 'Source 1'
        assert result['files'][0]['trans-units'][0]['target'] == 'Target 1'
        
        # Verify key2 is updated
        assert result['files'][0]['trans-units'][1]['source'] == 'Source 2'
        assert result['files'][0]['trans-units'][1]['target'] == 'New Target 2'
        
        # Verify key3 is unchanged
        assert result['files'][0]['trans-units'][2]['source'] == 'Source 3'
        assert result['files'][0]['trans-units'][2]['target'] == 'Target 3'

    def test_write_xliff_file_preserves_source_text(self):
        """Test that write_xliff_file preserves source text when writing."""
        xliff_content = {
            'version': '2.0',
            'files': [{
                'original': 'ng.template',
                'id': 'ngi18n',
                'source-language': 'en',
                'target-language': 'vi',
                'trans-units': [
                    {
                        'id': '1009606887419612072',
                        'source': 'Patient management',
                        'target': 'Quản lý bệnh nhân'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "vi")
            
            # Read it back and verify
            result = read_xliff_file(temp_file)
            assert result['version'] == '2.0'
            assert len(result['files']) == 1
            assert result['files'][0]['trans-units'][0]['source'] == 'Patient management'
            assert result['files'][0]['trans-units'][0]['target'] == 'Quản lý bệnh nhân'
        finally:
            os.unlink(temp_file)

    def test_write_xliff_file_preserves_version_2_0(self):
        """Test that write_xliff_file preserves XLIFF 2.0 format."""
        xliff_content = {
            'version': '2.0',
            'files': [{
                'original': 'ng.template',
                'id': 'ngi18n',
                'source-language': 'en-US',
                'target-language': 'vi',
                'trans-units': [
                    {
                        'id': '6439365426343089851',
                        'source': 'General',
                        'target': 'Tổng quát'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en-US", "vi")
            
            # Read it back and verify it's still XLIFF 2.0
            result = read_xliff_file(temp_file)
            assert result['version'] == '2.0'
            assert result['files'][0]['source-language'] == 'en-US'
            
            # Verify the XML structure is XLIFF 2.0 (unit with segment)
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'version="2.0"' in content
                assert 'xmlns="urn:oasis:names:tc:xliff:document:2.0"' in content
                assert '<unit id=' in content
                assert '<segment>' in content
        finally:
            os.unlink(temp_file)

    def test_write_xliff_file_preserves_version_1_2(self):
        """Test that write_xliff_file preserves XLIFF 1.2 format."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'datatype': 'plaintext',
                'trans-units': [
                    {
                        'id': 'app.title',
                        'source': 'My App',
                        'target': 'Mon App'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "fr")
            
            # Read it back and verify it's still XLIFF 1.2
            result = read_xliff_file(temp_file)
            assert result['version'] == '1.2'
            
            # Verify the XML structure is XLIFF 1.2 (trans-unit in body)
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'version="1.2"' in content
                assert 'xmlns="urn:oasis:names:tc:xliff:document:1.2"' in content
                assert '<body>' in content
                assert '<trans-unit id=' in content
        finally:
            os.unlink(temp_file)

    def test_update_xliff_targets_with_empty_target(self):
        """Test updating XLIFF targets when original target is empty."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': ''  # Empty target
                    }
                ]
            }]
        }
        
        translations = {
            'key1': 'Bonjour'
        }
        
        result = update_xliff_targets(xliff_content, translations)
        
        assert result['files'][0]['trans-units'][0]['source'] == 'Hello'
        assert result['files'][0]['trans-units'][0]['target'] == 'Bonjour'

    def test_update_xliff_targets_handles_missing_translation(self):
        """Test that update_xliff_targets handles units without translations gracefully."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': ''
                    }
                ]
            }]
        }
        
        translations = {}  # No translations provided
        
        result = update_xliff_targets(xliff_content, translations)
        
        # Should use source as target if no translation and target is empty
        assert result['files'][0]['trans-units'][0]['source'] == 'Hello'
        assert result['files'][0]['trans-units'][0]['target'] == 'Hello'

    def test_update_xliff_targets_adds_missing_units_from_source(self):
        """Test that update_xliff_targets adds new units from source that don't exist in target."""
        target_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'es',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola'
                    }
                ]
            }]
        }
        
        source_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'en',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hello'
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'World'
                    },
                    {
                        'id': 'key3',
                        'source': 'Test',
                        'target': 'Test'
                    }
                ]
            }]
        }
        
        translations = {
            'key1': 'Hola',
            'key2': 'Mundo',
            'key3': 'Prueba'
        }
        
        result = update_xliff_targets(target_content, translations, source_content)
        
        # Verify existing unit is updated
        assert result['files'][0]['trans-units'][0]['id'] == 'key1'
        assert result['files'][0]['trans-units'][0]['source'] == 'Hello'
        assert result['files'][0]['trans-units'][0]['target'] == 'Hola'
        
        # Verify new units from source are added
        assert len(result['files'][0]['trans-units']) == 3
        
        # Find key2
        key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit['source'] == 'World'
        assert key2_unit['target'] == 'Mundo'
        
        # Find key3
        key3_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key3'), None)
        assert key3_unit is not None
        assert key3_unit['source'] == 'Test'
        assert key3_unit['target'] == 'Prueba'

    def test_write_xliff_file_adds_state_attribute(self):
        """Test that write_xliff_file adds state attribute to target elements when unit has state."""
        xliff_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'es',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola',
                        'state': 'needs-review-translation'  # Unit has state
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "es", "translated")
            
            # Read it back and verify state attribute is present
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'state="needs-review-translation"' in content
                assert '<target state="needs-review-translation">Hola</target>' in content
        finally:
            os.unlink(temp_file)

    def test_write_xliff_file_preserves_existing_state(self):
        """Test that write_xliff_file preserves existing state from unit data."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola',
                        'state': 'final'  # Existing state
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            # Pass different state, but unit's state should take precedence
            write_xliff_file(temp_file, xliff_content, "en", "es", "needs-review-translation")
            
            # Read it back and verify the unit's state is preserved
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'state="final"' in content
                assert 'state="needs-review-translation"' not in content
        finally:
            os.unlink(temp_file)

    def test_update_xliff_targets_updates_target_without_state_for_existing_units(self):
        """Test that update_xliff_targets updates target but does NOT set state for existing units."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': ''
                    }
                ]
            }]
        }
        
        translations = {
            'key1': 'Hola'
        }
        
        result = update_xliff_targets(xliff_content, translations, None, "needs-review-translation")
        
        assert result['files'][0]['trans-units'][0]['target'] == 'Hola'
        # State should NOT be set for existing units, only for new units from source
        assert 'state' not in result['files'][0]['trans-units'][0]

    def test_update_xliff_targets_preserves_existing_state(self):
        """Test that update_xliff_targets preserves existing state attributes."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola',
                        'state': 'final'  # Existing state
                    }
                ]
            }]
        }
        
        translations = {
            'key1': 'Hola Updated'
        }
        
        # Pass different state, but existing state should be preserved
        result = update_xliff_targets(xliff_content, translations, None, "needs-review-translation")
        
        assert result['files'][0]['trans-units'][0]['target'] == 'Hola Updated'
        assert result['files'][0]['trans-units'][0]['state'] == 'final'  # Preserved

    def test_read_xliff_file_preserves_state_attribute(self):
        """Test that read_xliff_file preserves state attribute when reading."""
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en-US">
  <file id="ngi18n" original="ng.template">
    <unit id="6439365426343089851">
      <segment>
        <source>General</source>
        <target state="needs-review-translation">Général</target>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            assert result['files'][0]['trans-units'][0]['state'] == 'needs-review-translation'
        finally:
            os.unlink(temp_file)

    def test_update_xliff_targets_sets_state_only_for_translated_keys(self):
        """Test that update_xliff_targets sets state ONLY for keys in translations dict."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola'  # Already translated, not in translations dict
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': ''  # Missing translation, will be in translations dict
                    },
                    {
                        'id': 'key3',
                        'source': 'Test',
                        'target': 'Prueba'  # Already translated, not in translations dict
                    }
                ]
            }]
        }
        
        translations = {
            'key2': 'Mundo'  # Only key2 is being translated
        }
        
        result = update_xliff_targets(xliff_content, translations, None, "needs-review")
        
        # key1: not in translations, should NOT get state
        key1_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        assert key1_unit['target'] == 'Hola'
        assert 'state' not in key1_unit  # Should NOT have state
        
        # key2: in translations, target updated but state should NOT be set for existing units
        key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit['target'] == 'Mundo'
        assert 'state' not in key2_unit  # State should NOT be set for existing units
        
        # key3: not in translations, should NOT get state
        key3_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key3'), None)
        assert key3_unit is not None
        assert key3_unit['target'] == 'Prueba'
        assert 'state' not in key3_unit  # Should NOT have state

    def test_update_xliff_targets_sets_state_for_new_units_from_source(self):
        """Test that update_xliff_targets sets state for new units added from source."""
        target_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola'
                    }
                ]
            }]
        }
        
        source_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hello'
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'World'
                    }
                ]
            }]
        }
        
        translations = {
            'key2': 'Mundo'
        }
        
        result = update_xliff_targets(target_content, translations, source_content, "needs-review")
        
        # key1: existing unit, not in translations, should NOT get state
        key1_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        assert 'state' not in key1_unit
        
        # key2: new unit from source, in translations, should get state
        key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit['target'] == 'Mundo'
        assert key2_unit['state'] == 'needs-review'

    def test_write_xliff_file_only_writes_state_when_unit_has_state(self):
        """Test that write_xliff_file only writes state attribute when unit explicitly has it."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola',
                        'state': 'needs-review'  # Has state
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'Mundo'  # No state
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            # Pass target_state, but it should only be used if unit has state
            write_xliff_file(temp_file, xliff_content, "en", "es", "translated")
            
            # Read it back and verify
            with open(temp_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # key1 should have state
                assert 'id="key1"' in content
                assert 'state="needs-review"' in content
                # key2 should NOT have state
                assert 'id="key2"' in content
                # Verify key2's target doesn't have state attribute
                import re
                key2_target_match = re.search(r'id="key2"[^>]*>.*?<target([^>]*)>Mundo</target>', content, re.DOTALL)
                if key2_target_match:
                    target_attrs = key2_target_match.group(1)
                    assert 'state=' not in target_attrs
        finally:
            os.unlink(temp_file)

    def test_write_xliff_file_preserves_existing_state_values(self):
        """Test that write_xliff_file preserves existing state values, doesn't overwrite with target_state param."""
        xliff_content = {
            'version': '2.0',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola',
                        'state': 'final'  # Existing state
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'Mundo',
                        'state': 'needs-review'  # Different existing state
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            # Pass different target_state, but unit's state should be preserved
            write_xliff_file(temp_file, xliff_content, "en", "es", "translated")
            
            # Read it back and verify states are preserved
            result = read_xliff_file(temp_file)
            key1_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key1'), None)
            key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
            
            assert key1_unit['state'] == 'final'
            assert key2_unit['state'] == 'needs-review'
        finally:
            os.unlink(temp_file)

    def test_update_xliff_targets_does_not_set_state_for_units_not_in_translations(self):
        """Test that update_xliff_targets does NOT set state for units not in translations dict."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola'
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'Mundo'
                    }
                ]
            }]
        }
        
        translations = {
            'key1': 'Hola Updated'  # Only key1 is in translations
        }
        
        result = update_xliff_targets(xliff_content, translations, None, "needs-review")
        
        # key1: in translations, target updated but state should NOT be set for existing units
        key1_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit['target'] == 'Hola Updated'
        assert 'state' not in key1_unit  # State should NOT be set for existing units
        
        # key2: NOT in translations, should NOT get state
        key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit['target'] == 'Mundo'
        assert 'state' not in key2_unit  # Should NOT have state

    def test_read_xliff_file_preserves_units_without_state(self):
        """Test that read_xliff_file correctly handles units without state attribute."""
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file source-language="en" target-language="es">
    <body>
      <trans-unit id="key1">
        <source>Hello</source>
        <target>Hola</target>
      </trans-unit>
      <trans-unit id="key2">
        <source>World</source>
        <target state="needs-review">Mundo</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            assert len(result['files'][0]['trans-units']) == 2
            
            key1_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key1'), None)
            assert key1_unit is not None
            assert 'state' not in key1_unit  # Should NOT have state key
            
            key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
            assert key2_unit is not None
            assert key2_unit['state'] == 'needs-review'  # Should have state
        finally:
            os.unlink(temp_file)

    def test_write_xliff_file_roundtrip_preserves_state_selectively(self):
        """Test that write/read roundtrip preserves state only for units that had it."""
        xliff_content = {
            'version': '1.2',
            'files': [{
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Hola',
                        'state': 'needs-review'
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'Mundo'
                        # No state
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "es", "translated")
            
            # Read it back
            result = read_xliff_file(temp_file)
            
            key1_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key1'), None)
            key2_unit = next((u for u in result['files'][0]['trans-units'] if u['id'] == 'key2'), None)
            
            assert key1_unit['state'] == 'needs-review'
            assert 'state' not in key2_unit
        finally:
            os.unlink(temp_file)
