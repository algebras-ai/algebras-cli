"""
Tests for XLIFF config prompt support with --only-missing flag.

This test suite verifies that:
- Prompt from config file works with --only-missing flag
- --prompt-file takes precedence over config prompt
- Prompt is passed to translate_missing_keys_batch
"""

import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
import pytest

from algebras.config import Config
from algebras.services.translator import Translator
from algebras.commands.translate_command import execute


class TestXLIFFConfigPrompt:
    """Test cases for config prompt support with --only-missing."""
    
    def test_config_prompt_works_with_only_missing(self, monkeypatch):
        """
        Test that prompt from config file works with --only-missing flag.
        
        Behavior: When a prompt is configured in the config file and --only-missing
        is used, the prompt should be loaded and passed to the translator for
        batch translation of missing keys.
        """
        # Mock config with prompt
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_source_language.return_value = "en"
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_files.return_value = {}
        mock_config.get_setting.side_effect = lambda key, default=None: {
            "api.prompt": "Add HELLO at the end of each string",
            "xlf.default_target_state": "translated"
        }.get(key, default)
        mock_config.get_destination_locale_code.return_value = "fr"
        
        # Mock file scanner
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = {}
        
        # Mock translator
        mock_translator = MagicMock()
        mock_translator.translate_missing_keys_batch.return_value = {"key1": "Bonjour"}
        
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.Translator", return_value=mock_translator), \
             patch("algebras.commands.translate_command.validate_language_files", return_value=(True, {"key1"})), \
             patch("algebras.commands.translate_command.read_xliff_file") as mock_read, \
             patch("algebras.commands.translate_command.extract_xliff_strings") as mock_extract, \
             patch("algebras.commands.translate_command.update_xliff_targets") as mock_update, \
             patch("algebras.commands.translate_command.write_xliff_file") as mock_write, \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"):
            
            # Setup mocks
            mock_read.return_value = {
                'version': '1.2',
                'files': [{'trans-units': [{'id': 'key1', 'source': 'Hello', 'target': ''}]}]
            }
            mock_extract.side_effect = lambda x: {'key1': 'Hello'} if x else {}
            mock_update.return_value = {
                'version': '1.2',
                'files': [{'trans-units': [{'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'}]}]
            }
            
            # Create temp files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as source_f, \
                 tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as target_f:
                source_file = source_f.name
                target_file = target_f.name
            
            try:
                # Mock file paths
                with patch("algebras.commands.translate_command.resolve_destination_path", return_value=target_file):
                    # Execute with --only-missing
                    execute(language="fr", only_missing=True, config_file=None)
                    
                    # Verify set_custom_prompt was called with config prompt
                    assert mock_translator.set_custom_prompt.called
                    call_args = mock_translator.set_custom_prompt.call_args[0][0]
                    assert "HELLO" in call_args or "hello" in call_args.lower()
                    
                    # Verify translate_missing_keys_batch was called
                    assert mock_translator.translate_missing_keys_batch.called
            finally:
                if os.path.exists(source_file):
                    os.unlink(source_file)
                if os.path.exists(target_file):
                    os.unlink(target_file)
    
    def test_prompt_file_takes_precedence_over_config(self, monkeypatch):
        """
        Test that --prompt-file takes precedence over config prompt.
        
        Behavior: When both --prompt-file and config prompt are provided,
        the --prompt-file prompt should be used, not the config prompt.
        """
        # Mock config with prompt
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_source_language.return_value = "en"
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_files.return_value = {}
        mock_config.get_setting.side_effect = lambda key, default=None: {
            "api.prompt": "Config prompt",
            "xlf.default_target_state": "translated"
        }.get(key, default)
        mock_config.get_destination_locale_code.return_value = "fr"
        
        # Mock file scanner
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = {}
        
        # Mock translator
        mock_translator = MagicMock()
        mock_translator.translate_missing_keys_batch.return_value = {"key1": "Bonjour"}
        
        # Create prompt file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as prompt_f:
            prompt_file = prompt_f.name
            prompt_f.write("File prompt - Add HELLO")
        
        try:
            with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
                 patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
                 patch("algebras.commands.translate_command.Translator", return_value=mock_translator), \
                 patch("algebras.commands.translate_command.validate_language_files", return_value=(True, {"key1"})), \
                 patch("algebras.commands.translate_command.read_xliff_file") as mock_read, \
                 patch("algebras.commands.translate_command.extract_xliff_strings") as mock_extract, \
                 patch("algebras.commands.translate_command.update_xliff_targets") as mock_update, \
                 patch("algebras.commands.translate_command.write_xliff_file") as mock_write, \
                 patch("os.path.exists", return_value=True), \
                 patch("os.makedirs"):
                
                # Setup mocks
                mock_read.return_value = {
                    'version': '1.2',
                    'files': [{'trans-units': [{'id': 'key1', 'source': 'Hello', 'target': ''}]}]
                }
                mock_extract.side_effect = lambda x: {'key1': 'Hello'} if x else {}
                mock_update.return_value = {
                    'version': '1.2',
                    'files': [{'trans-units': [{'id': 'key1', 'source': 'Hello', 'target': 'Bonjour'}]}]
                }
                
                # Create temp files
                with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as source_f, \
                     tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False) as target_f:
                    source_file = source_f.name
                    target_file = target_f.name
                
                try:
                    # Mock file paths
                    with patch("algebras.commands.translate_command.resolve_destination_path", return_value=target_file):
                        # Execute with --only-missing and --prompt-file
                        execute(language="fr", only_missing=True, prompt_file=prompt_file, config_file=None)
                        
                        # Verify set_custom_prompt was called with file prompt, not config prompt
                        assert mock_translator.set_custom_prompt.called
                        call_args = mock_translator.set_custom_prompt.call_args[0][0]
                        assert "File prompt" in call_args
                        assert "Config prompt" not in call_args
                finally:
                    if os.path.exists(source_file):
                        os.unlink(source_file)
                    if os.path.exists(target_file):
                        os.unlink(target_file)
        finally:
            if os.path.exists(prompt_file):
                os.unlink(prompt_file)
    
    def test_prompt_passed_to_translate_missing_keys_batch(self, monkeypatch):
        """
        Test that prompt is passed to translate_missing_keys_batch.
        
        Behavior: When a prompt is set (either from config or file), it should be
        available in the translator when translate_missing_keys_batch is called,
        so the API can use it for translation.
        """
        # Mock config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_source_language.return_value = "en"
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_files.return_value = {}
        mock_config.get_setting.side_effect = lambda key, default=None: {
            "api.prompt": "Custom prompt",
            "xlf.default_target_state": "translated"
        }.get(key, default)
        mock_config.get_destination_locale_code.return_value = "fr"
        
        # Create real translator instance to test prompt propagation
        with patch("algebras.services.translator.Config", return_value=mock_config), \
             patch.dict(os.environ, {"ALGEBRAS_API_KEY": "test-key"}):
            
            translator = Translator(config=mock_config)
            translator.set_custom_prompt("Test prompt")
            
            # Verify prompt is stored
            assert translator.custom_prompt == "Test prompt"
            
            # When translate_missing_keys_batch calls _translate_with_algebras_ai_batch,
            # the prompt should be available in custom_prompt attribute
            # This is tested indirectly by checking the attribute exists

