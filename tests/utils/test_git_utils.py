import os
import json
import yaml
import unittest
from unittest.mock import patch, Mock, mock_open, call

from algebras.utils.git_utils import (
    is_git_available,
    is_git_repository,
    get_last_modified_date,
    read_file_content,
    get_key_last_modification,
    compare_key_modifications
)


class TestGitUtils(unittest.TestCase):
    def setUp(self):
        # Create a test directory structure
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_files")
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Sample file paths
        self.source_file = os.path.join(self.test_dir, "en.json")
        self.target_file = os.path.join(self.test_dir, "fr.json")
        
        # Fixed date strings (ISO format) without milliseconds for consistent tests
        self.older_date = "2023-01-01T12:00:00"
        self.newer_date = "2023-02-01T12:00:00"

    def tearDown(self):
        # Clean up test files if they exist
        if os.path.exists(self.source_file):
            os.remove(self.source_file)
        if os.path.exists(self.target_file):
            os.remove(self.target_file)
        
        # Remove test directory if it exists
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    @patch('subprocess.run')
    def test_is_git_available_success(self, mock_run):
        # Mock successful execution of git --version
        mock_process = Mock()
        mock_process.returncode = 0
        mock_run.return_value = mock_process
        
        self.assertTrue(is_git_available())
        mock_run.assert_called_once_with(['git', '--version'], capture_output=True, check=True)

    @patch('subprocess.run')
    def test_is_git_available_failure(self, mock_run):
        # Mock failed execution of git --version
        mock_run.side_effect = FileNotFoundError()
        
        self.assertFalse(is_git_available())
        mock_run.assert_called_once_with(['git', '--version'], capture_output=True, check=True)

    @patch('subprocess.run')
    def test_is_git_repository_success(self, mock_run):
        # Mock successful check for git repository
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "true"
        mock_run.return_value = mock_process
        
        self.assertTrue(is_git_repository(self.source_file))
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_is_git_repository_failure(self, mock_run):
        # Mock failed check for git repository
        mock_process = Mock()
        mock_process.returncode = 128
        mock_process.stdout = "fatal: not a git repository"
        mock_run.return_value = mock_process
        
        self.assertFalse(is_git_repository(self.source_file))
        mock_run.assert_called_once()

    @patch('algebras.utils.git_utils.is_git_repository')
    @patch('subprocess.run')
    def test_get_last_modified_date(self, mock_run, mock_is_git_repo):
        # Mock git repository check
        mock_is_git_repo.return_value = True
        
        # Mock successful git log command
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = self.newer_date
        mock_run.return_value = mock_process
        
        result = get_last_modified_date(self.source_file)
        self.assertEqual(result, self.newer_date)
        mock_run.assert_called_once()

    @patch('algebras.utils.git_utils.is_git_repository')
    def test_get_last_modified_date_not_git_repo(self, mock_is_git_repo):
        # Mock git repository check to return False
        mock_is_git_repo.return_value = False
        
        result = get_last_modified_date(self.source_file)
        self.assertIsNone(result)
        mock_is_git_repo.assert_called_once_with(self.source_file)

    @patch('builtins.open', new_callable=mock_open, read_data='{"key1": "value1", "key2": {"nested": "value2"}}')
    def test_read_file_content_json(self, mock_file):
        # Test reading a JSON file
        result = read_file_content(self.source_file)
        
        self.assertEqual(result, {"key1": "value1", "key2": {"nested": "value2"}})
        mock_file.assert_called_once_with(self.source_file, 'r', encoding='utf-8')

    @patch('yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    def test_read_file_content_yaml(self, mock_file, mock_yaml_load):
        # Test reading a YAML file
        mock_yaml_load.return_value = {"key1": "value1", "key2": {"nested": "value2"}}
        
        # Change file extension to .yaml
        yaml_file = os.path.join(self.test_dir, "en.yaml")
        
        result = read_file_content(yaml_file)
        
        self.assertEqual(result, {"key1": "value1", "key2": {"nested": "value2"}})
        mock_file.assert_called_once_with(yaml_file, 'r', encoding='utf-8')
        mock_yaml_load.assert_called_once()

    @patch('algebras.utils.git_utils.is_git_repository')
    @patch('subprocess.run')
    def test_get_key_last_modification(self, mock_run, mock_is_git_repo):
        # Mock git repository check
        mock_is_git_repo.return_value = True
        
        # Create mock result for the second git command with date in stdout
        mock_process = Mock()
        mock_process.returncode = 0
        # Git will return a list of dates, with the newest first
        mock_process.stdout = f"{self.newer_date}\n"
        
        # Always return this successful result for any subprocess call
        mock_run.return_value = mock_process
        
        # Call the function we want to test
        result = get_key_last_modification(self.source_file, "key1.nested")
        
        # Verify we get the expected date (the first line from stdout)
        self.assertEqual(result, self.newer_date)
        mock_is_git_repo.assert_called_once_with(self.source_file)

    @patch('algebras.utils.git_utils.get_key_last_modification')
    def test_compare_key_modifications_source_newer(self, mock_get_key_last_mod):
        # Mock get_key_last_modification to return different dates
        mock_get_key_last_mod.side_effect = [self.newer_date, self.older_date]
        
        is_outdated, source_date, target_date = compare_key_modifications(
            self.source_file, self.target_file, "key1.nested"
        )
        
        self.assertTrue(is_outdated)
        self.assertEqual(source_date, self.newer_date)
        self.assertEqual(target_date, self.older_date)
        self.assertEqual(mock_get_key_last_mod.call_count, 2)

    @patch('algebras.utils.git_utils.get_key_last_modification')
    def test_compare_key_modifications_target_newer(self, mock_get_key_last_mod):
        # Mock get_key_last_modification to return different dates
        mock_get_key_last_mod.side_effect = [self.older_date, self.newer_date]
        
        is_outdated, source_date, target_date = compare_key_modifications(
            self.source_file, self.target_file, "key1.nested"
        )
        
        self.assertFalse(is_outdated)
        self.assertEqual(source_date, self.older_date)
        self.assertEqual(target_date, self.newer_date)
        self.assertEqual(mock_get_key_last_mod.call_count, 2)

    @patch('algebras.utils.git_utils.get_key_last_modification')
    def test_compare_key_modifications_dates_unavailable(self, mock_get_key_last_mod):
        # Mock get_key_last_modification to return None
        mock_get_key_last_mod.side_effect = [None, self.newer_date]
        
        is_outdated, source_date, target_date = compare_key_modifications(
            self.source_file, self.target_file, "key1.nested"
        )
        
        self.assertFalse(is_outdated)
        self.assertIsNone(source_date)
        self.assertEqual(target_date, self.newer_date)
        self.assertEqual(mock_get_key_last_mod.call_count, 2)


if __name__ == "__main__":
    unittest.main() 