"""
Tests for the Config class
"""

import os
import tempfile
from unittest.mock import patch, mock_open

import pytest
import yaml

from algebras.config import Config


class TestConfig:
    """Tests for the Config class"""

    def test_init(self):
        """Test initialization of Config"""
        config = Config()
        assert config.config_path.endswith(".algebras.config")
        assert config.data == {}

    def test_exists_true(self, monkeypatch):
        """Test exists method when config file exists"""
        monkeypatch.setattr(os.path, "exists", lambda x: True)
        config = Config()
        assert config.exists() is True

    def test_exists_false(self, monkeypatch):
        """Test exists method when config file doesn't exist"""
        monkeypatch.setattr(os.path, "exists", lambda x: False)
        config = Config()
        assert config.exists() is False

    def test_load_file_not_found(self, monkeypatch):
        """Test load method when config file doesn't exist"""
        monkeypatch.setattr(os.path, "exists", lambda x: False)
        config = Config()
        with pytest.raises(FileNotFoundError):
            config.load()

    def test_load_empty_file(self, monkeypatch):
        """Test load method with empty config file"""
        monkeypatch.setattr(os.path, "exists", lambda x: True)
        m = mock_open(read_data="")
        with patch("builtins.open", m):
            config = Config()
            result = config.load()
            assert result == {}
            assert config.data == {}

    def test_load_valid_file(self, monkeypatch):
        """Test load method with valid config file"""
        # Sample config data
        config_data = {
            "languages": ["en", "fr"],
            "path_rules": ["**/*.json", "!**/node_modules/**"],
            "api": {"provider": "openai", "model": "gpt-4"},
        }
        yaml_content = yaml.dump(config_data)

        monkeypatch.setattr(os.path, "exists", lambda x: True)
        m = mock_open(read_data=yaml_content)
        with patch("builtins.open", m):
            config = Config()
            result = config.load()
            assert result == config_data
            assert config.data == config_data

    def test_save(self):
        """Test save method"""
        config = Config()
        config.data = {
            "languages": ["en", "fr"],
            "path_rules": ["**/*.json"],
        }

        m = mock_open()
        with patch("builtins.open", m):
            config.save()
            m.assert_called_once_with(config.config_path, "w", encoding="utf-8")
            handle = m()
            # Check that yaml.dump was called with the data
            # This is a simplified check since we can't easily verify the exact YAML content
            assert handle.write.called

    def test_create_default(self, monkeypatch):
        """Test create_default method"""
        # Mock exists to return False, then True after save is called
        exists_calls = [False, True]
        monkeypatch.setattr(os.path, "exists", lambda x: exists_calls.pop(0))
        
        # Mock save method
        save_called = [False]

        def mock_save():
            save_called[0] = True

        config = Config()
        config.save = mock_save
        
        # Call create_default
        config.create_default()
        
        # Verify save was called and data was set correctly
        assert save_called[0] is True
        assert "languages" in config.data
        assert "en" in config.data["languages"]
        assert "path_rules" in config.data
        assert "api" in config.data
        assert config.data["api"]["provider"] == "algebras-ai"

    def test_get_languages_empty(self, monkeypatch):
        """Test get_languages with empty config"""
        config = Config()
        config.data = {}
        # Mock exists() to return False to prevent loading the actual config file
        monkeypatch.setattr(config, 'exists', lambda: False)
        assert config.get_languages() == []

    def test_get_languages(self):
        """Test get_languages with languages in config"""
        config = Config()
        config.data = {"languages": ["en", "fr", "es"]}
        assert config.get_languages() == ["en", "fr", "es"]

    def test_add_language_new(self):
        """Test add_language with a new language"""
        config = Config()
        config.data = {"languages": ["en"]}
        
        # Mock save method
        save_called = [False]

        def mock_save():
            save_called[0] = True

        config.save = mock_save
        
        # Add new language
        config.add_language("fr")
        
        # Verify language was added and save was called
        assert "fr" in config.data["languages"]
        assert save_called[0] is True

    def test_add_language_existing(self):
        """Test add_language with an existing language"""
        config = Config()
        config.data = {"languages": ["en", "fr"]}
        
        # Mock save method
        save_called = [False]

        def mock_save():
            save_called[0] = True

        config.save = mock_save
        
        # Add existing language
        config.add_language("fr")
        
        # Verify save was not called (no changes to make)
        assert save_called[0] is False
        assert config.data["languages"] == ["en", "fr"]

    def test_get_path_rules_empty(self, monkeypatch):
        """Test get_path_rules with empty config"""
        config = Config()
        config.data = {}
        # Mock exists() to return False to prevent loading the actual config file
        monkeypatch.setattr(config, 'exists', lambda: False)
        assert config.get_path_rules() == []

    def test_get_path_rules(self):
        """Test get_path_rules with rules in config"""
        config = Config()
        path_rules = ["**/*.json", "!**/node_modules/**"]
        config.data = {"path_rules": path_rules}
        assert config.get_path_rules() == path_rules

    def test_get_api_config_empty(self, monkeypatch):
        """Test get_api_config with empty config"""
        config = Config()
        config.data = {}
        # Mock exists() to return False to prevent loading the actual config file
        monkeypatch.setattr(config, 'exists', lambda: False)
        assert config.get_api_config() == {}

    def test_get_api_config(self):
        """Test get_api_config with API config in config"""
        config = Config()
        api_config = {"provider": "openai", "model": "gpt-4"}
        config.data = {"api": api_config}
        assert config.get_api_config() == api_config 