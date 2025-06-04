"""
Tests for the FileScanner class
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from algebras.config import Config
from algebras.services.file_scanner import FileScanner


class TestFileScanner:
    """Tests for the FileScanner class"""

    def test_init(self, monkeypatch):
        """Test initialization of FileScanner"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_path_rules.return_value = ["**/*.json"]

        # Patch Config class
        monkeypatch.setattr("algebras.services.file_scanner.Config", lambda: mock_config)

        # Initialize FileScanner
        scanner = FileScanner()

        # Verify Config was used correctly
        assert mock_config.exists.called
        assert mock_config.load.called
        assert mock_config.get_path_rules.called
        assert scanner.path_rules == ["**/*.json"]

    def test_init_no_config(self, monkeypatch):
        """Test initialization of FileScanner with no config file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.services.file_scanner.Config", lambda: mock_config)

        # Initialize FileScanner - should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            FileScanner()

    def test_find_localization_files(self, monkeypatch):
        """Test find_localization_files method"""
        # Mock glob and os.path functionality
        file_paths = [
            "messages.json",
            "locales/en.json",
            "node_modules/package/en.json"  # This should be excluded
        ]

        def mock_glob(pattern, recursive=False):
            if pattern == "**/*.json":
                return file_paths
            elif pattern == "**/node_modules/**":
                return ["node_modules/package/en.json"]
            return []

        monkeypatch.setattr("glob.glob", mock_glob)
        monkeypatch.setattr("os.path.isfile", lambda x: True)
        monkeypatch.setattr("os.path.normpath", lambda x: x)

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_path_rules.return_value = ["**/*.json", "!**/node_modules/**"]

        # Patch Config class
        monkeypatch.setattr("algebras.services.file_scanner.Config", lambda: mock_config)

        # Initialize FileScanner
        scanner = FileScanner()

        # Test find_localization_files
        result = scanner.find_localization_files()

        # We should find two files (the node_modules one should be excluded)
        assert len(result) == 2
        assert "messages.json" in result
        assert "locales/en.json" in result
        assert "node_modules/package/en.json" not in result

    def test_group_files_by_language(self, monkeypatch):
        """Test group_files_by_language method"""
        # Mock find_localization_files to return a list of file paths
        file_paths = [
            "messages.en.json",
            "messages.fr.json",
            "locales/en.yaml",
            "locales/de.yaml",
            "generic.json"  # No language marker, should not be grouped with any language
        ]
        
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_path_rules.return_value = ["**/*.json", "**/*.yaml"]
        mock_config.get_languages.return_value = ["en", "fr", "de"]
        mock_config.get_source_language.return_value = "en"
        
        # Patch Config class and find_localization_files method
        monkeypatch.setattr("algebras.services.file_scanner.Config", lambda: mock_config)
        
        # Create scanner with mocked find_localization_files
        scanner = FileScanner()
        scanner.find_localization_files = lambda: file_paths
        
        # Test group_files_by_language
        result = scanner.group_files_by_language()
        
        # Verify the grouping
        assert set(result.keys()) == {"en", "fr", "de"}
        assert set(result["en"]) == {"messages.en.json", "locales/en.yaml"}
        assert set(result["fr"]) == {"messages.fr.json"}
        assert set(result["de"]) == {"locales/de.yaml"} 