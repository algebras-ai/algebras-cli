"""
Tests for the healthcheck command
"""

import os
import json
from unittest.mock import patch, MagicMock, Mock
from io import StringIO

import pytest
import click
from click.testing import CliRunner
from colorama import Fore

from algebras.commands import healthcheck_command
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.translation_validator import Issue


class TestHealthcheckExecute:
    """Tests for the execute() function"""

    def test_execute_no_config(self):
        """Test execute with no config file"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 1
            assert mock_config.exists.called
            mock_echo.assert_called_once_with(
                click.style("No Algebras configuration found. Run 'algebras init' first.", fg='red')
            )

    def test_execute_invalid_language(self):
        """Test execute with invalid language specified"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute(language="de")
            
            assert exit_code == 1
            assert mock_config.load.called
            assert mock_config.get_languages.called
            mock_echo.assert_called_with(
                click.style("Language 'de' is not configured in your project.", fg='red')
            )

    def test_execute_no_target_languages(self):
        """Test execute with no target languages to check"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en"]
        mock_config.get_source_language.return_value = "en"
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 0
            mock_echo.assert_called_with(
                click.style("No target languages to check.", fg='yellow')
            )

    def test_execute_no_source_files(self):
        """Test execute with no source files found"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {"en": [], "fr": ["messages.fr.json"]}
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 0
            mock_echo.assert_called_with(
                click.style("No source files found for language 'en'.", fg='yellow')
            )

    def test_execute_success_no_issues(self):
        """Test execute with successful validation and no issues"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Mock file reading and validation
        source_data = {"key1": "Hello", "key2": "World"}
        target_data = {"key1": "Bonjour", "key2": "Monde"}
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.find_source_file", return_value="messages.en.json"), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", return_value=([], 2, set(), set())), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 0
            # Check that success message was printed
            assert any("All translations passed validation" in str(call) for call in mock_echo.call_args_list)

    def test_execute_with_errors(self):
        """Test execute with validation errors"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Create mock issues with errors
        error_issue = Issue('error', 'placeholders', 'Missing placeholder: {name}', 'key1')
        error_issue.file_path = "messages.fr.json"
        error_issue.source_file = "messages.en.json"
        error_issue.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.find_source_file", return_value="messages.en.json"), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", 
                   return_value=([error_issue], 1, {"key1"}, set())), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 1
            # Check that error report was printed
            assert any("Translation Healthcheck Report" in str(call) for call in mock_echo.call_args_list)

    def test_execute_with_warnings_only(self):
        """Test execute with warnings only (should return 0)"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        # Create mock issues with warnings only
        warning_issue = Issue('warning', 'formatting', 'Extra newline in translation', 'key1')
        warning_issue.file_path = "messages.fr.json"
        warning_issue.source_file = "messages.en.json"
        warning_issue.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.find_source_file", return_value="messages.en.json"), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", 
                   return_value=([warning_issue], 1, set(), {"key1"})), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 0  # Warnings don't cause exit code 1
            # Check that report was printed
            assert any("Translation Healthcheck Report" in str(call) for call in mock_echo.call_args_list)

    def test_execute_json_output(self):
        """Test execute with JSON output format"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.find_source_file", return_value="messages.en.json"), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", return_value=([], 2, set(), set())), \
             patch("algebras.commands.healthcheck_command.print_json_report") as mock_json_report, \
             patch("algebras.commands.healthcheck_command.click.echo"):
            
            exit_code = healthcheck_command.execute(output_format='json')
            
            assert exit_code == 0
            mock_json_report.assert_called_once()

    def test_execute_verbose_mode(self):
        """Test execute with verbose mode"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"]
        }
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.find_source_file", return_value="messages.en.json"), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", return_value=([], 2, set(), set())), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute(verbose=True)
            
            assert exit_code == 0
            # Check verbose output
            assert any("Will check" in str(call) and "language(s)" in str(call) 
                      for call in mock_echo.call_args_list)

    def test_execute_single_language(self):
        """Test execute with single language specified"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": ["messages.en.json"],
            "fr": ["messages.fr.json"],
            "es": ["messages.es.json"]
        }
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.find_source_file", return_value="messages.en.json"), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", return_value=([], 2, set(), set())), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute(language="fr")
            
            assert exit_code == 0
            # Check that only fr language was checked
            assert any("Checking language: fr" in str(call) for call in mock_echo.call_args_list)
            # Check that es was not checked
            assert not any("Checking language: es" in str(call) for call in mock_echo.call_args_list)

    def test_execute_exception_handling(self):
        """Test execute with exception handling"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.side_effect = Exception("File scanner error")
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 1
            mock_echo.assert_any_call(
                click.style("Error: File scanner error", fg='red')
            )

    def test_execute_exception_handling_verbose(self):
        """Test execute with exception handling and verbose mode"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = None
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.side_effect = Exception("File scanner error")
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("traceback.print_exc") as mock_traceback, \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            exit_code = healthcheck_command.execute(verbose=True)
            
            assert exit_code == 1
            mock_traceback.assert_called_once()

    def test_execute_with_source_files_config(self):
        """Test execute with source_files configuration"""
        source_file = os.path.join("locales", "en.json")
        target_file = os.path.join("locales", "fr.json")
        
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_source_files.return_value = {
            source_file: {"destination_path": os.path.join("locales", "{language}.json")}
        }
        
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [target_file]
        }
        
        with patch("algebras.commands.healthcheck_command.Config", return_value=mock_config), \
             patch("algebras.commands.healthcheck_command.FileScanner", return_value=mock_scanner), \
             patch("os.path.isfile", return_value=True), \
             patch("algebras.commands.healthcheck_command.resolve_destination_path", return_value=target_file), \
             patch("algebras.commands.healthcheck_command.validate_file_pair", return_value=([], 2, set(), set())), \
             patch("algebras.commands.healthcheck_command.click.echo"):
            
            exit_code = healthcheck_command.execute()
            
            assert exit_code == 0


