"""
Test Android values directory structure handling
"""

import tempfile
import os
import json
from unittest.mock import MagicMock, patch

from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.path_utils import determine_target_path


def test_android_values_file_detection():
    """Test that Android values directory files are detected correctly"""
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create Android values structure
        values_dir = os.path.join(tmpdir, "app", "src", "main", "res", "values")
        values_es_dir = os.path.join(tmpdir, "app", "src", "main", "res", "values-es")
        values_ru_dir = os.path.join(tmpdir, "app", "src", "main", "res", "values-ru")
        
        os.makedirs(values_dir, exist_ok=True)
        os.makedirs(values_es_dir, exist_ok=True)
        os.makedirs(values_ru_dir, exist_ok=True)
        
        # Create XML files
        base_strings = os.path.join(values_dir, "strings.xml")
        base_app_strings = os.path.join(values_dir, "app_strings.xml")
        es_strings = os.path.join(values_es_dir, "strings.xml")
        ru_strings = os.path.join(values_ru_dir, "strings.xml")
        
        # Write test XML content
        xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Test App</string>
    <string name="welcome">Welcome</string>
</resources>'''
        
        for file_path in [base_strings, base_app_strings, es_strings, ru_strings]:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
        
        # Create config file
        config_path = os.path.join(tmpdir, ".algebras.config")
        config_data = {
            "languages": ["en", "es", "ru"],
            "path_rules": ["**/*.xml"],
            "api": {"provider": "algebras-ai"}
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        # Change to tmpdir and test file scanner
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            # Mock Config to use our test config
            mock_config = MagicMock(spec=Config)
            mock_config.exists.return_value = True
            mock_config.get_languages.return_value = ["en", "es", "ru"]
            mock_config.get_source_language.return_value = "en"
            mock_config.get_path_rules.return_value = ["**/*.xml"]
            mock_config.get_source_files.return_value = {}
            
            with patch("algebras.services.file_scanner.Config", return_value=mock_config):
                scanner = FileScanner()
                grouped_files = scanner.group_files_by_language()
                
                # Check that files are grouped correctly
                assert "en" in grouped_files
                assert "es" in grouped_files 
                assert "ru" in grouped_files
                
                # Base language files should be in 'en' (source language)
                en_files = grouped_files["en"]
                assert len(en_files) == 2  # strings.xml and app_strings.xml
                assert any(os.path.join("values", "strings.xml") in f for f in en_files)
                assert any(os.path.join("values", "app_strings.xml") in f for f in en_files)
                
                # Translated files should be in respective languages
                es_files = grouped_files["es"]
                assert len(es_files) == 1
                assert any(os.path.join("values-es", "strings.xml") in f for f in es_files)
                
                ru_files = grouped_files["ru"]
                assert len(ru_files) == 1
                assert any(os.path.join("values-ru", "strings.xml") in f for f in ru_files)
                
        finally:
            os.chdir(original_cwd)


def test_android_values_path_determination():
    """Test that Android values paths are determined correctly"""
    # Test base values to target language
    source_path = "app/src/main/res/values/strings.xml"
    target_path = determine_target_path(source_path, "en", "es")
    expected = os.path.join("app", "src", "main", "res", "values-es", "strings.xml")
    assert target_path == expected
    
    # Test preserving filename
    source_path = "app/src/main/res/values/app_strings.xml"
    target_path = determine_target_path(source_path, "en", "ru")
    expected = os.path.join("app", "src", "main", "res", "values-ru", "app_strings.xml")
    assert target_path == expected
    
    # Test values-{lang} to another language
    source_path = "app/src/main/res/values-es/strings.xml"
    target_path = determine_target_path(source_path, "es", "fr")
    expected = os.path.join("app", "src", "main", "res", "values-fr", "strings.xml")
    assert target_path == expected
    
    # Test nested subdirectories
    source_path = "project/mobile/android/app/src/main/res/values/ui_strings.xml"
    target_path = determine_target_path(source_path, "en", "de")
    expected = os.path.join("project", "mobile", "android", "app", "src", "main", "res", "values-de", "ui_strings.xml")
    assert target_path == expected


def test_android_values_priority_over_other_patterns():
    """Test that Android values pattern takes priority over other language patterns"""
    # Test with a file that could match multiple patterns
    source_path = "app/src/main/res/values/strings.en.xml"  # Has both values/ and .en. patterns
    target_path = determine_target_path(source_path, "en", "es")
    
    # Should use Android pattern (values -> values-es) not filename pattern (.en. -> .es.)
    expected = os.path.join("app", "src", "main", "res", "values-es", "strings.en.xml")
    assert target_path == expected


def test_android_values_non_xml_files_ignored():
    """Test that non-XML files in values directories don't get Android treatment"""
    # Non-XML file should use regular path logic
    source_path = "app/src/main/res/values/config.json"
    target_path = determine_target_path(source_path, "en", "es")
    
    # Should not convert to values-es since it's not an XML file
    assert target_path == source_path  # No change expected for non-XML


def test_android_values_file_scanning_patterns():
    """Test that the correct file patterns are included for Android values"""
    mock_config = MagicMock(spec=Config)
    mock_config.exists.return_value = True
    mock_config.get_languages.return_value = ["en", "es"]
    mock_config.get_source_language.return_value = "en"
    mock_config.get_path_rules.return_value = ["**/*.xml"]
    mock_config.get_source_files.return_value = {}
    
    with patch("algebras.services.file_scanner.Config", return_value=mock_config):
        scanner = FileScanner()
        
        # Check that Android patterns are included in the specific patterns
        # We can't easily test the internal patterns, but we can verify that 
        # find_localization_files would include Android-style paths
        
        # Mock glob.glob to return test files
        with patch("glob.glob") as mock_glob:
            test_files = [
                "app/src/main/res/values/strings.xml",
                "app/src/main/res/values-es/strings.xml",
                "res/values/app_strings.xml",
                "values/ui_strings.xml"
            ]
            mock_glob.return_value = test_files
            
            found_files = scanner.find_localization_files()
            
            # Verify that Android patterns would be searched
            # (glob.glob should be called with patterns including values patterns)
            assert mock_glob.called
            
            # Check that the call includes our Android patterns
            call_args_list = [call[0][0] for call in mock_glob.call_args_list]
            assert any("**/values/*.xml" in pattern for pattern in call_args_list)
            assert any("**/values-*/*.xml" in pattern for pattern in call_args_list)
