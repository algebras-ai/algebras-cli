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
        mock_config.check_deprecated_format.return_value = False
        
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
        mock_config.check_deprecated_format.return_value = False
        
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
        mock_config.get_source_language.return_value = "en"
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {"en": [], "fr": []}
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo, \
             patch("algebras.commands.translate_command.Translator") as mock_translator_class:
            
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
        mock_config.get_source_language.return_value = "en"

        # Set up source and target paths
        source_file = "public/locales/en/messages.json"
        target_file = "public/locales/fr/messages.json"
        source_basename = "messages.json"  # The base filename without language code
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": []
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"welcome": "Bienvenue"}

        # Mock the utility functions and file operations
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.Translator", return_value=mock_translator), \
             patch("builtins.open", mock_open()), \
             patch("os.path.exists", return_value=False), \
             patch("os.path.getmtime", return_value=0), \
             patch("os.makedirs", return_value=None), \
             patch("json.dump") as mock_json_dump, \
             patch("algebras.commands.translate_command.click.echo") as mock_echo, \
             patch("algebras.commands.translate_command.determine_target_path", return_value=target_file), \
             patch("os.path.dirname", return_value="public/locales/fr"), \
             patch("os.path.basename", return_value=source_basename), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.relpath", return_value=source_file), \
             patch("builtins.print") as mock_print:  # Mock print to avoid output in terminal

            # Call execute
            translate_command.execute()

            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify translation was attempted - should use translate_file
            assert mock_translator.translate_file.called

            # Verify output messages (updated to match actual implementation with raw color codes)
            mock_echo.assert_any_call("\x1b[32mFound 1 source files for language 'en'.\x1b[0m")
            mock_echo.assert_any_call("\n\x1b[34mTranslating to fr...\x1b[0m")

    def test_execute_skip_uptodate(self):
        """Test execute with up-to-date files (should skip)"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.config_path = "/path/to/.algebras.config"
        mock_config.get_source_language.return_value = "en"
        # Make sure load() doesn't actually try to load anything
        mock_config.load.return_value = {"languages": ["en", "fr"]}
        mock_config.data = {"languages": ["en", "fr"]}

        # Set up paths for testing
        source_file = "public/locales/en/messages.json"
        source_basename = "messages.json"
        target_file = "public/locales/fr/messages.json"
        target_basename = "messages.json"
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [target_file]
        }

        # Mock the directory and file paths
        def mock_dirname(path):
            if path == source_file:
                return "public/locales/en"
            return "public/locales/fr"
        
        def mock_basename(path):
            return source_basename
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", side_effect=[1000, 2000]), \
             patch("builtins.open", mock_open()), \
             patch("os.path.dirname", side_effect=mock_dirname), \
             patch("os.path.basename", side_effect=mock_basename), \
             patch("os.makedirs", return_value=None), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.relpath", return_value=source_file), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo, \
             patch("builtins.print") as mock_print, \
             patch("algebras.commands.translate_command.determine_target_path", return_value=target_file):

            # Call execute without force
            translate_command.execute(force=False)

            # Verify output messages (skipping messages)
            mock_echo.assert_any_call(f"{click.style('Found 1 source files for language \'en\'.', fg='green')}")
            
            # Look for skip message
            skipping_message_found = False
            for call_args in mock_echo.call_args_list:
                args, _ = call_args
                if len(args) > 0 and "Skipping" in args[0]:
                    skipping_message_found = True
                    break
            assert skipping_message_found, "No skipping message was logged"

    def test_execute_force_update(self):
        """Test execute with force update (should translate even if up-to-date)"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"

        # Set up paths for testing
        source_file = "public/locales/en/messages.json"
        source_basename = "messages.json"
        target_file = "public/locales/fr/messages.json"
        target_basename = "messages.json"
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [target_file]
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"welcome": "Bienvenue"}

        # Mock the directory and file paths
        def mock_dirname(path):
            if path == source_file:
                return "public/locales/en"
            return "public/locales/fr"
        
        def mock_basename(path):
            return source_basename
        
        # Patch dependencies
        with patch("algebras.commands.translate_command.Config", return_value=mock_config), \
             patch("algebras.commands.translate_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.translate_command.Translator", return_value=mock_translator), \
             patch("builtins.open", mock_open()), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", side_effect=[1000, 2000]), \
             patch("os.path.dirname", side_effect=mock_dirname), \
             patch("os.path.basename", side_effect=mock_basename), \
             patch("os.makedirs", return_value=None), \
             patch("json.dump"), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.relpath", return_value=source_file), \
             patch("algebras.commands.translate_command.determine_target_path", return_value=target_file), \
             patch("algebras.commands.translate_command.click.echo") as mock_echo, \
             patch("builtins.print") as mock_print:

            # Call execute with force=True
            translate_command.execute(force=True)

            # Verify translation was attempted with force
            mock_echo.assert_any_call(f"{click.style('Found 1 source files for language \'en\'.', fg='green')}")
            
            # Check for translation message
            assert mock_translator.translate_file.called, "translate_file was not called"
            
            # Check for translation message content
            translating_message_found = False
            for call_args in mock_echo.call_args_list:
                args, _ = call_args
                if len(args) > 0 and "Translating" in args[0] and "messages.json" in args[0]:
                    translating_message_found = True
                    break
            assert translating_message_found, "No translating message was found"

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
            
            # Verify execute was called with the right arguments (updated with new parameters)
            mock_execute.assert_called_once_with(None, False, False, ui_safe=False, verbose=False, batch_size=None, max_parallel_batches=None, glossary_id=None, prompt_file=None, config_file=None)
            
            # Test with language and force options
            result = runner.invoke(translate, ["--language", "fr", "--force"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_with("fr", True, False, ui_safe=False, verbose=False, batch_size=None, max_parallel_batches=None, glossary_id=None, prompt_file=None, config_file=None)
            
            # Test with ui_safe option
            result = runner.invoke(translate, ["--ui-safe"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_with(None, False, False, ui_safe=True, verbose=False, batch_size=None, max_parallel_batches=None, glossary_id=None, prompt_file=None, config_file=None) 