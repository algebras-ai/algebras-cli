import json
import os
import tempfile
import glob
import pytest
from unittest.mock import MagicMock, patch

from algebras.commands import translate_command
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.services.translator import Translator


class TestTranslateCommand:
    """Tests for the translate_command module"""
    
    def test_translate_file_paths(self, monkeypatch):
        """Test that file paths are correctly determined for different languages"""
        # Mock configuration
        mock_config = MagicMock(spec=Config)
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        mock_config.get_source_language.return_value = "en"
        
        # Mock translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"key": "translated value"}
        
        # Create temporary directory structure for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to tmpdir first to work with relative paths
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            
            try:
                # Create source directory and file
                en_dir = os.path.join("locales", "en")
                os.makedirs(en_dir, exist_ok=True)
                source_file = os.path.join(en_dir, "common.json")
                
                with open(source_file, "w") as f:
                    json.dump({"key": "value"}, f)
                
                # Create directories for target languages
                fr_dir = os.path.join("locales", "fr")
                es_dir = os.path.join("locales", "es")
                os.makedirs(fr_dir, exist_ok=True)
                os.makedirs(es_dir, exist_ok=True)
                
                # Mock file scanner to return our test file
                mock_scanner = MagicMock(spec=FileScanner)
                mock_scanner.group_files_by_language.return_value = {
                    "en": [source_file],
                    "fr": [],
                    "es": []
                }
                
                # Mock the path functions to ensure consistent paths
                # We'll use a modified version of determine_target_path that just switches the language directory
                def mock_determine_target_path(source_path, source_lang, target_lang):
                    return source_path.replace(f"/{source_lang}/", f"/{target_lang}/")
                
                # Apply monkeypatches
                monkeypatch.setattr("algebras.commands.translate_command.Config", lambda: mock_config)
                monkeypatch.setattr("algebras.commands.translate_command.FileScanner", lambda: mock_scanner)
                monkeypatch.setattr("algebras.commands.translate_command.Translator", lambda: mock_translator)
                monkeypatch.setattr("algebras.utils.path_utils.determine_target_path", mock_determine_target_path)
                
                # Call the function
                translate_command.execute(force=True)
                
                # Files should preserve their original names since they're in language-specific directories
                fr_target = os.path.join(fr_dir, "common.json")
                es_target = os.path.join(es_dir, "common.json")
                
                # Check that files were created
                assert os.path.exists(fr_target), f"French file not found: {fr_target}"
                assert os.path.exists(es_target), f"Spanish file not found: {es_target}"
                
                # Verify content
                with open(fr_target, "r") as f:
                    fr_content = json.load(f)
                    assert fr_content == {"key": "translated value"}
                    
                with open(es_target, "r") as f:
                    es_content = json.load(f)
                    assert es_content == {"key": "translated value"}
                    
            finally:
                os.chdir(original_cwd)

    def test_preserve_filename_in_language_directories(self, monkeypatch):
        """Test that files in language-specific directories preserve their original filenames"""
        # Mock configuration
        mock_config = MagicMock(spec=Config)
        mock_config.get_languages.return_value = ["en", "ar"]
        mock_config.get_source_language.return_value = "en"
        
        # Mock translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"app_name": "تطبيق"}
        
        # Create temporary directory structure for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to tmpdir first to work with relative paths
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            
            try:
                # Test case 1: Android XML files
                android_en_dir = os.path.join("Android", "en")
                os.makedirs(android_en_dir, exist_ok=True)
                android_source = os.path.join(android_en_dir, "generic_strings.xml")
                
                with open(android_source, "w") as f:
                    f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <string name="app_name">App</string>\n</resources>')
                
                # Test case 2: iOS strings files  
                ios_en_dir = os.path.join("iOS", "en")
                os.makedirs(ios_en_dir, exist_ok=True)
                ios_source = os.path.join(ios_en_dir, "Localizable.strings")
                
                with open(ios_source, "w") as f:
                    f.write('"app_name" = "App";')
                
                # Create target directories
                android_ar_dir = os.path.join("Android", "ar")
                ios_ar_dir = os.path.join("iOS", "ar")
                os.makedirs(android_ar_dir, exist_ok=True)
                os.makedirs(ios_ar_dir, exist_ok=True)
                
                # Mock file scanner to return our test files
                mock_scanner = MagicMock(spec=FileScanner)
                mock_scanner.group_files_by_language.return_value = {
                    "en": [android_source, ios_source],
                    "ar": []
                }
                
                # Mock the path functions to ensure consistent paths
                def mock_determine_target_path(source_path, source_lang, target_lang):
                    return source_path.replace(f"/{source_lang}/", f"/{target_lang}/")
                
                # Apply monkeypatches
                monkeypatch.setattr("algebras.commands.translate_command.Config", lambda: mock_config)
                monkeypatch.setattr("algebras.commands.translate_command.FileScanner", lambda: mock_scanner)
                monkeypatch.setattr("algebras.commands.translate_command.Translator", lambda: mock_translator)
                monkeypatch.setattr("algebras.utils.path_utils.determine_target_path", mock_determine_target_path)
                
                # Call the function
                translate_command.execute(force=True)
                
                # Check that files were created with correct names (no language suffixes)
                android_target = os.path.join(android_ar_dir, "generic_strings.xml")  # NOT generic_strings.ar.xml
                ios_target = os.path.join(ios_ar_dir, "Localizable.strings")  # NOT Localizable.ar.strings
                
                assert os.path.exists(android_target), f"Android target file not found: {android_target}"
                assert os.path.exists(ios_target), f"iOS target file not found: {ios_target}"
                
                # Verify that files with language suffixes were NOT created
                android_wrong = os.path.join(android_ar_dir, "generic_strings.ar.xml")
                ios_wrong = os.path.join(ios_ar_dir, "Localizable.ar.strings")
                
                assert not os.path.exists(android_wrong), f"Android file with language suffix should not exist: {android_wrong}"
                assert not os.path.exists(ios_wrong), f"iOS file with language suffix should not exist: {ios_wrong}"
                
            finally:
                os.chdir(original_cwd) 