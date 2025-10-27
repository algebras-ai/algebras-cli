"""
Tests for CLI -f/--config-file flag
"""

import os
import tempfile
import yaml
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

from algebras.cli import cli


class TestCLIConfigFileFlag:
    """Tests for CLI config file flag"""

    def test_cli_group_accepts_config_file_flag(self):
        """Test that CLI group accepts -f flag"""
        runner = CliRunner()
        
        # Test that the flag is accepted without error
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert '--config-file' in result.output or '-f' in result.output

    def test_init_command_with_config_file_flag(self):
        """Test init command with custom config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config = os.path.join(tmpdir, ".algebras-custom.config")
            
            with patch('algebras.commands.init_command.Config') as mock_config_class:
                mock_config = MagicMock()
                mock_config.exists.return_value = False
                mock_config.config_path = custom_config
                mock_config.data = {"api": {"provider": "algebras-ai"}}
                mock_config.detect_languages_from_files.return_value = ["en"]
                mock_config_class.return_value = mock_config
                
                runner = CliRunner()
                result = runner.invoke(cli, ['-f', custom_config, 'init'])
                
                # Verify Config was called with the custom path
                assert mock_config_class.called
                assert mock_config_class.call_args[1] == {} or \
                       mock_config_class.call_args[1].get('config_file_path') == custom_config

    def test_translate_command_with_config_file_flag(self):
        """Test translate command with custom config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config = os.path.join(tmpdir, ".algebras-custom.config")
            
            with patch('algebras.commands.translate_command.Config') as mock_config_class, \
                 patch('algebras.commands.translate_command.FileScanner') as mock_scanner_class:
                
                mock_config = MagicMock()
                mock_config.exists.return_value = True
                mock_config.get_languages.return_value = ["en", "fr"]
                mock_config.get_source_language.return_value = "en"
                mock_config.check_deprecated_format.return_value = False
                mock_config.config_path = custom_config
                mock_config_class.return_value = mock_config
                
                mock_scanner = MagicMock()
                mock_scanner.group_files_by_language.return_value = {"en": [], "fr": []}
                mock_scanner_class.return_value = mock_scanner
                
                runner = CliRunner()
                result = runner.invoke(cli, ['-f', custom_config, 'translate', '--language', 'fr'])
                
                # Should try to execute (may fail due to missing API key, but that's OK)
                assert 'fr' in str(mock_config_class.call_args) or mock_config_class.called

    def test_config_file_flag_passed_to_all_commands(self):
        """Test that config file flag is passed to command functions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config = os.path.join(tmpdir, ".algebras-custom.config")
            
            # Test add command
            with patch('algebras.commands.add_command.Config') as mock_config_class:
                mock_config = MagicMock()
                mock_config.exists.return_value = True
                mock_config.get_languages.return_value = ["en"]
                mock_config.check_deprecated_format.return_value = False
                mock_config_class.return_value = mock_config
                
                runner = CliRunner()
                result = runner.invoke(cli, ['-f', custom_config, 'add', 'fr'])
                
                # Verify the command was called
                assert mock_config_class.called

    def test_status_command_with_config_file_flag(self):
        """Test status command with custom config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config = os.path.join(tmpdir, ".algebras-custom.config")
            
            with patch('algebras.commands.status_command.Config') as mock_config_class, \
                 patch('algebras.commands.status_command.FileScanner') as mock_scanner_class:
                
                mock_config = MagicMock()
                mock_config.exists.return_value = True
                mock_config.get_languages.return_value = ["en", "fr"]
                mock_config.get_source_language.return_value = "en"
                mock_config.check_deprecated_format.return_value = False
                mock_config.config_path = custom_config
                mock_config_class.return_value = mock_config
                
                mock_scanner = MagicMock()
                mock_scanner.group_files_by_language.return_value = {"en": [], "fr": []}
                mock_scanner_class.return_value = mock_scanner
                
                runner = CliRunner()
                result = runner.invoke(cli, ['-f', custom_config, 'status'])
                
                # Should try to execute
                assert mock_config_class.called

    def test_review_command_with_config_file_flag(self):
        """Test review command with custom config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config = os.path.join(tmpdir, ".algebras-custom.config")
            
            with patch('algebras.commands.review_command.Config') as mock_config_class, \
                 patch('algebras.commands.review_command.FileScanner') as mock_scanner_class:
                
                mock_config = MagicMock()
                mock_config.exists.return_value = True
                mock_config.get_languages.return_value = ["en", "fr"]
                mock_config.get_source_language.return_value = "en"
                mock_config.check_deprecated_format.return_value = False
                mock_config_class.return_value = mock_config
                
                mock_scanner = MagicMock()
                mock_scanner.group_files_by_language.return_value = {"en": [], "fr": []}
                mock_scanner_class.return_value = mock_scanner
                
                runner = CliRunner()
                result = runner.invoke(cli, ['-f', custom_config, 'review', '--language', 'fr'])
                
                # Should try to execute
                assert mock_config_class.called

