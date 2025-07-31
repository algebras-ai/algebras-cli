"""
Tests for the status command
"""

import os
from unittest.mock import patch, MagicMock
import tempfile
import json

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
             patch("algebras.commands.status_command.click.echo") as mock_echo, \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr"], [])):
            
            # Call execute
            status_command.execute(language="de")
            
            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            
            # Verify output message - should be the last call since there's also a warning about API key
            mock_echo.assert_any_call(f"{click.style('Language \'de\' is not configured in your project.', fg='red')}")

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
             patch("algebras.commands.status_command.click.echo") as mock_echo, \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr"], [])):
            
            # Call execute
            status_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.get_source_language.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output message
            mock_echo.assert_any_call(f"{click.style('No source files found for language \'en\'.', fg='yellow')}")

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
             patch("os.path.exists", return_value=True), \
             patch("algebras.commands.status_command.count_translated_keys", return_value=(5, 10)), \
             patch("algebras.commands.status_command.count_current_and_outdated_keys", return_value=(5, 0)), \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr", "es"], [])), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute()
            
            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_config.get_source_language.called
            assert mock_scanner.group_files_by_language.called
            
            # Verify output messages - now checking for the new format with key counts
            mock_echo.assert_any_call(f"\n{click.style('Translation Status', fg='blue')}")
            mock_echo.assert_any_call(f"Source language: en (2 files)")
            # Check for the new format: "5/10 keys (50.0%) in 1/2 files (50.0%)"
            found_fr_output = False
            found_es_output = False
            for call_args in mock_echo.call_args_list:
                args, _ = call_args
                if len(args) > 0:
                    if "fr:" in args[0] and "50.0%" in args[0]:
                        found_fr_output = True
                    elif "es:" in args[0] and "100.0%" in args[0]:
                        found_es_output = True
            assert found_fr_output, "Did not find expected fr output"
            assert found_es_output, "Did not find expected es output"

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
             patch("os.path.exists", return_value=True), \
             patch("algebras.commands.status_command.count_translated_keys", return_value=(5, 10)), \
             patch("algebras.commands.status_command.count_current_and_outdated_keys", return_value=(5, 0)), \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr", "es"], [])), \
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
            
            # Check for the new format in fr output
            found_fr_output = False
            for call_args in mock_echo.call_args_list:
                args, _ = call_args
                if len(args) > 0 and "fr:" in args[0] and "50.0%" in args[0]:
                    found_fr_output = True
                    break
            assert found_fr_output, "Did not find expected fr output"
            
            # Verify that es language is not in the output
            assert not any("es:" in call.args[0] for call in mock_echo.call_args_list if len(call.args) > 0)

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
             patch("os.path.exists", return_value=True), \
             patch("algebras.commands.status_command.count_translated_keys", return_value=(5, 10)), \
             patch("algebras.commands.status_command.count_current_and_outdated_keys", return_value=(5, 0)), \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr"], [])), \
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

    def test_count_current_and_outdated_keys_json_format(self):
        """Test count_current_and_outdated_keys with JSON files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source JSON file
            source_file = os.path.join(temp_dir, "en.json")
            source_data = {
                "hello": "Hello",
                "goodbye": "Goodbye",
                "welcome": "Welcome"
            }
            with open(source_file, 'w') as f:
                json.dump(source_data, f)
            
            # Create target JSON file with translated keys and one outdated key
            target_file = os.path.join(temp_dir, "fr.json")
            target_data = {
                "hello": "Bonjour",
                "goodbye": "",  # Empty translation
                "welcome": "Bienvenue",
                "old_key": "Ancienne clé"  # Outdated key not in source
            }
            with open(target_file, 'w') as f:
                json.dump(target_data, f)
            
            # Test the function
            current_translated, outdated = status_command.count_current_and_outdated_keys(source_file, target_file)
            
            # Should count 2 translated keys (hello, welcome) and 1 outdated key
            assert current_translated == 2
            assert outdated == 1

    def test_count_current_and_outdated_keys_po_format(self):
        """Test count_current_and_outdated_keys with PO files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source PO file
            source_file = os.path.join(temp_dir, "en.po")
            source_content = '''#
msgid "hello"
msgstr "Hello"

msgid "goodbye"
msgstr "Goodbye"

msgid "welcome"
msgstr "Welcome"
'''
            with open(source_file, 'w') as f:
                f.write(source_content)
            
            # Create target PO file with translations and outdated key
            target_file = os.path.join(temp_dir, "fr.po")
            target_content = '''#
msgid "hello"
msgstr "Bonjour"

msgid "goodbye"
msgstr ""

msgid "welcome"
msgstr "Bienvenue"

msgid "old_key"
msgstr "Ancienne clé"
'''
            with open(target_file, 'w') as f:
                f.write(target_content)
            
            # Mock read_language_file to return simplified dict format
            with patch("algebras.commands.status_command.read_language_file") as mock_read:
                # Mock source file reading
                def mock_read_side_effect(path):
                    if path == source_file:
                        return {"hello": "Hello", "goodbye": "Goodbye", "welcome": "Welcome"}
                    else:  # target file
                        return {"hello": "Bonjour", "goodbye": "", "welcome": "Bienvenue", "old_key": "Ancienne clé"}
                
                mock_read.side_effect = mock_read_side_effect
                
                # Test the function
                current_translated, outdated = status_command.count_current_and_outdated_keys(source_file, target_file)
                
                # Should count 2 translated keys (hello, welcome) and 1 outdated key
                assert current_translated == 2
                assert outdated == 1

    def test_count_current_and_outdated_keys_no_outdated(self):
        """Test count_current_and_outdated_keys with no outdated keys"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source JSON file
            source_file = os.path.join(temp_dir, "en.json")
            source_data = {"hello": "Hello", "goodbye": "Goodbye"}
            with open(source_file, 'w') as f:
                json.dump(source_data, f)
            
            # Create target JSON file with exact same keys
            target_file = os.path.join(temp_dir, "fr.json")
            target_data = {"hello": "Bonjour", "goodbye": "Au revoir"}
            with open(target_file, 'w') as f:
                json.dump(target_data, f)
            
            # Test the function
            current_translated, outdated = status_command.count_current_and_outdated_keys(source_file, target_file)
            
            # Should count 2 translated keys and 0 outdated keys
            assert current_translated == 2
            assert outdated == 0

    def test_count_current_and_outdated_keys_missing_files(self):
        """Test count_current_and_outdated_keys with missing files"""
        # Test with non-existent files
        current_translated, outdated = status_command.count_current_and_outdated_keys("nonexistent.json", "also_nonexistent.json")
        
        # Should return 0, 0
        assert current_translated == 0
        assert outdated == 0

    def test_execute_status_with_outdated_keys(self):
        """Test execute status showing outdated keys in display"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        mock_config.get_source_language.return_value = "en"
        
        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"],
            "es": ["messages.es.json"]
        }
        
        # Mock count_translated_keys for source files
        def mock_count_translated_keys(path):
            return 50, 50  # translated_count, total_count
        
        # Mock count_current_and_outdated_keys
        def mock_count_current_and_outdated(source_path, target_path):
            if "fr" in target_path:
                return 45, 3  # 45 current translated, 3 outdated
            else:  # es
                return 30, 0  # 30 current translated, 0 outdated
        
        # Patch dependencies
        with patch("algebras.commands.status_command.Config", return_value=mock_config), \
             patch("algebras.commands.status_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.status_command.count_translated_keys", side_effect=mock_count_translated_keys), \
             patch("algebras.commands.status_command.count_current_and_outdated_keys", side_effect=mock_count_current_and_outdated), \
             patch("algebras.commands.status_command.validate_languages_with_api", return_value=(["en", "fr", "es"], [])), \
             patch("os.path.getmtime", return_value=1000), \
             patch("algebras.commands.status_command.click.echo") as mock_echo:
            
            # Call execute
            status_command.execute()
            
            # Verify the outdated keys are shown in the status line
            # Check that fr shows outdated keys
            fr_status_calls = [call for call in mock_echo.call_args_list if 'fr:' in str(call)]
            assert len(fr_status_calls) > 0
            fr_status_text = str(fr_status_calls[0])
            assert "45/50 keys (90.0%) + 3 outdated keys" in fr_status_text
            
            # Check that es doesn't show outdated keys (when 0)
            es_status_calls = [call for call in mock_echo.call_args_list if 'es:' in str(call)]
            assert len(es_status_calls) > 0
            es_status_text = str(es_status_calls[0])
            assert "30/50 keys (60.0%)" in es_status_text
            assert "outdated" not in es_status_text

    def test_execute_status_with_nested_format_outdated_keys(self):
        """Test execute status with nested format files containing outdated keys"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create source JSON file
            source_file = os.path.join(temp_dir, "en.json")
            source_data = {
                "user": {
                    "name": "Name",
                    "email": "Email"
                },
                "actions": {
                    "save": "Save",
                    "cancel": "Cancel"
                }
            }
            with open(source_file, 'w') as f:
                json.dump(source_data, f)
            
            # Create target JSON file with outdated nested keys
            target_file = os.path.join(temp_dir, "fr.json")
            target_data = {
                "user": {
                    "name": "Nom",
                    "email": "E-mail"
                },
                "actions": {
                    "save": "Sauvegarder",
                    "cancel": "Annuler"
                },
                "old_section": {  # This whole section is outdated
                    "old_key": "Ancienne valeur"
                }
            }
            with open(target_file, 'w') as f:
                json.dump(target_data, f)
            
            # Test the function directly
            current_translated, outdated = status_command.count_current_and_outdated_keys(source_file, target_file)
            
            # Should count 4 current translated keys and 1 outdated key
            assert current_translated == 4
            assert outdated == 1

    def test_count_current_and_outdated_keys_error_handling(self):
        """Test count_current_and_outdated_keys with file reading errors"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files that will cause parsing errors
            source_file = os.path.join(temp_dir, "en.json")
            target_file = os.path.join(temp_dir, "fr.json")
            
            # Create invalid JSON files
            with open(source_file, 'w') as f:
                f.write("invalid json content")
            with open(target_file, 'w') as f:
                f.write("also invalid json")
            
            # Mock read_language_file to raise an exception
            with patch("algebras.commands.status_command.read_language_file", side_effect=Exception("Parse error")), \
                 patch("algebras.commands.status_command.click.echo") as mock_echo:
                
                # Test the function
                current_translated, outdated = status_command.count_current_and_outdated_keys(source_file, target_file)
                
                # Should return 0, 0 and show warning
                assert current_translated == 0
                assert outdated == 0
                
                # Should have shown warning message
                mock_echo.assert_called_once()
                warning_call = mock_echo.call_args[0][0]
                assert "Warning: Could not check keys between" in str(warning_call) 