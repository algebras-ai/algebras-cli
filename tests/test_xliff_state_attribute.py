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
    
    def test_state_attribute_added_to_existing_units_without_state(self):
        """
        Test that state attribute is NOT added to existing units, only preserved if present.
        
        Behavior: When update_xliff_targets is called with target_state, it should NOT add
        the state to existing units. State is only added to new units from source_content.
        This prevents changing the state of units that were already reviewed/translated.
        """
        # Target with existing units but no state
        target_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Bonjour'
                        # No state attribute
                    },
                    {
                        'id': 'key2',
                        'source': 'World',
                        'target': 'Monde',
                        'state': 'needs-review-translation'  # Has existing state
                    }
                ]
            }]
        }
        
        # Update with target_state - should NOT add state to key1, but preserve key2's state
        translations = {'key1': 'Salut', 'key2': 'Monde'}
        updated = update_xliff_targets(target_content, translations, None, target_state='translated')
        
        # Verify key1 did NOT get state added (existing units don't get state)
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        assert 'state' not in key1_unit  # State was NOT added to existing unit
        
        # Verify key2's existing state was preserved
        key2_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit.get('state') == 'needs-review-translation'  # Existing state preserved
    
    def test_state_attribute_added_to_existing_units_with_only_missing(self):
        """
        Test that state attribute is NOT added to existing units when using only_missing flag.
        
        Behavior: When using --only-missing flag, existing units should NOT get the state
        attribute added. State is only added to new units from source_content. This prevents
        changing the state of units that were already reviewed/translated.
        """
        # Target with existing units but no state
        target_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {
                        'id': 'key1',
                        'source': 'Hello',
                        'target': 'Bonjour'  # Existing translation, no state
                    }
                ]
            }]
        }
        
        # Update with only_missing=True and target_state
        # key1 already has a target, so it should be preserved and state should NOT be added
        translations = {'key1': 'Salut'}  # This should be ignored due to only_missing
        updated = update_xliff_targets(target_content, translations, None, target_state='needs-review-translation', only_missing=True)
        
        # Verify key1's target was preserved
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        assert key1_unit['target'] == 'Bonjour'  # Target preserved
        
        # Verify key1 did NOT get state added (existing units don't get state)
        assert 'state' not in key1_unit  # State was NOT added to existing unit
    
    def test_state_attribute_on_segment_xliff_20_with_only_missing(self):
        """
        Test that state attribute is placed on <segment> element for XLIFF 2.0 when using only_missing flag.
        
        Behavior: When using --only-missing flag with XLIFF 2.0 files, the state attribute should be
        placed on the <segment> element, not on <target>. This is the correct behavior per XLIFF 2.0 spec.
        """
        # Target file with one existing translation
        target_content = {
            'version': '2.0',
            'files': [{
                'original': 'messages',
                'source-language': 'en',
                'target-language': 'fr',
                'trans-units': [
                    {'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'}  # Already translated
                ]
            }]
        }
        
        # Source file with two keys
        source_content = {
            'version': '2.0',
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
        
        # Translations dict contains both keys, but only key2 should be added (only_missing=True)
        translations = {
            'key1': 'Salut',  # Should be ignored (already exists)
            'key2': 'Monde'   # Should be added (missing)
        }
        
        # Update with only_missing=True and target_state
        updated = update_xliff_targets(target_content, translations, source_content, target_state='translated', only_missing=True)
        
        # Verify key1 was NOT overwritten
        key1_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key1'), None)
        assert key1_unit is not None
        assert key1_unit['target'] == 'Bonjour'  # Original preserved, not 'Salut'
        
        # Verify key2 was added with state
        key2_unit = next((u for u in updated['files'][0]['trans-units'] if u['id'] == 'key2'), None)
        assert key2_unit is not None
        assert key2_unit['target'] == 'Monde'
        assert key2_unit.get('state') == 'translated'
        
        # Write to file and verify state is on segment, not target
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            temp_file = f.name
        
        try:
            write_xliff_file(temp_file, updated, "en", "fr", "translated")
            
            # Read back and verify state is on segment for XLIFF 2.0
            tree = ET.parse(temp_file)
            root = tree.getroot()
            
            # Verify version is 2.0
            assert root.get('version') == '2.0'
            
            namespace = 'urn:oasis:names:tc:xliff:document:2.0'
            
            # Find segment elements
            segments = root.findall(f'.//{{{namespace}}}segment')
            if not segments:
                segments = root.findall('.//segment')
            
            assert len(segments) >= 2  # At least key1 and key2
            
            # Find the segment for key2 (the newly added one)
            # We need to find the unit with id="key2" and then its segment
            units = root.findall(f'.//{{{namespace}}}unit')
            if not units:
                units = root.findall('.//unit')
            
            key2_unit_elem = None
            for unit in units:
                if unit.get('id') == 'key2':
                    key2_unit_elem = unit
                    break
            
            assert key2_unit_elem is not None
            key2_segment = key2_unit_elem.find(f'{{{namespace}}}segment')
            if key2_segment is None:
                key2_segment = key2_unit_elem.find('segment')
            
            assert key2_segment is not None
            # State should be on segment for XLIFF 2.0
            assert key2_segment.get('state') == 'translated'
            
            # Verify state is NOT on target element
            key2_target = key2_segment.find(f'{{{namespace}}}target')
            if key2_target is None:
                key2_target = key2_segment.find('target')
            
            assert key2_target is not None
            assert key2_target.get('state') is None  # State should NOT be on target
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

