"""
Tests for the translate command
"""

import os
import json
from unittest.mock import patch, MagicMock, mock_open

import pytest
import click
from click.testing import CliRunner

from algebras.commands import translate_command
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.services.translator import Translator


class TestTranslateCommand:
    """Tests for the translate command"""

    def test_execute_no_config(self):
        """Test execute with no config file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        
        # Patch Config and click.echo
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute
            translate_command.execute()
            
            # Verify Config was used
            assert mock_config.exists.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('No Algebras configuration found. Run \'algebras init\' first.', fg='red')}")

    def test_execute_only_one_language(self):
        """Test execute with only one language configured"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en"]
        
        # Patch Config and click.echo
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute
            translate_command.execute()
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('Only one language (en) is configured. Add more languages with \'algebras add <language>\'.', fg='yellow')}")

    def test_execute_invalid_language(self):
        """Test execute with invalid language specified"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        
        # Patch Config and click.echo
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute
            translate_command.execute(language="de")
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('Language \'de\' is not configured in your project.', fg='red')}")

    def test_execute_no_source_files(self):
        """Test execute with no source files found"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {"en": [], "fr": []}
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute
            translate_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output message
            mock_echo.assert_called_with(f"{click.style('No source files found for language \'en\'.', fg='yellow')}")

    def test_execute_success(self):
        """Test execute with successful translation"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": []
        }
        
        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"welcome": "Bienvenue"}
        
        # Mock file operations
        mock_file = mock_open()
        mock_file_exists = False
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.Translator", return_value=mock_translator), \
             patch("builtins.open", mock_file), \
             patch("os.path.exists", return_value=mock_file_exists), \
             patch("os.path.getmtime", return_value=0), \
             patch("json.dump") as mock_json_dump, \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute
            translate_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_scanner.group_files_by_language.called
            assert mock_translator.translate_file.called
            
            # Verify translation was performed
            mock_translator.translate_file.assert_called_once_with("messages.en.json", "fr")
            
            # Verify JSON was written
            assert mock_json_dump.called
            
            # Verify output messages
            mock_echo.assert_any_call(f"{click.style('Found 1 source files for language \'en\'.', fg='green')}")
            mock_echo.assert_any_call(f"\n{click.style('Translating to fr...', fg='blue')}")
            mock_echo.assert_any_call(f"  {click.style('Translating messages.en.json to messages.fr.json...', fg='green')}")

    def test_execute_skip_uptodate(self):
        """Test execute with up-to-date files (should skip)"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.config_path = "/path/to/.algebras.config"
        # Make sure load() doesn't actually try to load anything
        mock_config.load.return_value = {"languages": ["en", "fr"]}
        mock_config.data = {"languages": ["en", "fr"]}
        
        # Mock FileScanner to avoid it trying to instantiate a real Config
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", side_effect=[1000, 2000]), \
             patch("builtins.open", mock_open()), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute without force
            translate_command.execute(force=False)
            
            # Verify output messages
            mock_echo.assert_any_call(f"{click.style('Found 1 source files for language \'en\'.', fg='green')}")
            mock_echo.assert_any_call(f"\n{click.style('Translating to fr...', fg='blue')}")
            mock_echo.assert_any_call(f"  {click.style('Skipping messages.fr.json (already up to date)', fg='yellow')}")

    def test_execute_force_update(self):
        """Test execute with force update (should translate even if up-to-date)"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"welcome": "Bienvenue"}
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.Translator", return_value=mock_translator), \
             patch("builtins.open", mock_open()), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", side_effect=[1000, 2000]), \
             patch("json.dump"), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo:
            
            # Call execute with force=True
            translate_command.execute(force=True)
            
            # Verify translation was performed despite file being up-to-date
            mock_translator.translate_file.assert_called_once_with("messages.en.json", "fr")
            
            # Verify output messages
            mock_echo.assert_any_call(f"{click.style('Found 1 source files for language \'en\'.', fg='green')}")
            mock_echo.assert_any_call(f"\n{click.style('Translating to fr...', fg='blue')}")
            mock_echo.assert_any_call(f"  {click.style('Translating messages.en.json to messages.fr.json...', fg='green')}")

    def test_execute_integration(self):
        """Test execute with the CLI runner"""
        # Use a real CLI runner to test the click command
        runner = CliRunner()
        
        # Patch the execute function in translate_command
        with patch("algebras.commands.translate_command.execute") as mock_execute:
            from algebras.cli import translate
            
            # Run the command
            result = runner.invoke(translate)
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_once_with(None, False)
            
            # Test with language and force options
            result = runner.invoke(translate, ["--language", "fr", "--force"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_with("fr", True) 