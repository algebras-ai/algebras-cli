import os
import json
import unittest
from unittest.mock import patch, mock_open, Mock, ANY

from algebras.utils.lang_validator import (
    read_language_file,
    extract_all_keys,
    get_key_value,
    validate_language_files,
    find_outdated_keys,
    map_language_code
)


class TestLangValidator(unittest.TestCase):
    def setUp(self):
        # Test data
        self.source_data = {
            "welcome": "Welcome",
            "login": {
                "title": "Login",
                "username": "Username",
                "password": "Password"
            },
            "errors": {
                "required": "This field is required",
                "invalid": "Invalid input"
            }
        }
        
        self.target_data = {
            "welcome": "Bienvenue",
            "login": {
                "title": "Connexion",
                "username": "Nom d'utilisateur",
                # Missing password key
            },
            "errors": {
                "required": "Ce champ est obligatoire",
                "invalid": "Entrée invalide"
            }
        }
        
        # Sample file paths
        self.source_file = "en.json"
        self.target_file = "fr.json"
        
        # Fixed date strings for consistent tests
        self.older_date = "2023-01-01T12:00:00"
        self.newer_date = "2023-02-01T12:00:00"

    @patch('builtins.open', new_callable=mock_open, read_data='{"key1": "value1", "key2": {"nested": "value2"}}')
    def test_read_language_file_json(self, mock_file):
        result = read_language_file("test.json")
        
        self.assertEqual(result, {"key1": "value1", "key2": {"nested": "value2"}})
        mock_file.assert_called_once_with("test.json", 'r', encoding='utf-8')

    @patch('yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    def test_read_language_file_yaml(self, mock_file, mock_yaml_load):
        mock_yaml_load.return_value = {"key1": "value1", "key2": {"nested": "value2"}}
        
        result = read_language_file("test.yaml")
        
        self.assertEqual(result, {"key1": "value1", "key2": {"nested": "value2"}})
        mock_file.assert_called_once_with("test.yaml", 'r', encoding='utf-8')

    def test_extract_all_keys(self):
        keys = extract_all_keys(self.source_data)
        
        expected_keys = {
            "welcome",
            "login",
            "login.title",
            "login.username",
            "login.password",
            "errors",
            "errors.required",
            "errors.invalid"
        }
        
        self.assertEqual(keys, expected_keys)

    def test_get_key_value(self):
        # Test simple key
        value1 = get_key_value(self.source_data, "welcome")
        self.assertEqual(value1, "Welcome")
        
        # Test nested key
        value2 = get_key_value(self.source_data, "login.title")
        self.assertEqual(value2, "Login")
        
        value3 = get_key_value(self.source_data, "errors.required")
        self.assertEqual(value3, "This field is required")
        
        # Test non-existent key
        value4 = get_key_value(self.source_data, "nonexistent")
        self.assertIsNone(value4)
        
        value5 = get_key_value(self.source_data, "login.nonexistent")
        self.assertIsNone(value5)

    @patch('algebras.utils.lang_validator.read_language_file')
    def test_validate_language_files(self, mock_read_file):
        # Mock read_language_file to return test data
        mock_read_file.side_effect = [self.source_data, self.target_data]
        
        is_valid, missing_keys = validate_language_files(self.source_file, self.target_file)
        
        self.assertFalse(is_valid)
        self.assertEqual(missing_keys, {"login.password"})
        self.assertEqual(mock_read_file.call_count, 2)

    @patch('algebras.utils.lang_validator.is_git_available')
    def test_find_outdated_keys_no_git(self, mock_is_git_available):
        # Test when git is not available
        mock_is_git_available.return_value = False
        
        has_outdated, outdated_keys = find_outdated_keys(self.source_file, self.target_file)
        
        self.assertFalse(has_outdated)
        self.assertEqual(outdated_keys, set())
        mock_is_git_available.assert_called_once()

    @patch('algebras.utils.lang_validator.is_git_available')
    @patch('algebras.utils.lang_validator.is_git_repository')
    def test_find_outdated_keys_not_git_repo(self, mock_is_git_repo, mock_is_git_available):
        # Test when git is available but path is not in a git repository
        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = False
        
        has_outdated, outdated_keys = find_outdated_keys(self.source_file, self.target_file)
        
        self.assertFalse(has_outdated)
        self.assertEqual(outdated_keys, set())
        mock_is_git_available.assert_called_once()
        mock_is_git_repo.assert_called_once_with(self.source_file)

    @patch('algebras.utils.lang_validator.is_git_available')
    @patch('algebras.utils.lang_validator.is_git_repository')
    @patch('algebras.utils.lang_validator.read_language_file')
    @patch('algebras.utils.lang_validator.get_keys_last_modifications_batch')
    def test_find_outdated_keys_with_outdated(self, mock_get_keys_batch, mock_read_file, mock_is_git_repo, mock_is_git_available):
        # Update test data to include same keys but different values
        target_data_with_diff = self.target_data.copy()
        target_data_with_diff["welcome"] = "Old welcome text"  # Different from source
        
        # Mock dependencies
        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True
        mock_read_file.side_effect = [self.source_data, target_data_with_diff]
        
        # Mock the batch function to return dates for the "welcome" key
        def batch_side_effect(file_path, keys):
            if "welcome" in keys:
                if "en.json" in file_path:  # source file
                    return {"welcome": self.newer_date}
                else:  # target file
                    return {"welcome": self.older_date}
            return {}
        
        # Set the side effect for mock_get_keys_batch
        mock_get_keys_batch.side_effect = batch_side_effect
        
        has_outdated, outdated_keys = find_outdated_keys(self.source_file, self.target_file)
        
        self.assertTrue(has_outdated)
        self.assertEqual(outdated_keys, {"welcome"})
        mock_is_git_available.assert_called_once()
        mock_is_git_repo.assert_called_once_with(self.source_file)
        mock_read_file.assert_called()
        # Verify get_keys_last_modifications_batch was called for both files
        self.assertEqual(mock_get_keys_batch.call_count, 2)

    @patch('algebras.utils.lang_validator.is_git_available')
    @patch('algebras.utils.lang_validator.is_git_repository')
    @patch('algebras.utils.lang_validator.read_language_file')
    @patch('algebras.utils.lang_validator.compare_key_modifications')
    def test_find_outdated_keys_no_outdated(self, mock_compare, mock_read_file, mock_is_git_repo, mock_is_git_available):
        # Both source and target have same values
        source_data = {"key1": "value1", "key2": "value2"}
        target_data = {"key1": "value1", "key2": "value2"}
        
        # Mock dependencies
        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True
        mock_read_file.side_effect = [source_data, target_data]
        
        # Values are the same, so compare_key_modifications should not be called
        
        has_outdated, outdated_keys = find_outdated_keys(self.source_file, self.target_file)
        
        self.assertFalse(has_outdated)
        self.assertEqual(outdated_keys, set())
        mock_is_git_available.assert_called_once()
        mock_is_git_repo.assert_called_once_with(self.source_file)
        mock_read_file.assert_called()
        mock_compare.assert_not_called()  # Should not be called when values are the same

    @patch('algebras.utils.lang_validator.is_git_available')
    @patch('algebras.utils.lang_validator.is_git_repository')
    @patch('algebras.utils.lang_validator.read_language_file')
    @patch('algebras.utils.lang_validator.compare_key_modifications')
    def test_find_outdated_keys_with_exception(self, mock_compare, mock_read_file, mock_is_git_repo, mock_is_git_available):
        # Test error handling
        mock_is_git_available.return_value = True
        mock_is_git_repo.return_value = True
        mock_read_file.side_effect = Exception("Test exception")
        
        has_outdated, outdated_keys = find_outdated_keys(self.source_file, self.target_file)
        
        self.assertFalse(has_outdated)
        self.assertEqual(outdated_keys, set())
        mock_is_git_available.assert_called_once()
        mock_is_git_repo.assert_called_once_with(self.source_file)
        mock_read_file.assert_called_once()

    def test_map_language_code(self):
        # Test already 2-letter codes
        self.assertEqual(map_language_code("en"), "en")
        self.assertEqual(map_language_code("pt"), "pt")
        
        # Test codes with separators
        self.assertEqual(map_language_code("pt-BR"), "pt")
        self.assertEqual(map_language_code("en-US"), "en")
        self.assertEqual(map_language_code("fr_FR"), "fr")
        
        # Test case insensitivity
        self.assertEqual(map_language_code("PT-BR"), "pt")
        self.assertEqual(map_language_code("EN_US"), "en")
        
        # Test codes without separators
        self.assertEqual(map_language_code("eng"), "en")
        self.assertEqual(map_language_code("port"), "po")


if __name__ == "__main__":
    unittest.main() 