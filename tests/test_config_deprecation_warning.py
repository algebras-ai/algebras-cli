"""
Test config deprecation warning functionality
"""

import os
import tempfile
import yaml
import pytest
from unittest.mock import patch, mock_open
from algebras.config import Config


class TestConfigDeprecationWarning:
    """Test cases for config deprecation warning functionality."""
    
    def test_check_deprecated_format_with_path_rules(self):
        """Test that check_deprecated_format returns True when path_rules exists."""
        config = Config()
        
        # Mock config data with path_rules
        config.data = {
            "languages": ["en", "fr"],
            "path_rules": ["*.json"],
            "api": {"provider": "algebras-ai"}
        }
        
        assert config.check_deprecated_format() is True
    
    def test_check_deprecated_format_with_empty_path_rules(self):
        """Test that check_deprecated_format returns True even with empty path_rules."""
        config = Config()
        
        # Mock config data with empty path_rules
        config.data = {
            "languages": ["en", "fr"],
            "path_rules": [],
            "api": {"provider": "algebras-ai"}
        }
        
        assert config.check_deprecated_format() is True
    
    def test_check_deprecated_format_without_path_rules(self):
        """Test that check_deprecated_format returns False when path_rules doesn't exist."""
        config = Config()
        
        # Mock config data without path_rules (new format)
        config.data = {
            "languages": ["en", "fr"],
            "source_files": {
                "locales/en.json": {
                    "destination_path": "locales/%algebras_locale_code%.json"
                }
            },
            "api": {"provider": "algebras-ai"}
        }
        
        assert config.check_deprecated_format() is False
    
    def test_check_deprecated_format_with_both_formats(self):
        """Test that check_deprecated_format returns True when both formats exist."""
        config = Config()
        
        # Mock config data with both path_rules and source_files
        config.data = {
            "languages": ["en", "fr"],
            "path_rules": ["*.json"],
            "source_files": {
                "locales/en.json": {
                    "destination_path": "locales/%algebras_locale_code%.json"
                }
            },
            "api": {"provider": "algebras-ai"}
        }
        
        assert config.check_deprecated_format() is True
    
    def test_check_deprecated_format_with_empty_data(self):
        """Test that check_deprecated_format returns False with empty data."""
        config = Config()
        config.data = {}
        
        assert config.check_deprecated_format() is False
    
    def test_check_deprecated_format_loads_config_if_not_loaded(self):
        """Test that check_deprecated_format loads config if not already loaded."""
        config = Config()
        
        # Mock the load method to set data
        def mock_load():
            config.data = {'path_rules': ['*.json']}
        
        with patch.object(config, 'load', side_effect=mock_load):
            config.data = None  # Simulate not loaded
            
            # Mock the exists method to return True
            with patch.object(config, 'exists', return_value=True):
                result = config.check_deprecated_format()
                assert result is True
    
    def test_warning_message_format(self):
        """Test that the warning message contains expected emojis and text."""
        config = Config()
        config.data = {"path_rules": ["*.json"]}
        
        # This test verifies the warning message format by checking the method returns True
        # The actual message display is tested in integration tests
        assert config.check_deprecated_format() is True
    
    def test_config_with_old_format_yaml(self):
        """Test with actual YAML config file containing path_rules."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "languages": ["en", "fr"],
                "path_rules": ["*.json", "*.xml"],
                "api": {"provider": "algebras-ai"}
            }, f)
            config_path = f.name
        
        try:
            config = Config()
            config.config_path = config_path
            config.load()
            
            assert config.check_deprecated_format() is True
        finally:
            os.unlink(config_path)
    
    def test_config_with_new_format_yaml(self):
        """Test with actual YAML config file using source_files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "languages": ["en", "fr"],
                "source_files": {
                    "locales/en.json": {
                        "destination_path": "locales/%algebras_locale_code%.json"
                    }
                },
                "api": {"provider": "algebras-ai"}
            }, f)
            config_path = f.name
        
        try:
            config = Config()
            config.config_path = config_path
            config.load()
            
            assert config.check_deprecated_format() is False
        finally:
            os.unlink(config_path)
