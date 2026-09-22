import os
import unittest
from unittest.mock import patch, Mock, call

from colorama import Fore

from algebras.commands.update_command import execute, find_matching_source_file


class TestUpdateCommand(unittest.TestCase):
    def setUp(self):
        # Sample language data
        self.languages = ["en", "fr", "es", "de"]
        self.source_language = "en"
        
        # Sample file paths
        self.en_file = "locales/en.json"
        self.fr_file = "locales/fr.json"
        self.es_file = "locales/es.json"
        self.de_file = "locales/de.json"
        
        # Sample file mapping
        self.files_by_language = {
            "en": [self.en_file],
            "fr": [self.fr_file],
            "es": [self.es_file],
            "de": [self.de_file]
        }
        
        # Sample missing keys
        self.missing_keys = {"welcome.message", "errors.required"}

    @patch('algebras.commands.update_command.Config')
    def test_execute_no_config(self, mock_config_class):
        # Mock Config to indicate no configuration exists
        mock_config = Mock()
        mock_config.exists.return_value = False
        mock_config_class.return_value = mock_config
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute()
            
            # Check that the error message was displayed
            mock_echo.assert_called_once_with(
                f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m"
            )
        
        mock_config.exists.assert_called_once()
        mock_config.load.assert_not_called()

    @patch('algebras.commands.update_command.Config')
    def test_execute_invalid_language(self, mock_config_class):
        # Mock Config to return specific languages
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = self.languages
        mock_config.check_deprecated_format.return_value = False
        mock_config_class.return_value = mock_config
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute(language="invalid_lang")
            
            # Check that the error message was displayed
            mock_echo.assert_called_once_with(
                f"{Fore.RED}Language 'invalid_lang' is not configured in your project.\x1b[0m"
            )
        
        mock_config.exists.assert_called_once()
        mock_config.load.assert_called_once()
        mock_config.get_languages.assert_called_once()

    @patch('algebras.commands.update_command.Config')
    def test_execute_no_target_languages(self, mock_config_class):
        # Mock Config to return only the source language
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en"]
        mock_config.get_source_language.return_value = "en"
        mock_config.check_deprecated_format.return_value = False
        mock_config_class.return_value = mock_config
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute()
            
            # Check that the warning message was displayed
            mock_echo.assert_called_once_with(
                f"{Fore.YELLOW}No target languages configured. Add languages with 'algebras add <language>'.\x1b[0m"
            )
        
        mock_config.exists.assert_called_once()
        mock_config.load.assert_called_once()
        mock_config.get_languages.assert_called_once()
        mock_config.get_source_language.assert_called_once()

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    def test_execute_no_source_files(self, mock_scanner_class, mock_config_class):
        # Mock Config
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = self.languages
        mock_config.get_source_language.return_value = self.source_language
        mock_config_class.return_value = mock_config
        
        # Mock FileScanner to return empty source files
        mock_scanner = Mock()
        mock_scanner.group_files_by_language.return_value = {
            "fr": [self.fr_file],
            "es": [self.es_file],
            "de": [self.de_file]
            # No "en" source files
        }
        mock_scanner_class.return_value = mock_scanner
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute()
            
            # Check that the warning message was displayed
            mock_echo.assert_any_call(
                f"{Fore.YELLOW}No source files found for language '{self.source_language}'.\x1b[0m"
            )
        
        mock_config.exists.assert_called_once()
        mock_config.load.assert_called_once()
        mock_scanner.group_files_by_language.assert_called_once()

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    @patch('algebras.commands.update_command.is_git_available')
    @patch('algebras.commands.update_command.is_git_repository')
    @patch('algebras.commands.update_command.validate_language_files')
    @patch('algebras.commands.update_command.find_outdated_keys')
    @patch('algebras.commands.update_command.translate_command')
    @patch('os.path.getmtime')
    def test_execute_with_all_outdated_types(self, mock_getmtime, mock_translate, mock_find_outdated,
                                            mock_validate, mock_is_git_repo, mock_is_git_available,
                                            mock_scanner_class, mock_config_class):
        # Mock Config
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = self.languages
        mock_config.get_source_language.return_value = self.source_language
        mock_config_class.return_value = mock_config
        
        # Mock FileScanner
        mock_scanner = Mock()
        mock_scanner.group_files_by_language.return_value = self.files_by_language
        mock_scanner_class.return_value = mock_scanner
        
        # Mock git availability
        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True
        
        # Mock file modification times (source is newer than target)
        mock_getmtime.side_effect = lambda file: 200 if file == self.en_file else 100
        
        # Mock validation results (fr has missing keys, es is valid)
        mock_validate.side_effect = [
            (False, self.missing_keys),  # fr file
            (True, set()),             # es file
            (True, set())              # de file
        ]
        
        # Mock git outdated keys detection (de has outdated keys)
        mock_find_outdated.side_effect = [
            (False, set()),            # fr file
            (False, set()),            # es file
            (True, {"home.title"})     # de file
        ]
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute()
            
            # Check that appropriate messages were displayed
            expected_calls = [
                call(f"{Fore.YELLOW}Found 3 outdated translations (file modification time).\x1b[0m"),
                call(f"{Fore.YELLOW}Found 1 translations with missing keys.\x1b[0m"),
                call(f"{Fore.YELLOW}Found 1 translations with outdated keys (based on git history).\x1b[0m"),
                # More calls for updating files...
            ]
            mock_echo.assert_has_calls(expected_calls, any_order=False)
        
        # Verify that translate_command.execute was called for target languages
        # The actual calls will include additional parameters, so we'll check for partial matches
        assert mock_translate.execute.call_count >= 3
        
        # Check that each language was passed to translate_command.execute
        languages_called = []
        for call_args in mock_translate.execute.call_args_list:
            args, kwargs = call_args
            if args and args[0] in ["fr", "es", "de"]:
                languages_called.append(args[0])
        
        # Verify all languages were included
        assert set(languages_called) == {"fr", "es", "de"}, f"Not all languages were processed: {languages_called}"
        
        # Verify force and only_missing parameters were passed
        for call_args in mock_translate.execute.call_args_list:
            _, kwargs = call_args
            assert kwargs.get("force") is True, "force parameter was not set to True"
            assert kwargs.get("only_missing") is True, "only_missing parameter was not set to True"

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    @patch('algebras.commands.update_command.is_git_available')
    @patch('algebras.commands.update_command.is_git_repository')
    @patch('algebras.commands.update_command.validate_language_files')
    @patch('algebras.commands.update_command.find_outdated_keys')
    @patch('algebras.commands.update_command.translate_command')
    @patch('os.path.getmtime')
    def test_execute_no_git_available(self, mock_getmtime, mock_translate, mock_find_outdated,
                                     mock_validate, mock_is_git_repo, mock_is_git_available,
                                     mock_scanner_class, mock_config_class):
        # Mock Config
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = self.languages
        mock_config.get_source_language.return_value = self.source_language
        mock_config_class.return_value = mock_config
        
        # Mock FileScanner
        mock_scanner = Mock()
        mock_scanner.group_files_by_language.return_value = self.files_by_language
        mock_scanner_class.return_value = mock_scanner
        
        # Mock git availability to False
        mock_is_git_available.return_value = False
        mock_is_git_repo.return_value = False
        
        # Mock file modification times
        mock_getmtime.side_effect = lambda file: 100  # All files have the same mtime
        
        # Mock validation results
        mock_validate.return_value = (True, set())  # No missing keys
        
        # Unused in this test since git is not available
        mock_find_outdated.return_value = (False, set())
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute()
            
            # Verify git-related messages
            mock_echo.assert_any_call(f"{Fore.YELLOW}Git is not available. Skipping detection of updated keys.\x1b[0m")
        
            # Verify that we still checked for outdated files by modification time
            mock_getmtime.assert_called()
            
            # Verify that find_outdated_keys was NOT called (git not available)
            mock_find_outdated.assert_not_called()
            
            # Verify that the "all up to date" message was displayed
            mock_echo.assert_any_call(f"{Fore.GREEN}All translations are up to date and complete.\x1b[0m")

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    @patch('algebras.commands.update_command.is_git_available')
    @patch('algebras.commands.update_command.is_git_repository')
    @patch('algebras.commands.update_command.validate_language_files')
    @patch('algebras.commands.update_command.find_outdated_keys')
    @patch('algebras.commands.update_command.translate_command')
    @patch('os.path.getmtime')
    def test_execute_selective_language(self, mock_getmtime, mock_translate, mock_find_outdated,
                                       mock_validate, mock_is_git_available, mock_is_git_repo,
                                       mock_scanner_class, mock_config_class):
        # Mock Config
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = self.languages
        mock_config.get_source_language.return_value = self.source_language
        mock_config_class.return_value = mock_config
        
        # Mock FileScanner
        mock_scanner = Mock()
        mock_scanner.group_files_by_language.return_value = self.files_by_language
        mock_scanner_class.return_value = mock_scanner
        
        # Mock git availability and repository
        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True
        
        # Mock file modification times
        mock_getmtime.side_effect = lambda file: 200 if file == self.en_file else 100
        
        # Mock validation results
        mock_validate.return_value = (False, self.missing_keys)
        
        # Mock git outdated keys detection
        mock_find_outdated.return_value = (True, {"navbar.login"})
        
        with patch('algebras.commands.update_command.click.echo'):
            # Execute with specific language
            execute(language="fr")
            
            # Verify that translate_command.execute was called for fr
            assert mock_translate.execute.call_count > 0
            
            # Check that the language 'fr' was passed to translate_command.execute
            language_called = False
            for call_args in mock_translate.execute.call_args_list:
                args, kwargs = call_args
                if args and args[0] == "fr":
                    language_called = True
                    # Also check the forced and only_missing parameters
                    assert kwargs.get("force") is True, "force parameter was not set to True"
                    assert kwargs.get("only_missing") is True, "only_missing parameter was not set to True"
            
            assert language_called, "Language 'fr' wasn't passed to translate_command.execute"

    def test_find_matching_source_file_lproj_directories(self):
        """
        Regression test: the standard iOS locale-directory convention
        (en.lproj/Localizable.stringsdict, fr.lproj/Localizable.stringsdict)
        embeds the language as a ".lproj" directory suffix, not as an isolated
        "/{lang}/" path segment or a filename suffix. Without matching this
        pattern, find_matching_source_file returns None, so update_command
        never pairs the files together and silently treats the project as
        fully up to date.
        """
        source_files = ["en.lproj/Localizable.stringsdict"]
        matched = find_matching_source_file(
            "fr.lproj/Localizable.stringsdict", source_files, "fr", "en"
        )
        self.assertEqual(matched, "en.lproj/Localizable.stringsdict")

        # Also works nested under a project directory
        nested_source_files = ["MyApp/en.lproj/Localizable.stringsdict"]
        nested_matched = find_matching_source_file(
            "MyApp/fr.lproj/Localizable.stringsdict", nested_source_files, "fr", "en"
        )
        self.assertEqual(nested_matched, "MyApp/en.lproj/Localizable.stringsdict")

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    @patch('algebras.commands.update_command.is_git_available')
    @patch('algebras.commands.update_command.is_git_repository')
    @patch('algebras.commands.update_command.validate_language_files')
    @patch('algebras.commands.update_command.find_outdated_keys')
    @patch('algebras.commands.update_command.translate_command')
    @patch('os.path.getmtime')
    def test_execute_translates_git_outdated_keys_with_full(
        self, mock_getmtime, mock_translate, mock_find_outdated, mock_validate,
        mock_is_git_repo, mock_is_git_available, mock_scanner_class, mock_config_class
    ):
        """
        Regression test: a key whose source value changed (detected via git
        history) but whose file mtime didn't independently trip the
        modification-time check (e.g. both files touched in the same
        commit/checkout) must still reach translate_command.execute via
        outdated_keys_files when --full (only_missing=False) is used. This
        loop was previously dead code, removed in a past commit and never
        restored, so git-detected outdated keys were reported but never
        actually retranslated regardless of flags.
        """
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config_class.return_value = mock_config

        mock_scanner = Mock()
        mock_scanner.group_files_by_language.return_value = {
            "en": [self.en_file],
            "fr": [self.fr_file],
        }
        mock_scanner_class.return_value = mock_scanner

        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True

        # Same mtime for source and target - the modification-time path must not fire
        mock_getmtime.return_value = 100

        # No missing keys
        mock_validate.return_value = (True, set())

        # Git history says "greeting" changed
        mock_find_outdated.return_value = (True, {"greeting"})

        with patch('algebras.commands.update_command.click.echo'):
            execute(only_missing=False)

        outdated_calls = [
            kwargs for _, kwargs in mock_translate.execute.call_args_list
            if kwargs.get("outdated_keys_files")
        ]
        assert outdated_calls, (
            "translate_command.execute was never called with outdated_keys_files - "
            "git-detected outdated keys are being silently dropped"
        )
        assert outdated_calls[0]["outdated_keys_files"] == [
            (self.fr_file, {"greeting"}, self.en_file)
        ]
        assert outdated_calls[0]["only_missing"] is False

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    @patch('algebras.commands.update_command.is_git_available')
    @patch('algebras.commands.update_command.is_git_repository')
    @patch('algebras.commands.update_command.validate_language_files')
    @patch('algebras.commands.update_command.find_outdated_keys')
    @patch('algebras.commands.update_command.translate_command')
    @patch('os.path.getmtime')
    def test_execute_default_mode_passes_only_missing_true_for_outdated_keys(
        self, mock_getmtime, mock_translate, mock_find_outdated, mock_validate,
        mock_is_git_repo, mock_is_git_available, mock_scanner_class, mock_config_class
    ):
        """
        Without --full, only_missing stays True end-to-end, matching its
        documented meaning of "only missing keys, don't touch existing ones" -
        the outdated_keys_files call still happens (so it's reported), but
        only_missing=True flows through so _process_outdated_keys_files skips
        actually retranslating them.
        """
        mock_config = Mock()
        mock_config.exists.return_value = True
        mock_config.get_languages.return_value = ["en", "fr"]
        mock_config.get_source_language.return_value = "en"
        mock_config_class.return_value = mock_config

        mock_scanner = Mock()
        mock_scanner.group_files_by_language.return_value = {
            "en": [self.en_file],
            "fr": [self.fr_file],
        }
        mock_scanner_class.return_value = mock_scanner

        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True
        mock_getmtime.return_value = 100
        mock_validate.return_value = (True, set())
        mock_find_outdated.return_value = (True, {"greeting"})

        with patch('algebras.commands.update_command.click.echo'):
            execute()  # default: only_missing=True

        outdated_calls = [
            kwargs for _, kwargs in mock_translate.execute.call_args_list
            if kwargs.get("outdated_keys_files")
        ]
        assert outdated_calls
        assert outdated_calls[0]["only_missing"] is True


if __name__ == "__main__":
    unittest.main()