class TestFindSourceFile:
    """Tests for the find_source_file() function"""

    def test_find_source_file_dot_pattern(self):
        """Test finding source file with .lang. pattern"""
        source_files = ["messages.en.json", "labels.en.json"]
        target_file = "messages.fr.json"
        
        result = healthcheck_command.find_source_file(
            target_file, source_files, "en", "fr"
        )
        
        assert result == "messages.en.json"

    def test_find_source_file_dash_pattern(self):
        """Test finding source file with -lang. pattern"""
        source_files = ["messages-en.json", "labels-en.json"]
        target_file = "messages-fr.json"
        
        result = healthcheck_command.find_source_file(
            target_file, source_files, "en", "fr"
        )
        
        assert result == "messages-en.json"

    def test_find_source_file_underscore_pattern(self):
        """Test finding source file with _lang. pattern"""
        source_files = ["messages_en.json", "labels_en.json"]
        target_file = "messages_fr.json"
        
        result = healthcheck_command.find_source_file(
            target_file, source_files, "en", "fr"
        )
        
        assert result == "messages_en.json"

    def test_find_source_file_directory_pattern(self):
        """Test finding source file with /lang/ directory pattern"""
        source_files = [
            os.path.join("locales", "en", "messages.json"),
            os.path.join("locales", "en", "labels.json")
        ]
        target_file = os.path.join("locales", "fr", "messages.json")
        
        result = healthcheck_command.find_source_file(
            target_file, source_files, "en", "fr"
        )
        
        expected = os.path.join("locales", "en", "messages.json")
        assert os.path.normpath(result) == os.path.normpath(expected)

    def test_find_source_file_android_xml(self):
        """Test finding source file for Android XML (values-es -> values)"""
        source_files = [
            os.path.join("res", "values", "strings.xml"),
            os.path.join("res", "values", "arrays.xml")
        ]
        target_file = os.path.join("res", "values-es", "strings.xml")
        
        result = healthcheck_command.find_source_file(
            target_file, source_files, "en", "es"
        )
        
        expected = os.path.join("res", "values", "strings.xml")
        assert os.path.normpath(result) == os.path.normpath(expected)

    def test_find_source_file_not_found(self):
        """Test finding source file when no match is found"""
        source_files = ["messages.en.json"]
        target_file = "messages.de.json"
        
        result = healthcheck_command.find_source_file(
            target_file, source_files, "en", "fr"
        )
        
        assert result is None


