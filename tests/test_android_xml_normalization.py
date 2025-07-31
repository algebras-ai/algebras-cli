"""
Test Android XML handler normalization behavior
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

from algebras.utils.android_xml_handler import write_android_xml_file, read_android_xml_file, _escape_xml_text
from algebras.config import Config


def test_android_xml_normalization_enabled():
    """Test that Android XML handler doesn't escape apostrophes when normalization is enabled"""
    # Mock Config to return normalization enabled
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_setting.return_value = True  # normalization enabled
    
    with patch("algebras.utils.android_xml_handler.Config", return_value=mock_config):
        # Test the escape function directly
        result = _escape_xml_text("Ko'proq matn")
        assert result == "Ko'proq matn"  # Should NOT escape apostrophes
        
        # Test with quotes (should also NOT be escaped when normalization is enabled)
        result = _escape_xml_text('Say "hello"')
        assert result == 'Say "hello"'  # Should NOT escape quotes when normalization is enabled


def test_android_xml_normalization_disabled():
    """Test that Android XML handler escapes apostrophes when normalization is disabled"""
    # Mock Config to return normalization disabled
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_setting.return_value = False  # normalization disabled
    
    with patch("algebras.utils.android_xml_handler.Config", return_value=mock_config):
        # Test the escape function directly
        result = _escape_xml_text("Ko'proq matn")
        assert result == "Ko\\'proq matn"  # Should escape apostrophes


def test_android_xml_write_with_normalization():
    """Test full write/read cycle with normalization enabled"""
    # Mock Config to return normalization enabled
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_setting.return_value = True  # normalization enabled
    
    with patch("algebras.utils.android_xml_handler.Config", return_value=mock_config):
        # Test data with apostrophes
        content = {
            "test_key": "Ko'proq matn",
            "another_key": "Salom 'dunyo'"
        }
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            temp_file = f.name
        
        try:
            write_android_xml_file(temp_file, content)
            
            # Read the file content directly to check XML format
            with open(temp_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Check that apostrophes are NOT escaped in the XML
            assert "Ko'proq matn" in xml_content
            assert "Salom 'dunyo'" in xml_content
            assert "Ko\\'proq" not in xml_content  # Should not contain escaped apostrophes
            
            # Read back using the handler
            read_content = read_android_xml_file(temp_file)
            
            # Should match original content
            assert read_content["test_key"] == "Ko'proq matn"
            assert read_content["another_key"] == "Salom 'dunyo'"
            
        finally:
            os.unlink(temp_file)


def test_android_xml_no_config():
    """Test that Android XML handler defaults to normalization enabled when no config exists"""
    # Mock Config to return no config file
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = False
    
    with patch("algebras.utils.android_xml_handler.Config", return_value=mock_config):
        # Test the escape function directly
        result = _escape_xml_text("Ko'proq matn")
        assert result == "Ko'proq matn"  # Should NOT escape apostrophes (default to normalization enabled) 