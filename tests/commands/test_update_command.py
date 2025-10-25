import os
import unittest
from unittest.mock import patch, Mock, call

from colorama import Fore

from algebras.commands.update_command import execute


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


if __name__ == "__main__":
    unittest.main() 