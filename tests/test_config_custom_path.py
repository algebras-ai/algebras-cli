"""
Tests for Config class with custom file paths
"""

import os
import tempfile
import yaml
from unittest.mock import patch, mock_open
import pytest

from algebras.config import Config


class TestConfigCustomPath:
    """Tests for Config class with custom file paths"""

    def test_init_with_default_path(self):
        """Test Config initialization with default path"""
        config = Config()
        assert config.config_path.endswith(".algebras.config")
        assert config.data == {}

    def test_init_with_custom_relative_path(self):
        """Test Config initialization with custom relative path"""
        custom_path = ".algebras-custom.config"
        config = Config(config_file_path=custom_path)
        expected_path = os.path.join(os.getcwd(), custom_path)
        assert config.config_path == expected_path
        assert config.data == {}

    def test_init_with_custom_absolute_path(self):
        """Test Config initialization with custom absolute path"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.config', delete=False) as tmp:
            custom_path = tmp.name
        
        try:
            config = Config(config_file_path=custom_path)
            assert config.config_path == custom_path
            assert config.data == {}
        finally:
            os.unlink(custom_path)

    def test_exists_with_custom_path(self, monkeypatch):
        """Test exists method with custom config path"""
        custom_path = ".algebras-custom.config"
        exists_calls = [False]
        
        def mock_exists(path):
            # Only return True if it's our custom path
            if custom_path in path:
                return exists_calls.pop() if exists_calls else False
            return False
        
        monkeypatch.setattr(os.path, "exists", mock_exists)
        
        # Initially doesn't exist
        config = Config(config_file_path=custom_path)
        assert config.exists() is False
        
        # After adding to exists_calls
        exists_calls.append(True)
        assert config.exists() is True

    def test_load_with_custom_path(self, monkeypatch):
        """Test load method with custom config path"""
        custom_path = ".algebras-custom.config"
        config_data = {
            "languages": ["en", "fr"],
            "api": {"provider": "algebras-ai"},
        }
        yaml_content = yaml.dump(config_data)
        
        exists_calls = [True]
        def mock_exists(path):
            if custom_path in path:
                return exists_calls.pop() if exists_calls else False
            return False
        
        monkeypatch.setattr(os.path, "exists", mock_exists)
        m = mock_open(read_data=yaml_content)
        
        with patch("builtins.open", m):
            config = Config(config_file_path=custom_path)
            result = config.load()
            assert result == config_data
            assert config.data == config_data

    def test_get_languages_with_custom_path(self):
        """Test get_languages with custom config path"""
        custom_path = ".algebras-custom.config"
        config_data = {
            "languages": ["en", "es", "de"],
            "api": {"provider": "algebras-ai"},
        }
        
        # Create config and set data directly
        config = Config(config_file_path=custom_path)
        config.data = config_data
        
        languages = config.get_languages()
        assert languages == ["en", "es", "de"]

    def test_multiple_config_instances_different_paths(self):
        """Test that multiple Config instances can use different paths"""
        config1 = Config()
        config2 = Config(config_file_path=".algebras-second.config")
        
        # Both should have different paths
        assert config1.config_path != config2.config_path
        assert config1.config_path.endswith(".algebras.config")
        assert config2.config_path.endswith(".algebras-second.config")

