"""
Tests for Android XML plural translation functionality

This test suite ensures that plural keys (stored as key.__plurals__ with dict values)
are correctly handled throughout the translation pipeline, preventing regression of
the bug where plural keys were not being translated.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from algebras.config import Config
from algebras.services.translator import Translator
from algebras.utils.android_xml_handler import (
    read_android_xml_file,
    write_android_xml_file,
    write_android_xml_file_in_place
)


class TestAndroidXMLPluralTranslation:
    """Tests for Android XML plural translation functionality"""
    
    def test_android_xml_plurals_are_read_correctly(self):
        """Test that plural elements are correctly extracted with .__plurals__ suffix"""
        # Create a temporary XML file with plural elements
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="regular_key">Regular string</string>
    <plurals name="Quiz.timer_format">
        <item quantity="one">%1$d minute</item>
        <item quantity="other">%1$d minutes</item>
    </plurals>
    <plurals name="Quiz.passing_score_points_format">
        <item quantity="one">%1$d point</item>
        <item quantity="other">%1$d points</item>
    </plurals>
    <string name="another_key">Another string</string>
</resources>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            temp_file = f.name
            f.write(xml_content)
        
        try:
            # Read the XML file
            result = read_android_xml_file(temp_file)
            
            # Verify regular strings are read correctly
            assert "regular_key" in result
            assert result["regular_key"] == "Regular string"
            assert "another_key" in result
            assert result["another_key"] == "Another string"
            
            # Verify plural keys have .__plurals__ suffix
            assert "Quiz.timer_format.__plurals__" in result
            assert "Quiz.passing_score_points_format.__plurals__" in result
            
            # Verify plural values are dictionaries with quantity keys
            timer_plurals = result["Quiz.timer_format.__plurals__"]
            assert isinstance(timer_plurals, dict)
            assert "one" in timer_plurals
            assert "other" in timer_plurals
            assert timer_plurals["one"] == "%1$d minute"
            assert timer_plurals["other"] == "%1$d minutes"
            
            points_plurals = result["Quiz.passing_score_points_format.__plurals__"]
            assert isinstance(points_plurals, dict)
            assert "one" in points_plurals
            assert "other" in points_plurals
            assert points_plurals["one"] == "%1$d point"
            assert points_plurals["other"] == "%1$d points"
            
        finally:
            os.unlink(temp_file)
    
    def test_xml_recognized_as_flat_format(self, monkeypatch):
        """Test that .xml files are recognized as flat format in translation logic"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        translator = Translator()

        # Mock batch processor
        from algebras.services.batch_processor import BatchResult
        mock_batch_processor = MagicMock()
        mock_batch_processor.process.return_value = BatchResult(
            translations=["Bonjour"],
            error_stats={"5xx": [], "429": [], "other": []},
            failed_batches=[],
            successful_batches=1,
            total_batches=1,
        )
        translator._batch_processor = mock_batch_processor

        # Test with a source file path ending in .xml
        source_content = {
            "test_key": "Hello"
        }
        target_content = {}
        missing_keys = ["test_key"]
        
        # This should work because .xml is now recognized as flat format
        result = translator.translate_missing_keys_batch(
            source_content,
            target_content,
            missing_keys,
            "fr",
            source_file_path="strings/values/test.xml"
        )
        
        # Verify the key was translated
        assert "test_key" in result
        assert result["test_key"] == "Bonjour"
    
    def test_translate_missing_plural_keys_batch(self, monkeypatch):
        """
        Core regression test: Verify plural keys are correctly translated.
        
        This test would have caught the original bug where plural keys
        (stored as dicts) were being skipped during translation.
        """
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        translator = Translator()

        # Mock batch processor to return German translations
        from algebras.services.batch_processor import BatchResult
        mock_batch_processor = MagicMock()
        
        def mock_process(texts, source_lang, target_lang, ui_safe=False, glossary_id="", on_batch_complete=None, translate_text_func=None):
            translations = []
            for text in texts:
                # Simulate German translations
                translation_map = {
                    "%1$d minute": "%1$d Minute",
                    "%1$d minutes": "%1$d Minuten",
                }
                translations.append(translation_map.get(text, text))
            return BatchResult(
                translations=translations,
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )
        
        mock_batch_processor.process = mock_process
        translator._batch_processor = mock_batch_processor

        # Source content with plural key (how it's stored internally)
        source_content = {
            "Quiz.timer_format.__plurals__": {
                "one": "%1$d minute",
                "other": "%1$d minutes"
            }
        }
        
        target_content = {}
        missing_keys = ["Quiz.timer_format.__plurals__"]
        
        # Translate missing plural keys
        result = translator.translate_missing_keys_batch(
            source_content,
            target_content,
            missing_keys,
            "de",
            source_file_path="strings/values/test.xml"
        )
        
        # Verify plural key is in result
        assert "Quiz.timer_format.__plurals__" in result
        
        # Verify it's a dictionary with the correct structure
        assert isinstance(result["Quiz.timer_format.__plurals__"], dict)
        
        # Verify both plural forms were translated
        plural_dict = result["Quiz.timer_format.__plurals__"]
        assert "one" in plural_dict
        assert "other" in plural_dict
        assert plural_dict["one"] == "%1$d Minute"
        assert plural_dict["other"] == "%1$d Minuten"
    
    def test_translate_multiple_plural_keys_batch(self, monkeypatch):
        """Test translating multiple plural keys simultaneously with regular strings"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        translator = Translator()

        # Mock batch processor
        from algebras.services.batch_processor import BatchResult
        mock_batch_processor = MagicMock()
        
        def mock_process(texts, source_lang, target_lang, ui_safe=False, glossary_id="", on_batch_complete=None, translate_text_func=None):
            translations = []
            translation_map = {
                "%1$d minute": "%1$d Minute",
                "%1$d minutes": "%1$d Minuten",
                "%1$d point": "%1$d Punkt",
                "%1$d points": "%1$d Punkte",
                "%1$d point scored on the question": "%1$d Punkt für die Frage erzielt",
                "%1$d points scored on the question": "%1$d Punkte für die Frage erzielt",
                "Start": "Anfang",
                "Finish": "Fertig",
            }
            for text in texts:
                translations.append(translation_map.get(text, text))
            return BatchResult(
                translations=translations,
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )
        
        mock_batch_processor.process = mock_process
        translator._batch_processor = mock_batch_processor

        # Source content with multiple plural keys and regular strings
        source_content = {
            "Quiz.start": "Start",
            "Quiz.timer_format.__plurals__": {
                "one": "%1$d minute",
                "other": "%1$d minutes"
            },
            "Quiz.passing_score_points_format.__plurals__": {
                "one": "%1$d point",
                "other": "%1$d points"
            },
            "Quiz.finish": "Finish",
            "Quiz.question_score_format.__plurals__": {
                "one": "%1$d point scored on the question",
                "other": "%1$d points scored on the question"
            }
        }
        
        target_content = {}
        missing_keys = [
            "Quiz.start",
            "Quiz.timer_format.__plurals__",
            "Quiz.passing_score_points_format.__plurals__",
            "Quiz.finish",
            "Quiz.question_score_format.__plurals__"
        ]
        
        # Translate all missing keys
        result = translator.translate_missing_keys_batch(
            source_content,
            target_content,
            missing_keys,
            "de",
            source_file_path="strings/values/test.xml"
        )
        
        # Verify regular strings were translated
        assert result["Quiz.start"] == "Anfang"
        assert result["Quiz.finish"] == "Fertig"
        
        # Verify all plural keys were translated correctly
        assert "Quiz.timer_format.__plurals__" in result
        assert isinstance(result["Quiz.timer_format.__plurals__"], dict)
        assert result["Quiz.timer_format.__plurals__"]["one"] == "%1$d Minute"
        assert result["Quiz.timer_format.__plurals__"]["other"] == "%1$d Minuten"
        
        assert "Quiz.passing_score_points_format.__plurals__" in result
        assert isinstance(result["Quiz.passing_score_points_format.__plurals__"], dict)
        assert result["Quiz.passing_score_points_format.__plurals__"]["one"] == "%1$d Punkt"
        assert result["Quiz.passing_score_points_format.__plurals__"]["other"] == "%1$d Punkte"
        
        assert "Quiz.question_score_format.__plurals__" in result
        assert isinstance(result["Quiz.question_score_format.__plurals__"], dict)
        assert result["Quiz.question_score_format.__plurals__"]["one"] == "%1$d Punkt für die Frage erzielt"
        assert result["Quiz.question_score_format.__plurals__"]["other"] == "%1$d Punkte für die Frage erzielt"
    
    def test_write_android_xml_with_plurals(self):
        """Test that write_android_xml_file_in_place correctly handles plural keys"""
        # Create initial XML file with one plural
        initial_xml = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="regular_key">Regular value</string>
    <plurals name="Plural.tasks">
        <item quantity="one">%1$d task</item>
        <item quantity="other">%1$d tasks</item>
    </plurals>
</resources>"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
            temp_file = f.name
            f.write(initial_xml)
        
        try:
            # Update with new plural keys
            updated_content = {
                "regular_key": "Regular value",
                "Plural.tasks.__plurals__": {
                    "one": "%1$d task",
                    "other": "%1$d tasks"
                },
                "Quiz.timer_format.__plurals__": {
                    "one": "%1$d Minute",
                    "other": "%1$d Minuten"
                }
            }
            
            # Write in place - should add the new plural
            write_android_xml_file_in_place(
                temp_file,
                updated_content,
                keys_to_update={"Quiz.timer_format.__plurals__"}
            )
            
            # Read back and verify
            result = read_android_xml_file(temp_file)
            
            # Verify both plurals exist
            assert "Plural.tasks.__plurals__" in result
            assert "Quiz.timer_format.__plurals__" in result
            
            # Verify the new plural was added correctly
            timer_plural = result["Quiz.timer_format.__plurals__"]
            assert isinstance(timer_plural, dict)
            assert timer_plural["one"] == "%1$d Minute"
            assert timer_plural["other"] == "%1$d Minuten"
            
        finally:
            os.unlink(temp_file)
