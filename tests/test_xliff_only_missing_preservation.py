"""
Tests for XLIFF --only-missing flag preserving existing translations.

This test suite verifies that when using --only-missing flag:
- Existing translations in target files are preserved
- Second run with --only-missing doesn't overwrite existing translations
- Only missing keys are translated and added
"""

import os
import tempfile
import pytest
from algebras.utils.xliff_handler import (
    read_xliff_file, write_xliff_file, update_xliff_targets, extract_translatable_strings
)


class TestXLIFFOnlyMissingPreservation:
    """Test cases for --only-missing flag preserving existing translations."""
    
    def test_only_missing_preserves_existing_translations(self):
        """
        Test that --only-missing preserves existing translations when target file exists.
        
        Behavior: When updating a target file with --only-missing, existing target values
        should remain unchanged, and only missing keys should be added with translations.
        """
        # Create source XLIFF with 3 units
        source_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': ''},
                    {'id': 'key2', 'source': 'World', 'target': ''},
                    {'id': 'key3', 'source': 'Test', 'target': ''}
                ]
            }]
        }
        
        # Create target XLIFF with 2 existing translations
        target_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'},  # Existing translation
                    {'id': 'key2', 'source': 'World', 'target': 'Monde'}  # Existing translation
                    # key3 is missing
                ]
            }]
        }
        
        # Simulate translation of only missing keys (key3)
        translations = {'key3': 'Teste'}  # Only translate missing key
        
        # Update targets
        updated = update_xliff_targets(target_content, translations, source_content)
        
        # Verify existing translations are preserved
        assert len(updated['files'][0]['trans-units']) == 3
        
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        assert key1_unit['target'] == 'Bonjour'  # Preserved
        
        key2_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit['target'] == 'Monde'  # Preserved
        
        # Verify missing key was added
        key3_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key3'), None)
        assert key3_unit is not None
        assert key3_unit['target'] == 'Teste'  # Newly translated
    
    def test_second_run_doesnt_overwrite_existing_translations(self):
        """
        Test that second run with --only-missing doesn't overwrite existing translations.
        
        Behavior: When running --only-missing twice, the second run should not replace
        existing translations with untranslated values. It should only add truly missing keys.
        """
        # Initial target file with some translations
        target_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'},
                    {'id': 'key2', 'source': 'World', 'target': 'Monde'}
                ]
            }]
        }
        
        # Source content
        source_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': ''},
                    {'id': 'key2', 'source': 'World', 'target': ''},
                    {'id': 'key3', 'source': 'Test', 'target': ''}
                ]
            }]
        }
        
        # First run: translate missing key3
        translations_run1 = {'key3': 'Teste'}
        updated_run1 = update_xliff_targets(target_content, translations_run1, source_content)
        
        # Verify existing translations preserved
        key1_unit = next((u for u in updated_run1['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit['target'] == 'Bonjour'
        
        # Second run: simulate running again with same missing keys (should be empty now)
        # But if somehow key1 or key2 are in translations dict, they should NOT overwrite
        translations_run2 = {}  # No missing keys
        updated_run2 = update_xliff_targets(updated_run1, translations_run2, source_content)
        
        # Verify existing translations still preserved
        key1_unit_run2 = next((u for u in updated_run2['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit_run2['target'] == 'Bonjour'  # Still preserved
        
        key2_unit_run2 = next((u for u in updated_run2['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit_run2['target'] == 'Monde'  # Still preserved
    
    def test_only_missing_keys_are_translated(self):
        """
        Test that only missing keys are translated and added.
        
        Behavior: When using --only-missing, the update_xliff_targets function should
        only update targets for keys that are in the translations dictionary and were
        missing from the target file. Keys already present should be left unchanged.
        """
        # Target with one existing translation
        target_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'}  # Already translated
                ]
            }]
        }
        
        # Source with two keys
        source_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': ''},
                    {'id': 'key2', 'source': 'World', 'target': ''}  # Missing
                ]
            }]
        }
        
        # Translations dict contains both keys, but only key2 should be updated
        translations = {
            'key1': 'Salut',  # Should be ignored (already exists)
            'key2': 'Monde'   # Should be added (missing)
        }
        
        updated = update_xliff_targets(target_content, translations, source_content, only_missing=True)
        
        # Verify key1 was NOT overwritten
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit['target'] == 'Bonjour'  # Original preserved, not 'Salut'
        
        # Verify key2 was added
        key2_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit['target'] == 'Monde'
    
    def test_update_xliff_targets_preserves_existing_when_translation_missing(self):
        """
        Test that update_xliff_targets preserves existing targets when translation is not provided.
        
        Behavior: If a unit exists in target but is not in the translations dictionary,
        its existing target value should be preserved, not replaced with source or empty.
        """
        target_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'}  # Existing
                ]
            }]
        }
        
        source_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': ''},
                    {'id': 'key2', 'source': 'World', 'target': ''}
                ]
            }]
        }
        
        # Only translate key2, not key1
        translations = {'key2': 'Monde'}
        
        updated = update_xliff_targets(target_content, translations, source_content)
        
        # Verify key1 target is preserved
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit['target'] == 'Bonjour'  # Preserved, not replaced
        
        # Verify key2 was added
        key2_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit['target'] == 'Monde'

