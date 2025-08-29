"""
Tests for the status command
"""

import os
from unittest.mock import patch, MagicMock

import pytest
import click
from click.testing import CliRunner

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
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json", "labels.en.json"],
            "fr": ["messages.fr.json"],
            "es": ["messages.es.json", "labels.es.json"]
        }
        
        # Patch dependencies and file operations
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.getmtime", return_value=1000), \
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
            mock_echo.assert_any_call(f"fr: {click.style('1/2 files (50.0%)', fg='yellow')}")
            mock_echo.assert_any_call(f"es: {click.style('2/2 files (100.0%)', fg='green')}")

    def test_execute_status_single_language(self):
        """Test execute status for a specific language"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        mock_config.get_source_language.return_value = "en"
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json", "labels.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Patch dependencies and file operations
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.getmtime", return_value=1000), \
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
            mock_echo.assert_any_call(f"fr: {click.style('1/2 files (50.0%)', fg='yellow')}")
            
            # Verify that es language is not in the output
            assert not any(call.args[0].endswith("es:") for call in mock_echo.call_args_list)

    def test_execute_detect_outdated_files(self):
        """Test execute with outdated files"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        
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
            mock_execute.assert_called_once_with(None)
            
            # Test with language option
            result = runner.invoke(status, ["--language", "fr"])
            
            # Verify the command executed successfully
            assert result.exit_code == 0
            
            # Verify execute was called with the right arguments
            mock_execute.assert_called_with("fr") 