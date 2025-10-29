"""
Tests for FileScanner with custom Config instances
"""

from unittest.mock import MagicMock, patch
import pytest

from algebras.config import Config
from algebras.services.file_scanner import FileScanner


class TestFileScannerCustomConfig:
    """Tests for FileScanner with custom Config instances"""

    def test_init_with_custom_config_instance(self):
        """Test FileScanner initialization with custom Config instance"""
        # Create a mock config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_source_files.return_value = {"src/locales/en.json": {"destination_path": "src/locales/%algebras_locale_code%/common.json"}}
        mock_config.get_path_rules.return_value = ["**/*.json"]
        
        # Initialize FileScanner with custom config
        scanner = FileScanner(config=mock_config)
        
        # Verify the custom config was used
        assert scanner.config == mock_config
        assert mock_config.exists.called
        assert mock_config.load.called
        assert mock_config.get_source_files.called
        assert mock_config.get_path_rules.called

    def test_init_without_config_creates_default(self):
        """Test FileScanner creates default Config when none provided"""
        with patch('algebras.services.file_scanner.Config') as mock_config_class:
            mock_config = MagicMock(spec=Config)
            mock_config.exists.return_value = True
            mock_config.get_source_files.return_value = {}
            mock_config.get_path_rules.return_value = []
            mock_config_class.return_value = mock_config
            
            scanner = FileScanner()
            
            # Verify Config was instantiated
            assert mock_config_class.called
            assert scanner.config == mock_config

    def test_find_localization_files_with_custom_config(self):
        """Test find_localization_files with custom config"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_source_files.return_value = {
            "src/locales/en.json": {"destination_path": "src/locales/%algebras_locale_code%/common.json"}
        }
        mock_config.get_path_rules.return_value = []
        
        scanner = FileScanner(config=mock_config)
        
        # Mock os.path.isfile to return True for our test file
        with patch('os.path.isfile', return_value=True), \
             patch('os.path.normpath', side_effect=lambda x: x):
            
            files = scanner.find_localization_files()
            
            # Should include the source file from config
            assert "src/locales/en.json" in files

    def test_group_files_by_language_with_custom_config(self):
        """Test group_files_by_language with custom config"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_source_files.return_value = {}
        mock_config.get_path_rules.return_value = []
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        
        scanner = FileScanner(config=mock_config)
        
        with patch('algebras.services.file_scanner.glob') as mock_glob:
            mock_glob.glob.return_value = []
            
            result = scanner.group_files_by_language()
            
            # Should have entries for both languages
            assert "en" in result
            assert "fr" in result
            assert isinstance(result["en"], list)
            assert isinstance(result["fr"], list)

