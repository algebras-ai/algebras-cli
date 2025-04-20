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
        
        # Verify that translate_command.execute was called for each target language
        mock_translate.execute.assert_has_calls([
            call("fr", force=True, only_missing=True),
            call("es", force=True, only_missing=True),
            call("de", force=True, only_missing=True)
        ])

    @patch('algebras.commands.update_command.Config')
    @patch('algebras.commands.update_command.FileScanner')
    @patch('algebras.commands.update_command.is_git_available')
    @patch('algebras.commands.update_command.validate_language_files')
    @patch('os.path.getmtime')
    def test_execute_no_git_available(self, mock_getmtime, mock_validate, mock_is_git_available,
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
        
        # Mock git NOT available
        mock_is_git_available.return_value = False
        
        # Mock file modification times (all files same age)
        mock_getmtime.return_value = 100
        
        # Mock validation results (all files valid)
        mock_validate.return_value = (True, set())
        
        with patch('algebras.commands.update_command.click.echo') as mock_echo:
            execute()
            
            # Check that git warning was displayed
            mock_echo.assert_any_call(
                f"{Fore.YELLOW}Git is not available. Skipping detection of updated keys.\x1b[0m"
            )
            
            # And that "all up to date" message was also displayed
            mock_echo.assert_any_call(
                f"{Fore.GREEN}All translations are up to date and complete.\x1b[0m"
            )
        
        # find_outdated_keys should not be called when git is not available
        self.assertEqual(mock_is_git_available.call_count, 1)

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
            
            # Verify that translate_command.execute was called only for fr
            mock_translate.execute.assert_called_once_with("fr", force=True, only_missing=True)
        
        # Only one target language should be processed
        self.assertEqual(mock_validate.call_count, 1)
        # Verify find_outdated_keys was called
        mock_find_outdated.assert_called_once()


if __name__ == "__main__":
    unittest.main() 