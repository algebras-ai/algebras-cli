"""
Tests for the status command
"""

import os
from unittest.mock import patch, MagicMock

import pytest
import click
from click.testing import CliRunner
from colorama import Fore

from algebras.commands import status_command
from algebras.config import Config
from algebras.services.file_scanner import FileScanner


class TestStatusCommand:
    """Tests for the status command"""

    def test_execute_no_config(self):
        """Test execute with no config file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        
        # Patch Config and click.echo
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute()
            
            # Verify Config was used
            assert mock_config.exists.called
            
            # Verify output message
            mock_echo.assert_called_once_with(f"{click.style('No Algebras configuration found. Run \'algebras init\' first.', fg='red')}")

    def test_execute_invalid_language(self):
        """Test execute with invalid language specified"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.check_deprecated_format.return_value = False
        
        # Patch Config and click.echo
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute(language="de")
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            
    def test_execute_no_source_files(self):
        """Test execute with no source files found"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {"en": [], "fr": []}
        
        # Patch dependencies
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.get_source_language.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output message
            mock_echo.assert_called_with(f"{click.style('No source files found for language \'en\'.', fg='yellow')}")

    def test_execute_status_all_languages(self):
        """Test execute status for all languages"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None  # Use filename-based matching
        mock_config.check_deprecated_format.return_value = False
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json", "labels.en.json"],
            "fr": ["messages.fr.json"],
            "es": ["messages.es.json", "labels.es.json"]
        }
        
        # Create a side effect function for count_translated_keys to return different values
        # based on the file being processed
        def count_translated_keys_side_effect(file_path, language=None, config=None):
            if "messages.en.json" in file_path:
                return (2, 2)  # 2 translated out of 2 total keys
            elif "labels.en.json" in file_path:
                return (2, 2)  # 2 translated out of 2 total keys
            elif "messages.fr.json" in file_path:
                return (1, 2)  # 1 translated out of 2 total keys
            elif "messages.es.json" in file_path:
                return (2, 2)  # 2 translated out of 2 total keys
            elif "labels.es.json" in file_path:
                return (2, 2)  # 2 translated out of 2 total keys
            else:
                return (0, 0)
        
        # Create a side effect function for count_current_and_outdated_keys
        def count_current_and_outdated_keys_side_effect(source_file, target_file, source_language=None, target_language=None, config=None):
            if "messages.fr.json" in target_file:
                return (1, 0)  # 1 current translated, 0 outdated
            elif "messages.es.json" in target_file:
                return (2, 0)  # 2 current translated, 0 outdated
            elif "labels.es.json" in target_file:
                return (2, 0)  # 2 current translated, 0 outdated
            else:
                return (0, 0)
        
        # Patch dependencies and file operations
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.getmtime", return_value=1000), \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr", "es"], [])), \
             patch("algebras.commands.status_command.count_translated_keys", side_effect=count_translated_keys_side_effect), \
             patch("algebras.commands.status_command.count_current_and_outdated_keys", side_effect=count_current_and_outdated_keys_side_effect), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.get_source_language.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output messages
            mock_echo.assert_any_call(f"\n{click.style('Translation Status', fg='blue')}")
            mock_echo.assert_any_call(f"Source language: en (2 files)")
            # Updated format: shows keys and files
            mock_echo.assert_any_call(f"fr: {click.style('1/2 keys (50.0%) in 1/2 files (50.0%)', fg='yellow')}")
            mock_echo.assert_any_call(f"es: {click.style('4/4 keys (100.0%) in 2/2 files (100.0%)', fg='green')}")

    def test_execute_status_single_language(self):
        """Test execute status for a specific language"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None  # Use filename-based matching
        mock_config.check_deprecated_format.return_value = False
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json", "labels.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Create a side effect function for count_translated_keys to return different values
        # based on the file being processed
        def count_translated_keys_side_effect(file_path, language=None, config=None):
            if "messages.en.json" in file_path:
                return (2, 2)  # 2 translated out of 2 total keys
            elif "labels.en.json" in file_path:
                return (2, 2)  # 2 translated out of 2 total keys
            elif "messages.fr.json" in file_path:
                return (1, 2)  # 1 translated out of 2 total keys
            else:
                return (0, 0)
        
        # Create a side effect function for count_current_and_outdated_keys
        def count_current_and_outdated_keys_side_effect(source_file, target_file, source_language=None, target_language=None, config=None):
            if "messages.fr.json" in target_file:
                return (1, 0)  # 1 current translated, 0 outdated
            else:
                return (0, 0)
        
        # Patch dependencies and file operations
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.getmtime", return_value=1000), \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr", "es"], [])), \
             patch("algebras.commands.status_command.count_translated_keys", side_effect=count_translated_keys_side_effect), \
             patch("algebras.commands.status_command.count_current_and_outdated_keys", side_effect=count_current_and_outdated_keys_side_effect), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute(language="fr")
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.get_source_language.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output messages
            mock_echo.assert_any_call(f"\n{click.style('Translation Status', fg='blue')}")
            mock_echo.assert_any_call(f"Source language: en (2 files)")
            mock_echo.assert_any_call(f"fr: {click.style('1/2 keys (50.0%) in 1/2 files (50.0%)', fg='yellow')}")
            
            # Verify that es language is not in the output
            assert not any(call.args[0].startswith("es:") for call in mock_echo.call_args_list)

    def test_execute_detect_outdated_files(self):
        """Test execute with outdated files"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Patch dependencies and file operations
        # Make source file newer than target file to simulate outdated translation
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.getmtime", side_effect=[2000, 1000]), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.get_source_language.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output messages showing outdated files
            mock_echo.assert_any_call(f"  {click.style('Warning: 1 files are outdated', fg='yellow')}")

    def test_execute_integration(self):
        """Test execute with the CLI runner"""
        # Use a real CLI runner to test the click command
        runner = CliRunner()
        
        # Patch the execute function in status_command
        with patch("algebras.commands.status_command.execute") as mock_execute:
            from algebras.cli import status
            
            # Run the command
            result = runner.invoke(status)
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_once_with(None, None)
            
            # Test with language option
            result = runner.invoke(status, ["--language", "fr"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_with("fr", None)

    def test_count_translated_keys_xlf(self):
        """Test counting translated keys in XLIFF files."""
        from algebras.commands.status_command import count_translated_keys
        from unittest.mock import patch, MagicMock
        
        # Mock read_language_file to return XLIFF data
        xliff_data = {
            'key1': 'translated1',
            'key2': 'translated2',
            'key3': ''  # Empty translation
        }
        
        with patch('algebras.commands.status_command.read_language_file', return_value=xliff_data), \
             patch('os.path.exists', return_value=True):
            
            translated, total = count_translated_keys("messages.xlf")
            
            assert translated == 2  # Only non-empty values
            assert total == 3  # All keys

    def test_count_current_and_outdated_keys_xlf(self):
        """Test counting current and outdated keys for XLIFF files."""
        from algebras.commands.status_command import count_current_and_outdated_keys
        from unittest.mock import patch
        
        source_data = {
            'key1': 'value1',
            'key2': 'value2'
        }
        
        target_data = {
            'key1': 'translated1',
            'key2': '',  # Empty translation
            'key3': 'old_value'  # Outdated key
        }
        
        with patch('algebras.commands.status_command.read_language_file', side_effect=[source_data, target_data]), \
             patch('os.path.exists', return_value=True):
            
            current, outdated = count_current_and_outdated_keys("source.xlf", "target.xlf")
            
            # key1 is translated, key2 is empty (not counted as translated)
            assert current == 1
            # key3 exists in target but not in source
            assert outdated == 1 