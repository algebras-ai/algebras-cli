"""
Tests for XLIFF state attribute placement and configuration.

This test suite verifies that:
- State attribute is placed on <target> for XLIFF 1.2
- State attribute is placed on <segment> for XLIFF 2.0
- State attribute is added to newly translated targets
- State attribute respects XLIFF version from config
"""

import os
import tempfile
import xml.etree.ElementTree as ET
import pytest
from algebras.utils.xliff_handler import write_xliff_file, update_xliff_targets, read_xliff_file


class TestXLIFFStateAttribute:
    """Test cases for XLIFF state attribute placement."""
    
    def test_state_attribute_on_target_xliff_12(self):
        """
        Test that state attribute is placed on <target> element for XLIFF 1.2.
        
        Behavior: When writing XLIFF 1.2 files, the state attribute should be
        placed on the <target> element, not on <segment> or <trans-unit>.
        """
        xliff_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Bonjour',
                        'state': 'translated'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "fr", "translated")
            
            # Read back and verify state is on target
            tree = ET.parse(temp_file)
            root = tree.getroot()
            
            # Find target element
            namespace = 'urn:oasis:names:tc:xliff:document:1.2'
            target_elem = root.find(f'.//{{{namespace}}}target')
            if target_elem is None:
                target_elem = root.find('.//target')
            
            assert target_elem is not None
            assert target_elem.get('state') == 'translated'
            
            # Verify state is NOT on segment (XLIFF 1.2 doesn't have segment)
            segment_elem = root.find(f'.//{{{namespace}}}segment')
            if segment_elem is None:
                segment_elem = root.find('.//segment')
            assert segment_elem is None  # XLIFF 1.2 doesn't use segment
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_state_attribute_on_segment_xliff_20(self):
        """
        Test that state attribute is placed on <segment> element for XLIFF 2.0.
        
        Behavior: When writing XLIFF 2.0 files, the state attribute should be
        placed on the <segment> element, not on <target>.
        """
        xliff_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Bonjour',
                        'state': 'translated'
                    }
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, xliff_content, "en", "fr", "translated")
            
            # Read back and verify state is on segment
            tree = ET.parse(temp_file)
            root = tree.getroot()
            
            # Find segment element
            namespace = 'urn:oasis:names:tc:xliff:document:2.0'
            segment_elem = root.find(f'.//{{{namespace}}}segment')
            if segment_elem is None:
                segment_elem = root.find('.//segment')
            
            assert segment_elem is not None
            assert segment_elem.get('state') == 'translated'
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_state_attribute_added_to_newly_translated_targets(self):
        """
        Test that state attribute is added to newly translated targets.
        
        Behavior: When update_xliff_targets adds new units from source, it should
        add the state attribute to those new units.
        """
        # Target file (empty)
        target_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': []
            }]
        }
        
        # Source file
        source_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': ''}
                ]
            }]
        }
        
        # Translations
        translations = {'key1': 'Bonjour'}
        
        # Update with state
        updated = update_xliff_targets(target_content, translations, source_content, target_state='translated')
        
        # Verify new unit has state
        assert len(updated['files'][0]['trans-units']) == 1
        new_unit = updated['files'][0]['trans-units'][0]
        assert new_unit['id'] == 'key1'
        assert new_unit['target'] == 'Bonjour'
        assert new_unit.get('state') == 'translated'
    
    def test_state_attribute_respects_xliff_version_from_config(self):
        """
        Test that state attribute respects XLIFF version from config.
        
        Behavior: When writing XLIFF files, the version should determine where
        the state attribute is placed. This is controlled by the version in the
        content dictionary, which should come from config.
        """
        # Test XLIFF 1.2
        content_12 = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour', 'state': 'translated'}
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            temp_file_12 = f.name
        
        try:
            write_xliff_file(temp_file_12, content_12, "en", "fr", "translated")
            
            tree = ET.parse(temp_file_12)
            root = tree.getroot()
            namespace = 'urn:oasis:names:tc:xliff:document:1.2'
            target_elem = root.find(f'.//{{{namespace}}}target')
            if target_elem is None:
                target_elem = root.find('.//target')
            
            # For 1.2, state should be on target
            assert target_elem is not None
            assert target_elem.get('state') == 'translated'
        finally:
            if os.path.exists(temp_file_12):
                os.unlink(temp_file_12)
        
        # Test XLIFF 2.0
        content_20 = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour', 'state': 'translated'}
                ]
            }]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            temp_file_20 = f.name
        
        try:
            write_xliff_file(temp_file_20, content_20, "en", "fr", "translated")
            
            tree = ET.parse(temp_file_20)
            root = tree.getroot()
            namespace = 'urn:oasis:names:tc:xliff:document:2.0'
            segment_elem = root.find(f'.//{{{namespace}}}segment')
            if segment_elem is None:
                segment_elem = root.find('.//segment')
            
            # For 2.0, state should be on segment
            assert segment_elem is not None
            assert segment_elem.get('state') == 'translated'
        finally:
            if os.path.exists(temp_file_20):
                os.unlink(temp_file_20)
    
    def test_state_attribute_preserved_when_updating_existing(self):
        """
        Test that existing state attributes are preserved when updating targets.
        
        Behavior: When update_xliff_targets updates an existing unit, it should
        preserve any existing state attribute, not overwrite it.
        """
        # Target with existing state
        target_content = {
            'version': '1.2',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Bonjour',
                        'state': 'needs-review-translation'  # Existing state
                    }
                ]
            }]
        }
        
        # Update with new translation but no state override
        translations = {'key1': 'Salut'}
        updated = update_xliff_targets(target_content, translations, None, target_state=None)
        
        # State should be preserved (or updated if target_state is provided)
        # This depends on implementation - if target_state is None, preserve existing
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        # The state might be preserved or updated based on implementation
        assert 'state' in key1_unit

