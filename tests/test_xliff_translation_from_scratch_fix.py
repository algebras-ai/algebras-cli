"""
Tests for XLIFF translation from scratch bug fix.

This test file covers the fix for the issue where XLIFF translations
were using source text instead of actual translations when creating
target files from scratch.

Bug: translate_command.py was incorrectly handling the return value from
translator.translate_file() for XLIFF files, treating it as a flat dict
when it was actually a structured dict, resulting in empty translations
and fallback to source text.

Fix: Changed XLIFF handling to extract strings first, translate as flat dict,
then update structure properly.
"""

import os
import tempfile
import json
from unittest.mock import patch, MagicMock, Mock
from io import StringIO

import pytest

from algebras.utils.xliff_handler import (
    read_xliff_file,
    write_xliff_file,
    extract_translatable_strings,
    update_xliff_targets
)
from algebras.services.translator import Translator
from algebras.config import Config


class TestXLIFFTranslationFromScratchFix:
    """Test the fix for XLIFF translation from scratch bug."""
    
    @pytest.fixture
    def source_xliff_content(self):
        """Create a sample source XLIFF file content."""
        return '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en-US">
  <file id="ngi18n" original="ng.template">
    <unit id="test.general">
      <segment>
        <source>General</source>
      </segment>
    </unit>
    <unit id="test.display">
      <segment>
        <source>Display</source>
      </segment>
    </unit>
    <unit id="test.patient">
      <segment>
        <source>Patient management</source>
      </segment>
    </unit>
  </file>