class TestValidateFilePair:
    """Tests for the validate_file_pair() function"""

    def test_validate_file_pair_html(self):
        """Test validate_file_pair with HTML files"""
        source_file = os.path.join("templates", "en.html")
        target_file = os.path.join("templates", "fr.html")
        
        source_data = {"key1": "Hello", "key2": "World"}
        target_data = {"key1": "Bonjour", "key2": "Monde"}
        
        mock_issue_key1 = Issue('error', 'placeholders', 'Missing placeholder', 'key1')
        mock_issue_key2 = Issue('warning', 'formatting', 'Extra space', 'key2')
        
        def validate_side_effect(source, target, key):
            if key == "key1":
                return [mock_issue_key1]
            elif key == "key2":
                return [mock_issue_key2]
            return []
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_html_file", 
                  side_effect=[source_data, target_data]), \
             patch("algebras.commands.healthcheck_command.validate_translation", 
                  side_effect=validate_side_effect):
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            assert len(issues) == 2
            assert keys_checked == 2
            assert "key1" in keys_with_errors
            assert "key2" in keys_with_warnings
            assert issues[0].file_path == target_file
            assert issues[0].source_file == source_file
            assert issues[0].language == "fr"

    def test_validate_file_pair_flat_format(self):
        """Test validate_file_pair with flat dictionary formats"""
        source_file = "messages.en.po"
        target_file = "messages.fr.po"
        
        source_data = {"key1": "Hello", "key2": "World"}
        target_data = {"key1": "Bonjour", "key2": "Monde"}
        
        mock_issue_key1 = Issue('warning', 'formatting', 'Extra space', 'key1')
        
        def validate_side_effect(source, target, key):
            if key == "key1":
                return [mock_issue_key1]
            return []  # key2 has no issues
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_language_file", 
                  side_effect=[source_data, target_data]), \
             patch("algebras.commands.healthcheck_command.validate_translation", 
                  side_effect=validate_side_effect):
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            assert len(issues) == 1
            assert keys_checked == 2
            assert "key1" in keys_with_warnings

    def test_validate_file_pair_nested_format(self):
        """Test validate_file_pair with nested formats (JSON)"""
        source_file = "messages.en.json"
        target_file = "messages.fr.json"
        
        source_data = {"nested": {"key1": "Hello", "key2": "World"}}
        target_data = {"nested": {"key1": "Bonjour", "key2": "Monde"}}
        
        mock_issue_key1 = Issue('error', 'placeholders', 'Missing placeholder', 'nested.key1')
        
        def validate_side_effect(source, target, key):
            if key == "nested.key1":
                return [mock_issue_key1]
            return []  # nested.key2 has no issues
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_language_file", 
                  side_effect=[source_data, target_data]), \
             patch("algebras.commands.healthcheck_command.extract_all_keys", 
                  side_effect=[["nested.key1", "nested.key2"], ["nested.key1", "nested.key2"]]), \
             patch("algebras.commands.healthcheck_command.get_key_value", 
                  side_effect=["Hello", "Bonjour", "World", "Monde"]), \
             patch("algebras.commands.healthcheck_command.validate_translation", 
                  side_effect=validate_side_effect):
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            assert len(issues) == 1
            assert keys_checked == 2
            assert "nested.key1" in keys_with_errors

    def test_validate_file_pair_empty_translation(self):
        """Test validate_file_pair with empty translations (should be skipped)"""
        source_file = "messages.en.json"
        target_file = "messages.fr.json"
        
        source_data = {"key1": "Hello", "key2": "World"}
        target_data = {"key1": "", "key2": "   "}  # Empty or whitespace only
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_language_file", 
                  side_effect=[source_data, target_data]), \
             patch("algebras.commands.healthcheck_command.validate_translation") as mock_validate:
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            assert len(issues) == 0
            assert keys_checked == 0
            assert len(keys_with_errors) == 0
            assert len(keys_with_warnings) == 0
            # validate_translation should not be called for empty translations
            assert mock_validate.call_count == 0

    def test_validate_file_pair_file_error(self):
        """Test validate_file_pair with file reading error"""
        source_file = "messages.en.json"
        target_file = "messages.fr.json"
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_language_file", 
                  side_effect=Exception("File read error")), \
             patch("algebras.commands.healthcheck_command.click.echo"):
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            assert len(issues) == 1
            assert issues[0].severity == 'error'
            assert issues[0].category == 'system'
            assert "Failed to validate file" in issues[0].message
            assert issues[0].file_path == target_file
            assert issues[0].source_file == source_file
            assert issues[0].language == "fr"

    def test_validate_file_pair_file_error_verbose(self):
        """Test validate_file_pair with file reading error in verbose mode"""
        source_file = "messages.en.json"
        target_file = "messages.fr.json"
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_language_file", 
                  side_effect=Exception("File read error")), \
             patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, True
                )
            
            assert len(issues) == 1
            # Check that verbose error message was printed
            assert any("Error validating" in str(call) for call in mock_echo.call_args_list)

    def test_validate_file_pair_csv_tsv(self):
        """Test validate_file_pair with CSV/TSV files (language parameters)"""
        source_file = "messages.csv"
        target_file = "messages.csv"
        
        source_data = {"key1": "Hello", "key2": "World"}
        target_data = {"key1": "Bonjour", "key2": "Monde"}
        
        mock_config = MagicMock(spec=Config)
        
        with patch("algebras.commands.healthcheck_command.read_language_file") as mock_read, \
             patch("algebras.commands.healthcheck_command.validate_translation", 
                  return_value=[]):
            
            mock_read.side_effect = [source_data, target_data]
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            # Verify language parameters were passed
            assert mock_read.call_count == 2
            assert mock_read.call_args_list[0][0][1] == "en"  # source_lang
            assert mock_read.call_args_list[1][0][1] == "fr"  # target_lang

    def test_validate_file_pair_both_errors_and_warnings(self):
        """Test validate_file_pair tracking both errors and warnings"""
        source_file = "messages.en.json"
        target_file = "messages.fr.json"
        
        source_data = {"key1": "Hello", "key2": "World"}
        target_data = {"key1": "Bonjour", "key2": "Monde"}
        
        error_issue = Issue('error', 'placeholders', 'Missing placeholder', 'key1')
        warning_issue = Issue('warning', 'formatting', 'Extra space', 'key2')
        
        mock_config = MagicMock(spec=Config)
        
        def validate_side_effect(source, target, key):
            if key == "key1":
                return [error_issue]
            elif key == "key2":
                return [warning_issue]
            return []
        
        with patch("algebras.commands.healthcheck_command.read_language_file", 
                  side_effect=[source_data, target_data]), \
             patch("algebras.commands.healthcheck_command.validate_translation", 
                  side_effect=validate_side_effect):
            
            issues, keys_checked, keys_with_errors, keys_with_warnings = \
                healthcheck_command.validate_file_pair(
                    source_file, target_file, "en", "fr", mock_config, False
                )
            
            assert len(issues) == 2
            assert keys_checked == 2
            assert "key1" in keys_with_errors
            assert "key2" in keys_with_warnings
            assert "key1" not in keys_with_warnings
            assert "key2" not in keys_with_errors


