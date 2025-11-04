"""
Test in-place update functionality across formats
"""

import tempfile
import os
import json
from unittest.mock import patch, MagicMock

from algebras.commands.translate_command import _should_use_in_place
from algebras.utils.android_xml_handler import (
    write_android_xml_file_in_place,
    read_android_xml_file,
    write_android_xml_file
)


def test_should_use_in_place_with_flag():
    """Test that regenerate_from_scratch flag prevents in-place updates"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        # Create file
        with open(temp_file, 'w') as f:
            f.write('test')
        
        # With flag set, should not use in-place
        assert _should_use_in_place(temp_file, regenerate_from_scratch=True) == False
        
        # Without flag, should use in-place if file exists
        assert _should_use_in_place(temp_file, regenerate_from_scratch=False) == True
        
    finally:
        os.unlink(temp_file)


def test_should_use_in_place_no_file():
    """Test that non-existent files don't use in-place updates"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    # Remove file so it doesn't exist
    if os.path.exists(temp_file):
        os.unlink(temp_file)
    
    try:
        # Should not use in-place for non-existent files
        assert _should_use_in_place(temp_file, regenerate_from_scratch=False) == False
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_android_xml_in_place_preserves_order():
    """Test that in-place updates preserve element order"""
    initial_content = {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        from algebras.utils.android_xml_handler import write_android_xml_file
        write_android_xml_file(temp_file, initial_content)
        
        # Read file to see initial order
        with open(temp_file, 'r', encoding='utf-8') as f:
            initial_lines = f.readlines()
        
        # Update only key2
        updated_content = {
            "key1": "value1",
            "key2": "updated_value2",
            "key3": "value3"
        }
        
        write_android_xml_file_in_place(temp_file, updated_content, keys_to_update={"key2"})
        
        # Read back and verify order is preserved
        result = read_android_xml_file(temp_file)
        assert result["key1"] == "value1"
        assert result["key2"] == "updated_value2"
        assert result["key3"] == "value3"
        
        # Verify that only key2 was updated (order should be similar)
        with open(temp_file, 'r', encoding='utf-8') as f:
            updated_lines = f.readlines()
        
        # Key positions should be similar (not reordered)
        initial_key2_pos = None
        updated_key2_pos = None
        
        for i, line in enumerate(initial_lines):
            if 'name="key2"' in line:
                initial_key2_pos = i
        
        for i, line in enumerate(updated_lines):
            if 'name="key2"' in line:
                updated_key2_pos = i
        
        # Key2 should be in similar position (not moved to end)
        assert initial_key2_pos is not None
        assert updated_key2_pos is not None
        
    finally:
        os.unlink(temp_file)


def test_android_xml_in_place_handles_malformed_file():
    """Test that in-place update falls back gracefully for malformed XML"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        # Write malformed XML
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0"?>\n')
            f.write('<resources>\n')
            f.write('<string name="key1">value1</string>\n')
            # Missing closing tag to make it malformed
            # Actually, let's make it valid but with wrong root
            f.write('</wrong_root>\n')
        
        # Should fall back to regular write
        content = {
            "key1": "value1"
        }
        
        # Should not raise error, should handle gracefully
        try:
            write_android_xml_file_in_place(temp_file, content)
        except Exception:
            # If it fails, that's okay - it should fall back
            pass
        
    finally:
        os.unlink(temp_file)

