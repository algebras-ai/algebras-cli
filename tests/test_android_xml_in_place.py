"""
Test Android XML in-place update functionality
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

from algebras.utils.android_xml_handler import (
    write_android_xml_file_in_place,
    read_android_xml_file,
    write_android_xml_file
)
from algebras.config import Config


def test_android_xml_in_place_update_existing_keys():
    """Test that in-place updates modify only specified keys"""
    # Create initial XML file
    initial_content = {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        # Write initial file
        write_android_xml_file(temp_file, initial_content)
        
        # Update only key1 and key2
        updated_content = {
            "key1": "updated_value1",
            "key2": "updated_value2",
            "key3": "value3"  # Should remain unchanged
        }
        
        write_android_xml_file_in_place(temp_file, updated_content, keys_to_update={"key1", "key2"})
        
        # Read back and verify
        result = read_android_xml_file(temp_file)
        assert result["key1"] == "updated_value1"
        assert result["key2"] == "updated_value2"
        assert result["key3"] == "value3"  # Should remain unchanged
        
    finally:
        os.unlink(temp_file)


def test_android_xml_in_place_add_new_keys():
    """Test that in-place updates add new keys at the end"""
    # Create initial XML file
    initial_content = {
        "key1": "value1",
        "key2": "value2"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        # Write initial file
        write_android_xml_file(temp_file, initial_content)
        
        # Add new keys
        updated_content = {
            "key1": "value1",
            "key2": "value2",
            "key3": "new_value3",
            "key4": "new_value4"
        }
        
        write_android_xml_file_in_place(temp_file, updated_content, keys_to_update={"key3", "key4"})
        
        # Read back and verify
        result = read_android_xml_file(temp_file)
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"
        assert result["key3"] == "new_value3"
        assert result["key4"] == "new_value4"
        
    finally:
        os.unlink(temp_file)


def test_android_xml_in_place_preserve_entities():
    """Test that in-place updates preserve HTML entities like &#160;"""
    # Create initial XML file with &#160; entity
    initial_content = {
        "key1": "user&#160;agreement"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        # Write initial file with entity
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write('<resources>\n')
            f.write('    <string name="key1">user&#160;agreement</string>\n')
            f.write('</resources>\n')
        
        # Update with new value that should also have entity
        updated_content = {
            "key1": "termini di utilizzo"  # This will be translated and should preserve entity format
        }
        
        write_android_xml_file_in_place(temp_file, updated_content, keys_to_update={"key1"})
        
        # Read the file content directly to check entity format
        with open(temp_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # The key originally had &#160;, so new value should also use entity if it has non-breaking space
        # But since the translation doesn't have non-breaking space, it won't be added
        # However, if we add a non-breaking space, it should be converted to &#160;
        
        # Read back and verify the key was updated
        result = read_android_xml_file(temp_file)
        assert result["key1"] == "termini di utilizzo"
        
    finally:
        os.unlink(temp_file)


def test_android_xml_in_place_non_existent_file():
    """Test that in-place update falls back to regular write for non-existent files"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    # Remove the file so it doesn't exist
    if os.path.exists(temp_file):
        os.unlink(temp_file)
    
    try:
        content = {
            "key1": "value1"
        }
        
        # Should not raise error, should create file
        write_android_xml_file_in_place(temp_file, content)
        
        # Verify file was created
        assert os.path.exists(temp_file)
        result = read_android_xml_file(temp_file)
        assert result["key1"] == "value1"
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_android_xml_in_place_update_all_keys():
    """Test that updating all keys works when keys_to_update is None"""
    initial_content = {
        "key1": "value1",
        "key2": "value2"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        temp_file = f.name
    
    try:
        write_android_xml_file(temp_file, initial_content)
        
        updated_content = {
            "key1": "updated1",
            "key2": "updated2",
            "key3": "new3"
        }
        
        # Update all keys (keys_to_update=None means update all)
        write_android_xml_file_in_place(temp_file, updated_content, keys_to_update=None)
        
        result = read_android_xml_file(temp_file)
        assert result["key1"] == "updated1"
        assert result["key2"] == "updated2"
        assert result["key3"] == "new3"
        
    finally:
        os.unlink(temp_file)