class TestPrintConsoleReport:
    """Tests for the print_console_report() function"""

    def test_print_console_report_no_issues(self):
        """Test print_console_report with no issues"""
        with patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            healthcheck_command.print_console_report([], 2, 5, 5, 0, 0, False)
            
            # Check success message
            assert any("All translations passed validation" in str(call) 
                      for call in mock_echo.call_args_list)
            assert any("Files checked: 2" in str(call) for call in mock_echo.call_args_list)
            assert any("Keys checked: 5" in str(call) for call in mock_echo.call_args_list)

    def test_print_console_report_with_errors(self):
        """Test print_console_report with errors only"""
        error_issue = Issue('error', 'placeholders', 'Missing placeholder: {name}', 'key1')
        error_issue.file_path = "messages.fr.json"
        error_issue.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            healthcheck_command.print_console_report([error_issue], 1, 2, 1, 1, 0, False)
            
            # Check that report header was printed
            assert any("Translation Healthcheck Report" in str(call) 
                      for call in mock_echo.call_args_list)
            # Check that error was printed
            assert any("Missing placeholder" in str(call) 
                      for call in mock_echo.call_args_list)

    def test_print_console_report_with_warnings(self):
        """Test print_console_report with warnings only"""
        warning_issue = Issue('warning', 'formatting', 'Extra newline', 'key1')
        warning_issue.file_path = "messages.fr.json"
        warning_issue.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            healthcheck_command.print_console_report([warning_issue], 1, 2, 1, 0, 1, False)
            
            # Check that report was printed
            assert any("Translation Healthcheck Report" in str(call) 
                      for call in mock_echo.call_args_list)
            # Check that warning was printed
            assert any("Extra newline" in str(call) 
                      for call in mock_echo.call_args_list)

    def test_print_console_report_with_both(self):
        """Test print_console_report with both errors and warnings"""
        error_issue = Issue('error', 'placeholders', 'Missing placeholder', 'key1')
        error_issue.file_path = "messages.fr.json"
        error_issue.language = "fr"
        
        warning_issue = Issue('warning', 'formatting', 'Extra space', 'key2')
        warning_issue.file_path = "messages.fr.json"
        warning_issue.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            healthcheck_command.print_console_report(
                [error_issue, warning_issue], 1, 2, 0, 1, 1, False
            )
            
            # Check that both error and warning messages were printed
            assert any("Missing placeholder" in str(call) 
                      for call in mock_echo.call_args_list)
            assert any("Extra space" in str(call) 
                      for call in mock_echo.call_args_list)

    def test_print_console_report_grouping(self):
        """Test print_console_report issue grouping by file and category"""
        error1 = Issue('error', 'placeholders', 'Missing placeholder 1', 'key1')
        error1.file_path = "messages.fr.json"
        error1.language = "fr"
        
        error2 = Issue('error', 'placeholders', 'Missing placeholder 2', 'key2')
        error2.file_path = "messages.fr.json"
        error2.language = "fr"
        
        warning = Issue('warning', 'formatting', 'Extra space', 'key3')
        warning.file_path = "labels.fr.json"
        warning.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            healthcheck_command.print_console_report(
                [error1, error2, warning], 2, 3, 0, 2, 1, False
            )
            
            # Check that files were grouped
            echo_calls = [str(call) for call in mock_echo.call_args_list]
            assert any("messages.fr.json" in call for call in echo_calls)
            assert any("labels.fr.json" in call for call in echo_calls)

    def test_print_console_report_statistics(self):
        """Test print_console_report displays correct statistics"""
        error_issue = Issue('error', 'placeholders', 'Missing placeholder', 'key1')
        error_issue.file_path = "messages.fr.json"
        error_issue.language = "fr"
        
        with patch("algebras.commands.healthcheck_command.click.echo") as mock_echo:
            healthcheck_command.print_console_report([error_issue], 1, 5, 4, 1, 0, False)
            
            echo_calls = [str(call) for call in mock_echo.call_args_list]
            # Check statistics are displayed
            assert any("Files checked: 1" in call for call in echo_calls)
            assert any("Keys checked: 5" in call for call in echo_calls)
            assert any("Keys OK: 4" in call for call in echo_calls)
            assert any("Keys with errors: 1" in call for call in echo_calls)


