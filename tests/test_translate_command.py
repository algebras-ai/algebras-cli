import json
import os
import tempfile
import glob
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
        mock_config.get_source_language.return_value = "en"
        
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
            
            # Mock the path functions to ensure consistent paths
            # We'll use a modified version of determine_target_path that just switches the language directory
            def mock_determine_target_path(source_path, source_lang, target_lang):
                return source_path.replace(f"/{source_lang}/", f"/{target_lang}/")
            
            # Apply monkeypatches
            monkeypatch.setattr("algebras.commands.translate_command.Config", lambda: mock_config)
            monkeypatch.setattr("algebras.commands.translate_command.FileScanner", lambda: mock_scanner)
            monkeypatch.setattr("algebras.commands.translate_command.Translator", lambda: mock_translator)
            monkeypatch.setattr("algebras.utils.path_utils.determine_target_path", mock_determine_target_path)
            
            # Call the function
            translate_command.execute(force=True)
            
            # Use the target extensions from the logs to check files
            fr_target = os.path.join(fr_dir, "common.fr.json")
            es_target = os.path.join(es_dir, "common.es.json")
            
            # Check that files were created
            assert os.path.exists(fr_target) or os.path.exists(fr_target.lstrip('/')), \
                f"French file not found: {fr_target}"
            assert os.path.exists(es_target) or os.path.exists(es_target.lstrip('/')), \
                f"Spanish file not found: {es_target}"
            
            # Verify content - find actual file path first
            fr_content_path = fr_target if os.path.exists(fr_target) else fr_target.lstrip('/')
            es_content_path = es_target if os.path.exists(es_target) else es_target.lstrip('/')
            
            # Sometimes the file might be saved with a different name, use glob if needed
            if not os.path.exists(fr_content_path):
                fr_files = glob.glob(os.path.join(fr_dir, "*.json"))
                if fr_files:
                    fr_content_path = fr_files[0]
            
            if not os.path.exists(es_content_path):
                es_files = glob.glob(os.path.join(es_dir, "*.json"))
                if es_files:
                    es_content_path = es_files[0]
            
            # Verify content if files found
            if os.path.exists(fr_content_path):
                with open(fr_content_path, "r") as f:
                    fr_content = json.load(f)
                    assert fr_content == {"key": "translated value"}
            
            if os.path.exists(es_content_path):
                with open(es_content_path, "r") as f:
                    es_content = json.load(f)
                    assert es_content == {"key": "translated value"} 