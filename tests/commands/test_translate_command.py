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
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch("algebras.commands.translate_command.click.echo") as mock_echo:

            # Call execute
            translate_command.execute()

            # Verify Config was used
            assert mock_config.exists.called

            # Verify output message
            mock_echo.assert_called_once_with(
                f"{click.style('No Algebras configuration found. Run \'algebras init\' first.', fg='red')}"
            )

    def test_execute_only_one_language(self):
        """Test execute with only one language configured"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en"]
        mock_config.check_deprecated_format.return_value = False

        # Patch Config and click.echo
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch("algebras.commands.translate_command.click.echo") as mock_echo:

            # Call execute
            translate_command.execute()

            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called

            # Verify output message
            mock_echo.assert_called_once_with(
                f"{click.style('Only one language (en) is configured. Add more languages with \'algebras add <language>\'.', fg='yellow')}"
            )

    def test_execute_invalid_language(self):
        """Test execute with invalid language specified"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.check_deprecated_format.return_value = False

        # Patch Config and click.echo
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch("algebras.commands.translate_command.click.echo") as mock_echo:

            # Call execute
            translate_command.execute(language="de")

            # Verify Config was used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called

            # Verify output message
            mock_echo.assert_called_once_with(
                f"{click.style('Language \'de\' is not configured in your project.', fg='red')}"
            )

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
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "algebras.commands.translate_command.Translator"
        ) as mock_translator_class:

            # Call execute
            translate_command.execute()

            # Verify dependencies were used correctly
            assert mock_config.exists.called
            assert mock_config.load.called
            assert mock_config.get_languages.called
            assert mock_scanner.group_files_by_language.called

            # Verify output message
            mock_echo.assert_called_with(
                f"{click.style('No source files found for language \'en\'.', fg='yellow')}"
            )

    def test_execute_success(self):
        """Test execute with successful translation"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        mock_config.get_source_files.return_value = None
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.has_setting.return_value = False
        # Mock get_setting to return appropriate values
        mock_config.get_setting.side_effect = lambda key, default: {
            "xlf.default_target_state": "translated",
            "xlf.version": "1.2",
            "po.mark_fuzzy": False,
            "api.prompt": "",
        }.get(key, default)

        # Set up source and target paths
        source_file = "public/locales/en/messages.json"
        target_file = "public/locales/fr/messages.json"
        source_basename = "messages.json"  # The base filename without language code

        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [],
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"welcome": "Bienvenue"}
        mock_translator.set_verbose.return_value = None

        # Mock the utility functions and file operations
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            new=lambda *args, **kwargs: mock_translator,
        ), patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=False
        ), patch(
            "os.path.getmtime", return_value=0
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "json.dump"
        ) as mock_json_dump, patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "os.path.dirname", return_value="public/locales/fr"
        ), patch(
            "os.path.basename", return_value=source_basename
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "builtins.print"
        ) as mock_print:  # Mock print to avoid output in terminal

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
            mock_echo.assert_any_call(
                "\x1b[32mFound 1 source files for language 'en'.\x1b[0m"
            )
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
            "fr": [target_file],
        }

        # Mock the directory and file paths
        def mock_dirname(path):
            if path == source_file:
                return "public/locales/en"
            return "public/locales/fr"

        def mock_basename(path):
            return source_basename

        # Patch dependencies
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "os.path.exists", return_value=True
        ), patch(
            "os.path.getmtime", side_effect=[1000, 2000]
        ), patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.dirname", side_effect=mock_dirname
        ), patch(
            "os.path.basename", side_effect=mock_basename
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "builtins.print"
        ) as mock_print, patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ):

            # Call execute without force
            translate_command.execute(force=False)

            # Verify output messages (skipping messages)
            mock_echo.assert_any_call(
                f"{click.style('Found 1 source files for language \'en\'.', fg='green')}"
            )

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
            "fr": [target_file],
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
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            return_value=mock_translator,
        ), patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=True
        ), patch(
            "os.path.getmtime", side_effect=[1000, 2000]
        ), patch(
            "os.path.dirname", side_effect=mock_dirname
        ), patch(
            "os.path.basename", side_effect=mock_basename
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "json.dump"
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "builtins.print"
        ) as mock_print:

            # Call execute with force="__all__"
            translate_command.execute(force="__all__")

            # Verify translation was attempted with force
            mock_echo.assert_any_call(
                f"{click.style('Found 1 source files for language \'en\'.', fg='green')}"
            )

            # Check for translation message
            assert (
                mock_translator.translate_file.called
            ), "translate_file was not called"

            # Check for translation message content
            translating_message_found = False
            for call_args in mock_echo.call_args_list:
                args, _ = call_args
                if (
                    len(args) > 0
                    and "Translating" in args[0]
                    and "messages.json" in args[0]
                ):
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
            mock_execute.assert_called_once_with(
                None,
                None,
                False,
                ui_safe=False,
                verbose=False,
                batch_size=None,
                max_parallel_batches=None,
                glossary_id=None,
                prompt_file=None,
                regenerate_from_scratch=False,
                config_file=None,
            )

            # Test with language and force options
            result = runner.invoke(translate, ["--language", "fr", "--force"])

            # Verify the command executed successfully
            assert result.exit_code == 0

            # Verify execute was called with the right arguments
            mock_execute.assert_called_with(
                "fr",
                "__all__",
                False,
                ui_safe=False,
                verbose=False,
                batch_size=None,
                max_parallel_batches=None,
                glossary_id=None,
                prompt_file=None,
                regenerate_from_scratch=False,
                config_file=None,
            )

            # Test with ui_safe option
            result = runner.invoke(translate, ["--ui-safe"])

            # Verify the command executed successfully
            assert result.exit_code == 0

            # Verify execute was called with the right arguments
            mock_execute.assert_called_with(
                None,
                None,
                False,
                ui_safe=True,
                verbose=False,
                batch_size=None,
                max_parallel_batches=None,
                glossary_id=None,
                prompt_file=None,
                regenerate_from_scratch=False,
                config_file=None,
            )

    def test_execute_reads_po_mark_fuzzy_config(self):
        """Test that execute reads po.mark_fuzzy config and passes it to write_po_file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        # Mock get_setting to return True for po.mark_fuzzy
        mock_config.get_setting.side_effect = lambda key, default: {
            "xlf.default_target_state": "translated",
            "po.mark_fuzzy": True,
        }.get(key, default)

        # Set up paths for testing
        source_file = "public/locales/en/messages.po"
        target_file = "public/locales/fr/messages.po"

        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [],
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"Hello": "Bonjour"}

        # Mock write_po_file to verify it's called with mark_fuzzy=True
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            return_value=mock_translator,
        ), patch(
            "algebras.utils.file_format_handlers.po_handler.write_po_file"
        ) as mock_write_po, patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=False
        ), patch(
            "os.path.getmtime", return_value=0
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.dirname", return_value="public/locales/fr"
        ), patch(
            "os.path.basename", return_value="messages.po"
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ), patch(
            "builtins.print"
        ):

            # Call execute
            translate_command.execute()

            # Verify get_setting was called for po.mark_fuzzy
            mock_config.get_setting.assert_any_call("po.mark_fuzzy", False)

            # Verify write_po_file was called with mark_fuzzy=True
            assert mock_write_po.called, "write_po_file should be called"
            call_args = mock_write_po.call_args
            assert (
                call_args is not None
            ), "write_po_file should have been called with arguments"
            # Check that mark_fuzzy=True was passed (third argument)
            assert (
                len(call_args[0]) >= 3
            ), "write_po_file should be called with at least 3 arguments"
            assert (
                call_args[0][2] == True
            ), "write_po_file should be called with mark_fuzzy=True"

    def test_execute_reads_po_mark_fuzzy_config_false(self):
        """Test that execute reads po.mark_fuzzy config (False) and passes it to write_po_file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        # Mock get_setting to return False for po.mark_fuzzy (default)
        mock_config.get_setting.side_effect = lambda key, default: {
            "xlf.default_target_state": "translated",
            "po.mark_fuzzy": False,
        }.get(key, default)

        # Set up paths for testing
        source_file = "public/locales/en/messages.po"
        target_file = "public/locales/fr/messages.po"

        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [],
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"Hello": "Bonjour"}

        # Mock write_po_file to verify it's called with mark_fuzzy=False
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            return_value=mock_translator,
        ), patch(
            "algebras.utils.file_format_handlers.po_handler.write_po_file"
        ) as mock_write_po, patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=False
        ), patch(
            "os.path.getmtime", return_value=0
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.dirname", return_value="public/locales/fr"
        ), patch(
            "os.path.basename", return_value="messages.po"
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ), patch(
            "builtins.print"
        ):

            # Call execute
            translate_command.execute()

            # Verify get_setting was called for po.mark_fuzzy
            mock_config.get_setting.assert_any_call("po.mark_fuzzy", False)

            # Verify write_po_file was called with mark_fuzzy=False
            assert mock_write_po.called, "write_po_file should be called"
            call_args = mock_write_po.call_args
            assert (
                call_args is not None
            ), "write_po_file should have been called with arguments"
            # Check that mark_fuzzy=False was passed (third positional argument)
            # Handler calls: write_po_file(file_path, content, po_mark_fuzzy)
            assert (
                len(call_args[0]) >= 3
            ), "write_po_file should be called with at least 3 arguments"
            assert (
                call_args[0][2] == False
            ), "write_po_file should be called with mark_fuzzy=False"

    def test_default_mode_translates_files_with_missing_keys_despite_newer_mtime(self):
        """
        Test that default mode (without --only-missing) checks for missing keys
        even when target file has newer mtime than source.
        
        This is a regression test for the bug where files were skipped based solely
        on modification time without checking for missing keys.
        """
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "de"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        mock_config.get_source_files.return_value = None
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.has_setting.return_value = False
        mock_config.get_setting.side_effect = lambda key, default: {
            "xlf.default_target_state": "translated",
            "xlf.version": "1.2",
            "po.mark_fuzzy": False,
            "api.prompt": "",
        }.get(key, default)

        # Set up paths
        source_file = "strings/values/generic_strings_2.xml"
        target_file = "strings/values-de/generic_strings_2.xml"
        source_basename = "generic_strings_2.xml"

        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "de": [target_file],
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {
            "Quiz.timer_format.__plurals__": {"one": "%1$d Minute", "other": "%1$d Minuten"}
        }
        mock_translator.set_verbose.return_value = None

        # Mock validate_language_files to return missing plural keys
        missing_keys = {
            "Quiz.timer_format.__plurals__",
            "Quiz.passing_score_points_format.__plurals__",
            "Quiz.question_score_format.__plurals__"
        }

        # Patch all dependencies
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            return_value=mock_translator,
        ), patch(
            "algebras.commands.translate_command.validate_language_files",
            return_value=(False, missing_keys)
        ) as mock_validate, patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=True
        ), patch(
            "os.path.getmtime", side_effect=[1000, 2000]  # source older, target newer
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.dirname", return_value="strings/values-de"
        ), patch(
            "os.path.basename", return_value=source_basename
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "builtins.print"
        ):

            # Call execute in default mode (no force, no only_missing)
            translate_command.execute(force=False, only_missing=False)

            # Verify the file was NOT skipped (no "Skipping" message)
            skip_messages = [
                call for call in mock_echo.call_args_list
                if len(call[0]) > 0 and "Skipping" in str(call[0][0])
            ]
            assert len(skip_messages) == 0, "File should NOT be skipped when missing keys exist"

            # Verify validate_language_files was called to check for missing keys
            assert mock_validate.called, "validate_language_files should be called in default mode"

            # Verify translation was attempted
            assert mock_translator.translate_file.called, "Translation should be attempted for missing keys"

    def test_default_mode_skips_complete_files_with_newer_mtime(self):
        """
        Test that default mode still skips files with newer mtime when they have no missing keys.
        
        This ensures the mtime optimization still works for truly up-to-date files.
        """
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "de"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        mock_config.get_source_files.return_value = None
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.has_setting.return_value = False
        mock_config.get_setting.side_effect = lambda key, default: {
            "xlf.default_target_state": "translated",
            "xlf.version": "1.2",
            "po.mark_fuzzy": False,
            "api.prompt": "",
        }.get(key, default)

        # Set up paths
        source_file = "strings/values/generic_strings.xml"
        target_file = "strings/values-de/generic_strings.xml"
        source_basename = "generic_strings.xml"

        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "de": [target_file],
        }

        # Mock Translator
        mock_translator = MagicMock(spec=Translator)
        mock_translator.set_verbose.return_value = None

        # Mock validate_language_files to return NO missing keys
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            return_value=mock_translator,
        ), patch(
            "algebras.commands.translate_command.validate_language_files",
            return_value=(True, set())  # No missing keys
        ) as mock_validate, patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=True
        ), patch(
            "os.path.getmtime", side_effect=[1000, 2000]  # source older, target newer
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.dirname", return_value="strings/values-de"
        ), patch(
            "os.path.basename", return_value=source_basename
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "builtins.print"
        ):

            # Call execute in default mode
            translate_command.execute(force=False, only_missing=False)

            # Verify validate_language_files was called
            assert mock_validate.called, "validate_language_files should be called"

            # Verify the file WAS skipped (optimization works)
            skip_messages = [
                call for call in mock_echo.call_args_list
                if len(call[0]) > 0 and "Skipping" in str(call[0][0])
            ]
            assert len(skip_messages) > 0, "File should be skipped when no missing keys and newer mtime"

            # Verify translation was NOT attempted
            assert not mock_translator.translate_file.called, "Translation should not be attempted for complete files"

    def test_default_mode_with_xml_plural_keys_missing(self):
        """
        Integration test for Android XML plural scenario from bug report.
        
        Tests the exact scenario: source XML has plural keys, target is missing them
        but has newer mtime. Default mode should detect and translate missing plurals.
        """
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "de"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        mock_config.get_source_files.return_value = None
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.has_setting.return_value = False
        mock_config.get_setting.side_effect = lambda key, default: {
            "xlf.default_target_state": "translated",
            "xlf.version": "1.2",
            "po.mark_fuzzy": False,
            "api.prompt": "",
        }.get(key, default)

        # Set up paths
        source_file = "strings/values/generic_strings_2.xml"
        target_file = "strings/values-de/generic_strings_2.xml"
        source_basename = "generic_strings_2.xml"

        # Mock FileScanner
        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "de": [target_file],
        }

        # Mock Translator to return German translations for plurals
        mock_translator = MagicMock(spec=Translator)
        mock_translator.set_verbose.return_value = None
        mock_translator.translate_file.return_value = {
            "Quiz.timer_format.__plurals__": {"one": "%1$d Minute", "other": "%1$d Minuten"},
            "Quiz.passing_score_points_format.__plurals__": {"one": "%1$d Punkt", "other": "%1$d Punkte"},
            "Quiz.question_score_format.__plurals__": {"one": "%1$d Punkt erzielt", "other": "%1$d Punkte erzielt"}
        }

        # Mock validate_language_files to return missing plural keys
        missing_keys = {
            "Quiz.timer_format.__plurals__",
            "Quiz.passing_score_points_format.__plurals__",
            "Quiz.question_score_format.__plurals__"
        }

        # Track whether translation was called
        translation_attempted = []
        
        def track_translate(*args, **kwargs):
            translation_attempted.append(True)
            return mock_translator.translate_file.return_value
        
        mock_translator.translate_file.side_effect = track_translate

        # Patch dependencies
        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator",
            return_value=mock_translator,
        ), patch(
            "algebras.commands.translate_command.validate_language_files",
            return_value=(False, missing_keys)
        ) as mock_validate, patch(
            "builtins.open", mock_open()
        ), patch(
            "os.path.exists", return_value=True
        ), patch(
            "os.path.getmtime", side_effect=[1000, 2000]  # source older, target newer
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.dirname", return_value="strings/values-de"
        ), patch(
            "os.path.basename", return_value=source_basename
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ) as mock_echo, patch(
            "builtins.print"
        ), patch(
            "json.dump"
        ):

            # Call execute in default mode
            translate_command.execute(force=False, only_missing=False)

            # Verify validate_language_files was called
            assert mock_validate.called, "validate_language_files should be called"

            # Verify the file was NOT skipped (translation was attempted)
            assert len(translation_attempted) > 0, \
                "Translation should be attempted for missing plural keys"

            # Verify no skip message was logged
            skip_messages = [
                call for call in mock_echo.call_args_list
                if len(call[0]) > 0 and "Skipping" in str(call[0][0])
            ]
            assert len(skip_messages) == 0, \
                "File should NOT be skipped when plural keys are missing"

    def test_force_key_cli_parsing(self):
        """Test that --force "key1,key2" is passed as a string to execute()"""
        runner = CliRunner()

        with patch("algebras.commands.translate_command.execute") as mock_execute:
            from algebras.cli import translate

            result = runner.invoke(translate, ["--force", "login.title,nav.home"])

            assert result.exit_code == 0
            mock_execute.assert_called_once_with(
                None,
                "login.title,nav.home",
                False,
                ui_safe=False,
                verbose=False,
                batch_size=None,
                max_parallel_batches=None,
                glossary_id=None,
                prompt_file=None,
                regenerate_from_scratch=False,
                config_file=None,
            )

    def test_execute_force_specific_keys(self):
        """Test that execute(force="key1,key2") calls translate_missing_keys_batch with those keys only"""
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.side_effect = lambda key, default: default
        mock_config.get_source_files.return_value = None

        source_file = "locales/en/messages.json"
        target_file = "locales/fr/messages.json"

        mock_scanner = MagicMock(spec=FileScanner)
        mock_scanner.group_files_by_language.return_value = {
            "en": [source_file],
            "fr": [target_file],
        }

        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_missing_keys_batch.return_value = {
            "login": {"title": "Connexion"},
            "nav": {"home": "Accueil"},
        }

        source_content = {"login": {"title": "Login"}, "nav": {"home": "Home"}, "other": "Keep"}
        target_content = {"login": {"title": "Old"}, "nav": {"home": "Old"}, "other": "Garder"}

        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.FileScanner", return_value=mock_scanner
        ), patch(
            "algebras.commands.translate_command.Translator", return_value=mock_translator
        ), patch(
            "os.path.exists", return_value=True
        ), patch(
            "os.makedirs", return_value=None
        ), patch(
            "os.path.dirname", side_effect=lambda p: p.rsplit("/", 1)[0]
        ), patch(
            "os.path.basename", side_effect=lambda p: p.rsplit("/", 1)[-1]
        ), patch(
            "os.path.getsize", return_value=1024
        ), patch(
            "os.path.getmtime", side_effect=[2000, 1000]  # source newer → skip mtime block
        ), patch(
            "os.path.relpath", return_value=source_file
        ), patch(
            "algebras.commands.translate_command.determine_target_path",
            return_value=target_file,
        ), patch(
            "algebras.commands.translate_command._load_file_contents",
            return_value=(source_content, target_content, None, None),
        ), patch(
            "algebras.commands.translate_command._should_use_in_place", return_value=False
        ), patch(
            "algebras.commands.translate_command._write_translated_content"
        ), patch(
            "algebras.commands.translate_command.detect_format", return_value=None
        ), patch(
            "algebras.commands.translate_command.get_handler", return_value=MagicMock()
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ), patch(
            "builtins.print"
        ):
            translate_command.execute(force="login.title,nav.home")

            # translate_missing_keys_batch must be called with the two specified keys
            assert mock_translator.translate_missing_keys_batch.called, \
                "translate_missing_keys_batch should be called for --force key mode"

            call_args = mock_translator.translate_missing_keys_batch.call_args
            keys_arg = call_args[0][2]  # third positional: list of keys
            assert set(keys_arg) == {"login.title", "nav.home"}, \
                f"Expected force keys, got {keys_arg}"

            # translate_file must NOT be called (full retranslation not triggered)
            assert not mock_translator.translate_file.called, \
                "translate_file should NOT be called when force keys are specified"

    def test_empty_value_nested_format_triggers_translation_in_process_outdated_files(self):
        """
        Regression: keys with empty-string values in nested JSON target files should be
        treated as missing in _process_outdated_files (previously only flat formats were handled).
        """
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.side_effect = lambda key, default: default

        source_file = "locales/en/messages.json"
        target_file = "locales/fr/messages.json"

        # Source has a key; target has the same key but with an empty string value
        source_content = {"greeting": "Hello"}
        target_content = {"greeting": ""}  # empty value — should trigger retranslation

        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_missing_keys_batch.return_value = {"greeting": "Bonjour"}

        # handler.extract_keys returns {"greeting"} for both source and target
        mock_handler = MagicMock()
        mock_handler.extract_keys.return_value = {"greeting"}

        with patch(
            "algebras.commands.translate_command.Config", return_value=mock_config
        ), patch(
            "algebras.commands.translate_command.Translator", return_value=mock_translator
        ), patch(
            "algebras.commands.translate_command._load_file_contents",
            return_value=(source_content, target_content, None, None),
        ), patch(
            "algebras.commands.translate_command.get_handler", return_value=mock_handler
        ), patch(
            "algebras.commands.translate_command.is_flat_format", return_value=False
        ), patch(
            "algebras.commands.translate_command.detect_format", return_value=None
        ), patch(
            "algebras.commands.translate_command._should_use_in_place", return_value=False
        ), patch(
            "algebras.commands.translate_command._write_translated_content"
        ), patch(
            "algebras.commands.translate_command.click.echo"
        ), patch(
            "builtins.print"
        ):
            # Pass pre-computed outdated_files list — routes to _process_outdated_files
            translate_command.execute(
                outdated_files=[(target_file, source_file)]
            )

            # translate_missing_keys_batch must be called because "greeting" has an empty value
            assert mock_translator.translate_missing_keys_batch.called, \
                "translate_missing_keys_batch should be called for empty-value keys in nested JSON"

            call_args = mock_translator.translate_missing_keys_batch.call_args
            keys_arg = call_args[0][2]  # third positional: list of keys
            assert "greeting" in keys_arg, \
                f"'greeting' should be treated as missing (empty value), got keys={keys_arg}"
