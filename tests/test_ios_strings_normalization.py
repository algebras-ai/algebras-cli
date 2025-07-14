"""
Test iOS strings handler normalization behavior
"""

import tempfile
import os
from unittest.mock import patch, MagicMock

from algebras.utils.ios_strings_handler import write_ios_strings_file, read_ios_strings_file, _escape_ios_string
from algebras.config import Config


def test_ios_strings_normalization_enabled():
    """Test that iOS strings handler doesn't escape apostrophes when normalization is enabled"""
    # Mock Config to return normalization enabled
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_setting.return_value = True  # normalization enabled
    
    with patch("algebras.utils.ios_strings_handler.Config", return_value=mock_config):
        # Test the escape function directly
        result = _escape_ios_string("Profil rasmingizni o'zgartirish")
        assert result == "Profil rasmingizni o'zgartirish"  # Should NOT escape apostrophes
        
        # Test with quotes (should still be escaped)
        result = _escape_ios_string('Say "hello"')
        assert result == 'Say \\"hello\\"'  # Should escape quotes


def test_ios_strings_normalization_disabled():
    """Test that iOS strings handler escapes apostrophes when normalization is disabled"""
    # Mock Config to return normalization disabled
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_setting.return_value = False  # normalization disabled
    
    with patch("algebras.utils.ios_strings_handler.Config", return_value=mock_config):
        # Test the escape function directly
        result = _escape_ios_string("Profil rasmingizni o'zgartirish")
        assert result == "Profil rasmingizni o\\'zgartirish"  # Should escape apostrophes


def test_ios_strings_write_with_normalization():
    """Test full write/read cycle with normalization enabled"""
    # Mock Config to return normalization enabled
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_setting.return_value = True  # normalization enabled
    
    with patch("algebras.utils.ios_strings_handler.Config", return_value=mock_config):
        # Test data with apostrophes
        content = {
            "NSCameraUsageDescription": "Profil rasmingizni o'zgartirish uchun.",
            "NSMicrophoneUsageDescription": "Kurs natijalari bilan videolarni yuborish uchun."
        }
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.strings', delete=False) as f:
            temp_file = f.name
        
        try:
            write_ios_strings_file(temp_file, content)
            
            # Read the file content directly to check .strings format
            with open(temp_file, 'r', encoding='utf-8') as f:
                strings_content = f.read()
            
            # Check that apostrophes are NOT escaped in the .strings file
            assert "o'zgartirish" in strings_content
            assert "o\\'zgartirish" not in strings_content  # Should not contain escaped apostrophes
            
            # Read back using the handler
            read_content = read_ios_strings_file(temp_file)
            
            # Should match original content
            assert read_content["NSCameraUsageDescription"] == "Profil rasmingizni o'zgartirish uchun."
            assert read_content["NSMicrophoneUsageDescription"] == "Kurs natijalari bilan videolarni yuborish uchun."
            
        finally:
            os.unlink(temp_file)


def test_ios_strings_no_config():
    """Test that iOS strings handler defaults to normalization enabled when no config exists"""
    # Mock Config to return no config file
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = False
    
    with patch("algebras.utils.ios_strings_handler.Config", return_value=mock_config):
        # Test the escape function directly
        result = _escape_ios_string("Profil rasmingizni o'zgartirish")
        assert result == "Profil rasmingizni o'zgartirish"  # Should NOT escape apostrophes (default to normalization enabled) 