class TestPrintJsonReport:
    """Tests for the print_json_report() function"""

    def test_print_json_report_structure(self):
        """Test print_json_report JSON structure"""
        error_issue = Issue('error', 'placeholders', 'Missing placeholder: {name}', 'key1')
        error_issue.file_path = "messages.fr.json"
        error_issue.language = "fr"
        
        warning_issue = Issue('warning', 'formatting', 'Extra newline', 'key2')
        warning_issue.file_path = "messages.fr.json"
        warning_issue.language = "fr"
        
        with patch("builtins.print") as mock_print:
            healthcheck_command.print_json_report(
                [error_issue, warning_issue], 1, 2, 0, 1, 1
            )
            
            # Get the JSON string that was printed
            assert mock_print.call_count == 1
            json_str = mock_print.call_args[0][0]
            report = json.loads(json_str)
            
            # Verify structure
            assert 'summary' in report
            assert 'files' in report
            assert report['summary']['files_checked'] == 1
            assert report['summary']['keys_checked'] == 2
            assert report['summary']['keys_ok'] == 0
            assert report['summary']['keys_with_errors'] == 1
            assert report['summary']['keys_with_warnings'] == 1
            assert report['summary']['total_issues'] == 2
            assert report['summary']['errors'] == 1
            assert report['summary']['warnings'] == 1

    def test_print_json_report_issues(self):
        """Test print_json_report issue details"""
        error_issue = Issue('error', 'placeholders', 'Missing placeholder', 'key1')
        error_issue.file_path = "messages.fr.json"
        error_issue.language = "fr"
        
        with patch("builtins.print") as mock_print:
            healthcheck_command.print_json_report([error_issue], 1, 1, 0, 1, 0)
            
            json_str = mock_print.call_args[0][0]
            report = json.loads(json_str)
            
            # Verify file entry
            assert len(report['files']) == 1
            file_entry = report['files'][0]
            assert file_entry['file'] == "messages.fr.json"
            assert file_entry['language'] == "fr"
            assert len(file_entry['issues']) == 1
            
            issue_entry = file_entry['issues'][0]
            assert issue_entry['severity'] == 'error'
            assert issue_entry['category'] == 'placeholders'
            assert issue_entry['message'] == 'Missing placeholder'
            assert issue_entry['key'] == 'key1'

    def test_print_json_report_multiple_files(self):
        """Test print_json_report with multiple files"""
        issue1 = Issue('error', 'placeholders', 'Missing placeholder', 'key1')
        issue1.file_path = "messages.fr.json"
        issue1.language = "fr"
        
        issue2 = Issue('warning', 'formatting', 'Extra space', 'key2')
        issue2.file_path = "labels.fr.json"
        issue2.language = "fr"
        
        with patch("builtins.print") as mock_print:
            healthcheck_command.print_json_report([issue1, issue2], 2, 2, 0, 1, 1)
            
            json_str = mock_print.call_args[0][0]
            report = json.loads(json_str)
            
            # Verify both files are in the report
            assert len(report['files']) == 2
            file_paths = [f['file'] for f in report['files']]
            assert "messages.fr.json" in file_paths
            assert "labels.fr.json" in file_paths

    def test_print_json_report_no_issues(self):
        """Test print_json_report with no issues"""
        with patch("builtins.print") as mock_print:
            healthcheck_command.print_json_report([], 2, 5, 5, 0, 0)
            
            json_str = mock_print.call_args[0][0]
            report = json.loads(json_str)
            
            assert report['summary']['total_issues'] == 0
            assert report['summary']['errors'] == 0
            assert report['summary']['warnings'] == 0
            assert len(report['files']) == 0


