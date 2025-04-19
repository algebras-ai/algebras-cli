import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from algebras.commands import translate_command
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.services.translator import Translator

class TestTranslateCommand:
    """Tests for the translate_command module"""
    
    def test_translate_file_paths(self, monkeypatch):
        """Test that files are saved to the correct language-specific directories"""
        # Mock necessary components and functions
        mock_config = MagicMock(spec=Config)
        mock_config.get_languages.return_value = ["en", "fr", "es"]
        
        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_file.return_value = {"key": "translated value"}
        
        # Create temporary directory structure for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory and file
            en_dir = os.path.join(tmpdir, "locales", "en")
            os.makedirs(en_dir, exist_ok=True)
            source_file = os.path.join(en_dir, "common.json")
            
            with open(source_file, "w") as f:
                json.dump({"key": "value"}, f)
            
            # Create directories for target languages
            fr_dir = os.path.join(tmpdir, "locales", "fr")
            es_dir = os.path.join(tmpdir, "locales", "es")
            os.makedirs(fr_dir, exist_ok=True)
            os.makedirs(es_dir, exist_ok=True)
            
            # Mock file scanner to return our test file
            mock_scanner = MagicMock(spec=FileScanner)
            mock_scanner.group_files_by_language.return_value = {
                "en": [source_file],
                "fr": [],
                "es": []
            }
            
            # Apply monkeypatches
            monkeypatch.setattr("algebras.commands.translate_command.Config", lambda: mock_config)
            monkeypatch.setattr("algebras.commands.translate_command.FileScanner", lambda: mock_scanner)
            monkeypatch.setattr("algebras.commands.translate_command.Translator", lambda: mock_translator)
            
            # Call the function
            translate_command.execute(force=True)
            
            # Check that files were saved to the correct language directories
            fr_file = os.path.join(fr_dir, "common.json")
            es_file = os.path.join(es_dir, "common.json")
            
            assert os.path.exists(fr_file), "French file should be saved in fr directory"
            assert os.path.exists(es_file), "Spanish file should be saved in es directory"
            
            # Verify file content if needed
            with open(fr_file, "r") as f:
                fr_content = json.load(f)
                assert fr_content == {"key": "translated value"} 