</xliff>'''
    
    @pytest.fixture
    def mock_translations(self):
        """Mock translations that should be returned by the translator."""
        return {
            "test.general": "Общее",
            "test.display": "Отображение",
            "test.patient": "Управление пациентами"
        }
    
    def test_extract_translatable_strings_from_xliff(self, source_xliff_content):
        """Test that we can extract flat strings from XLIFF structure."""
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff_content)
            temp_file = f.name
        
        try:
            # Read and extract
            content = read_xliff_file(temp_file)
            strings = extract_translatable_strings(content)
            
            # Verify we got flat dictionary
            assert isinstance(strings, dict)
            assert "test.general" in strings
            assert strings["test.general"] == "General"
            assert "test.display" in strings
            assert strings["test.display"] == "Display"
            assert "test.patient" in strings
            assert strings["test.patient"] == "Patient management"
        finally:
            os.unlink(temp_file)
    
    def test_update_xliff_targets_with_translations(self, source_xliff_content, mock_translations):
        """Test that update_xliff_targets properly applies translations."""
        # Create temp source file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff_content)
            source_file = f.name
        
        try:
            # Read source
            source_content = read_xliff_file(source_file)
            
            # Create empty target
            target_content = {'version': '2.0', 'files': []}
            
            # Update with translations
            updated_content = update_xliff_targets(
                target_content,
                mock_translations,
                source_content,
                "translated"
            )
            
            # Verify structure
            assert 'version' in updated_content
            assert updated_content['version'] == '2.0'
            assert 'files' in updated_content
            assert len(updated_content['files']) > 0
            
            # Verify translations were applied (not source text)
            trans_units = updated_content['files'][0]['trans-units']
            
            # Find the units and verify they have translations, not source text
            general_unit = next(u for u in trans_units if u['id'] == 'test.general')
            assert general_unit['source'] == "General"
            assert general_unit['target'] == "Общее"  # Translation, not source!
            
            display_unit = next(u for u in trans_units if u['id'] == 'test.display')
            assert display_unit['source'] == "Display"
            assert display_unit['target'] == "Отображение"  # Translation, not source!
            
            patient_unit = next(u for u in trans_units if u['id'] == 'test.patient')
            assert patient_unit['source'] == "Patient management"
            assert patient_unit['target'] == "Управление пациентами"  # Translation, not source!
            
        finally:
            os.unlink(source_file)
    
    def test_update_xliff_targets_without_translations_uses_empty_string(self, source_xliff_content):
        """Test that update_xliff_targets uses empty string (not source) when no translation provided."""
        # Create temp source file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff_content)
            source_file = f.name
        
        try:
            # Read source
            source_content = read_xliff_file(source_file)
            
            # Create empty target
            target_content = {'version': '2.0', 'files': []}
            
            # Update with NO translations (empty dict)
            updated_content = update_xliff_targets(
                target_content,
                {},  # Empty translations!
                source_content,
                "translated"
            )
            
            # Verify units were added but with empty targets (not source text)
            trans_units = updated_content['files'][0]['trans-units']
            
            general_unit = next(u for u in trans_units if u['id'] == 'test.general')
            assert general_unit['source'] == "General"
            # CRITICAL: Should be empty string, NOT "General"
            assert general_unit['target'] == ""
            
        finally:
            os.unlink(source_file)
    
    def test_write_xliff_file_with_translations(self, mock_translations):
        """Test writing XLIFF file with proper translations."""
        # Create XLIFF content with translations
        xliff_content = {
            'version': '2.0',
            'files': [{
                'original': 'ng.template',
                'source-language': 'en-US',
                'target-language': 'ru',
                'trans-units': [
                    {
                        'id': 'test.general',
                        'source': 'General',
                        'target': mock_translations['test.general'],
                        'state': 'translated'
                    },
                    {
                        'id': 'test.display',
                        'source': 'Display',
                        'target': mock_translations['test.display'],
                        'state': 'translated'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(suffix='.xlf', delete=False) as f:
            target_file = f.name
        
        try:
            # Write file
            write_xliff_file(target_file, xliff_content, 'en-US', 'ru', 'translated')
            
            # Read back and verify
            result = read_xliff_file(target_file)
            trans_units = result['files'][0]['trans-units']
            
            general_unit = next(u for u in trans_units if u['id'] == 'test.general')
            # Verify target has translation, not source
            assert general_unit['target'] == "Общее"
            assert general_unit['target'] != general_unit['source']
            
        finally:
            os.unlink(target_file)
    
    def test_translator_verbose_mode(self):
        """Test that translator verbose mode can be enabled."""
        # Create mock config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_api_config.return_value = {'provider': 'algebras-ai'}
        mock_config.get_languages.return_value = ['en', 'ru']
        
        # Create translator
        translator = Translator(config=mock_config)
        
        # Initially verbose should be False
        assert translator.verbose is False
        
        # Enable verbose
        translator.set_verbose(True)
        assert translator.verbose is True
        
        # Disable verbose
        translator.set_verbose(False)
        assert translator.verbose is False
    
    @patch('algebras.services.translator.requests.post')
    @patch('sys.stdout', new_callable=StringIO)
    def test_translator_verbose_logging(self, mock_stdout, mock_post):
        """Test that verbose mode produces debug output."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'translations': [
                    {'index': 0, 'content': 'Общее'}
                ]
            }
        }
        mock_post.return_value = mock_response
        
        # Create mock config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_api_config.return_value = {'provider': 'algebras-ai'}
        mock_config.get_languages.return_value = ['en', 'ru']
        mock_config.get_base_url.return_value = 'https://api.example.com'
        
        # Create translator with verbose enabled
        translator = Translator(config=mock_config)
        translator.set_verbose(True)
        
        # Mock environment
        with patch.dict(os.environ, {'ALGEBRAS_API_KEY': 'test-key'}):
            # Call batch translation
            result = translator._translate_with_algebras_ai_batch(
                ['General'],
                'en',
                'ru',
                False,
                ''
            )
        
        # Verify result
        assert result == ['Общее']
        
        # Verify verbose output was produced
        output = mock_stdout.getvalue()
        assert '[API Request]' in output or 'Translating' in output
    
    def test_update_xliff_targets_preserves_version(self, source_xliff_content, mock_translations):
        """Test that version is preserved during update."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff_content)
            source_file = f.name
        
        try:
            source_content = read_xliff_file(source_file)
            target_content = {'version': '2.0', 'files': []}
            
            updated_content = update_xliff_targets(
                target_content,
                mock_translations,
                source_content,
                "translated"
            )
            
            # Verify version was preserved
            assert 'version' in updated_content
            assert updated_content['version'] == '2.0'
            
        finally:
            os.unlink(source_file)
    
    def test_update_xliff_targets_adds_state_to_new_units(self, source_xliff_content, mock_translations):
        """Test that state attribute is added to new units."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff_content)
            source_file = f.name
        
        try:
            source_content = read_xliff_file(source_file)
            target_content = {'version': '2.0', 'files': []}
            
            # Custom state
            custom_state = "needs-review"
            
            updated_content = update_xliff_targets(
                target_content,
                mock_translations,
                source_content,
                custom_state
            )
            
            # Verify state was added to all new units
            trans_units = updated_content['files'][0]['trans-units']
            for unit in trans_units:
                assert 'state' in unit
                assert unit['state'] == custom_state
            
        finally:
            os.unlink(source_file)
    
    def test_update_xliff_targets_preserves_existing_state(self, source_xliff_content, mock_translations):
        """Test that existing unit states are preserved, not overwritten."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff_content)
            source_file = f.name
        
        try:
            source_content = read_xliff_file(source_file)
            
            # Create target with existing units that have state
            target_content = {
                'version': '2.0',
                'files': [{
                    'original': 'ng.template',
                    'source-language': 'en-US',
                    'target-language': 'ru',
                    'trans-units': [
                        {
                            'id': 'test.general',
                            'source': 'General',
                            'target': 'Старое значение',
                            'state': 'final'  # Existing state
                        }
                    ]
                }]
            }
            
            # Update with new translations and new state
            updated_content = update_xliff_targets(
                target_content,
                mock_translations,
                source_content,
                "translated"  # This should NOT override existing "final" state
            )
            
            # Find the existing unit
            trans_units = updated_content['files'][0]['trans-units']
            general_unit = next(u for u in trans_units if u['id'] == 'test.general')
            
            # Verify existing state was preserved
            assert general_unit['state'] == 'final'  # NOT "translated"
            
            # But translation should be updated
            assert general_unit['target'] == mock_translations['test.general']
            
        finally:
            os.unlink(source_file)


class TestXLIFFTranslationEndToEnd:
    """End-to-end integration tests for XLIFF translation from scratch."""
    
    def test_full_translation_workflow(self):
        """Test complete workflow: source XLIFF → extract → translate → write target."""
        # Step 1: Create source XLIFF
        source_xliff = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en-US">
  <file id="test" original="test.template">
    <unit id="app.title">
      <segment>
        <source>My Application</source>
      </segment>
    </unit>
    <unit id="app.welcome">
      <segment>
        <source>Welcome to our app!</source>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff)
            source_file = f.name
        
        target_file = tempfile.NamedTemporaryFile(suffix='.xlf', delete=False).name
        
        try:
            # Step 2: Read source and extract strings
            source_content = read_xliff_file(source_file)
            source_strings = extract_translatable_strings(source_content)
            
            assert source_strings == {
                "app.title": "My Application",
                "app.welcome": "Welcome to our app!"
            }
            
            # Step 3: Simulate translation (in real code, this would call translator._translate_flat_dict)
            translated_strings = {
                "app.title": "Mi Aplicación",
                "app.welcome": "¡Bienvenido a nuestra aplicación!"
            }
            
            # Step 4: Create empty target and update with translations
            target_content = {'version': '2.0', 'files': []}
            updated_content = update_xliff_targets(
                target_content,
                translated_strings,
                source_content,
                "translated"
            )
            
            # Step 5: Write target file
            write_xliff_file(target_file, updated_content, 'en-US', 'es', 'translated')
            
            # Step 6: Verify target file
            result = read_xliff_file(target_file)
            result_strings = extract_translatable_strings(result)
            
            # Verify we have source text in source elements
            trans_units = result['files'][0]['trans-units']
            title_unit = next(u for u in trans_units if u['id'] == 'app.title')
            assert title_unit['source'] == "My Application"
            assert title_unit['target'] == "Mi Aplicación"
            
            welcome_unit = next(u for u in trans_units if u['id'] == 'app.welcome')
            assert welcome_unit['source'] == "Welcome to our app!"
            assert welcome_unit['target'] == "¡Bienvenido a nuestra aplicación!"
            
            # CRITICAL: Verify targets contain translations, NOT source text
            assert title_unit['target'] != title_unit['source']
            assert welcome_unit['target'] != welcome_unit['source']
            
        finally:
            os.unlink(source_file)
            os.unlink(target_file)
    
    def test_regression_source_text_not_used_as_fallback(self):
        """Regression test: Ensure source text is NOT used when translations are missing."""
        source_xliff = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en-US">
  <file id="test" original="test.template">
    <unit id="test.key">
      <segment>
        <source>English Text</source>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as f:
            f.write(source_xliff)
            source_file = f.name
        
        try:
            source_content = read_xliff_file(source_file)
            
            # Update with EMPTY translations dict (simulate translation failure)
            target_content = {'version': '2.0', 'files': []}
            updated_content = update_xliff_targets(
                target_content,
                {},  # No translations!
                source_content,
                "translated"
            )
            
            # Verify target is empty string, NOT source text
            trans_units = updated_content['files'][0]['trans-units']
            unit = trans_units[0]
            
            assert unit['source'] == "English Text"
            # CRITICAL: This should be empty, NOT "English Text"
            assert unit['target'] == ""
            assert unit['target'] != unit['source']
            
        finally:
            os.unlink(source_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