class TestHealthcheckCLI:
    """Tests for CLI integration"""

    def test_cli_invoke_healthcheck(self):
        """Test CLI command invocation"""
        runner = CliRunner()
        
        with patch("algebras.commands.healthcheck_command.execute") as mock_execute:
            from algebras.cli import healthcheck
            
            mock_execute.return_value = 0
            
            result = runner.invoke(healthcheck)
            
            assert result.exit_code == 0
            mock_execute.assert_called_once_with(
                language=None, output_format='console', verbose=False, config_file=None
            )

    def test_cli_invoke_with_language(self):
        """Test CLI command with language option"""
        runner = CliRunner()
        
        with patch("algebras.commands.healthcheck_command.execute") as mock_execute:
            from algebras.cli import healthcheck
            
            mock_execute.return_value = 0
            
            result = runner.invoke(healthcheck, ["--language", "fr"])
            
            assert result.exit_code == 0
            mock_execute.assert_called_once_with(
                language="fr", output_format='console', verbose=False, config_file=None
            )

    def test_cli_invoke_with_format_json(self):
        """Test CLI command with JSON format"""
        runner = CliRunner()
        
        with patch("algebras.commands.healthcheck_command.execute") as mock_execute:
            from algebras.cli import healthcheck
            
            mock_execute.return_value = 0
            
            result = runner.invoke(healthcheck, ["--format", "json"])
            
            assert result.exit_code == 0
            mock_execute.assert_called_once_with(
                language=None, output_format='json', verbose=False, config_file=None
            )

    def test_cli_invoke_with_verbose(self):
        """Test CLI command with verbose flag"""
        runner = CliRunner()
        
        with patch("algebras.commands.healthcheck_command.execute") as mock_execute:
            from algebras.cli import healthcheck
            
            mock_execute.return_value = 0
            
            result = runner.invoke(healthcheck, ["--verbose"])
            
            assert result.exit_code == 0
            mock_execute.assert_called_once_with(
                language=None, output_format='console', verbose=True, config_file=None
            )

    def test_cli_invoke_with_all_options(self):
        """Test CLI command with all options"""
        runner = CliRunner()
        
        with patch("algebras.commands.healthcheck_command.execute") as mock_execute:
            from algebras.cli import healthcheck
            
            mock_execute.return_value = 0
            
            result = runner.invoke(healthcheck, [
                "--language", "fr",
                "--format", "json",
                "--verbose"
            ])
            
            assert result.exit_code == 0
            mock_execute.assert_called_once_with(
                language="fr", output_format='json', verbose=True, config_file=None
            )

    def test_cli_exit_code_with_errors(self):
        """Test CLI command exit code when errors are found"""
        runner = CliRunner()
        
        with patch("algebras.commands.healthcheck_command.execute") as mock_execute:
            from algebras.cli import healthcheck
            
            mock_execute.return_value = 1
            
            result = runner.invoke(healthcheck)
            
            assert result.exit_code == 1

