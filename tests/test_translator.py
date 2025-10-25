"""
Tests for the Translator class
"""

import os
import json
import yaml
from unittest.mock import patch, MagicMock, mock_open

import pytest

from algebras.config import Config
from algebras.services.translator import Translator


class TestTranslator:
    """Tests for the Translator class"""

    def test_init(self, monkeypatch):
        """Test initialization of Translator"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Verify Config was used correctly
        assert mock_config.exists.called
        assert mock_config.load.called
        assert mock_config.get_api_config.called
        assert translator.api_config == {"provider": "algebras-ai"}

    def test_init_no_config(self, monkeypatch):
        """Test initialization of Translator with no config file"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Initialize Translator - should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            Translator()

    def test_translate_text(self, monkeypatch):
        """Test translate_text method"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock Algebras AI API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"translation": "Bonjour le monde"}
        mock_response.status_code = 200
        
        monkeypatch.setattr("algebras.services.translator.requests.post", lambda *args, **kwargs: mock_response)

        # Initialize Translator
        translator = Translator()
        result = translator.translate_text("Hello world", "en", "fr")

        # Verify the translation
        assert result == "Bonjour le monde"

    def test_translate_text_unsupported_provider(self, monkeypatch):
        """Test translate_text method with unsupported provider"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "unsupported"}

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Mock the cache to return None (cache miss)
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Test translate_text with unsupported provider
        with pytest.raises(ValueError, match="Unsupported provider: unsupported"):
            translator.translate_text("Hello world", "en", "fr")

    def test_translate_text_no_api_key(self, monkeypatch):
        """Test translate_text method with no API key"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Ensure no API key in environment
        monkeypatch.delenv("ALGEBRAS_API_KEY", raising=False)
        
        # Mock the cache to return None (cache miss)
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Test translate_text with no API key - should raise an error when making the API call
        with pytest.raises(Exception):  # Algebras AI will raise an exception when API key is missing
            translator.translate_text("Hello world", "en", "fr")

    def test_translate_file_json(self, monkeypatch):
        """Test translate_file method with JSON file"""
        # Sample JSON content
        json_content = {
            "welcome": "Welcome to our application!",
            "login": {
                "title": "Login",
                "submit": "Sign In"
            }
        }
        
        # Expected translation
        expected_translation = {
            "welcome": "Bienvenue dans notre application!",
            "login": {
                "title": "Connexion",
                "submit": "Se connecter"
            }
        }

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_languages.return_value = ["en", "fr"]

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock open to return the JSON content
        m = mock_open(read_data=json.dumps(json_content))
        
        # Mock translate_text to return expected translations
        def mock_translate_text(text, source_lang, target_lang, ui_safe=False, glossary_id=None):
            if text == "Welcome to our application!":
                return "Bienvenue dans notre application!"
            elif text == "Login":
                return "Connexion"
            elif text == "Sign In":
                return "Se connecter"
            return text
        
        with patch("builtins.open", m), \
             patch.object(Translator, "translate_text", side_effect=mock_translate_text):
            
            translator = Translator()
            result = translator.translate_file("messages.en.json", "fr")
            
            # Verify the translation
            assert result == expected_translation

    def test_translate_file_yaml(self, monkeypatch):
        """Test translate_file method with YAML file"""
        # Sample YAML content
        yaml_content = """
        welcome: Welcome to our application!
        login:
          title: Login
          submit: Sign In
        """
        
        # Parsed YAML content
        parsed_yaml = {
            "welcome": "Welcome to our application!",
            "login": {
                "title": "Login",
                "submit": "Sign In"
            }
        }
        
        # Expected translation
        expected_translation = {
            "welcome": "Bienvenue dans notre application!",
            "login": {
                "title": "Connexion",
                "submit": "Se connecter"
            }
        }

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_languages.return_value = ["en", "fr"]

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock open to return the YAML content
        m = mock_open(read_data=yaml_content)
        
        # Mock yaml.safe_load to return parsed content
        monkeypatch.setattr(yaml, "safe_load", lambda f: parsed_yaml)
        
        # Mock translate_text to return expected translations
        def mock_translate_text(text, source_lang, target_lang, ui_safe=False, glossary_id=None):
            if text == "Welcome to our application!":
                return "Bienvenue dans notre application!"
            elif text == "Login":
                return "Connexion"
            elif text == "Sign In":
                return "Se connecter"
            return text
        
        with patch("builtins.open", m), \
             patch.object(Translator, "translate_text", side_effect=mock_translate_text):
            
            translator = Translator()
            result = translator.translate_file("messages.en.yaml", "fr")
            
            # Verify the translation
            assert result == expected_translation

    def test_translate_file_unsupported_format(self, monkeypatch):
        """Test translate_file method with unsupported file format"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_languages.return_value = ["en", "fr"]

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()
        
        # Test translate_file with unsupported format
        with pytest.raises(ValueError, match="Unsupported file format"):
            translator.translate_file("messages.en.txt", "fr")

    def test_translate_nested_dict(self, monkeypatch):
        """Test _translate_nested_dict method"""
        # Sample nested dictionary
        nested_dict = {
            "welcome": "Welcome to our application!",
            "login": {
                "title": "Login",
                "submit": "Sign In"
            },
            "count": 5  # Non-string value should be preserved
        }
        
        # Expected translation
        expected_translation = {
            "welcome": "Bienvenue dans notre application!",
            "login": {
                "title": "Connexion",
                "submit": "Se connecter"
            },
            "count": 5
        }

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock translate_text to return expected translations
        def mock_translate_text(text, source_lang, target_lang, ui_safe=False, glossary_id=None):
            if text == "Welcome to our application!":
                return "Bienvenue dans notre application!"
            elif text == "Login":
                return "Connexion"
            elif text == "Sign In":
                return "Se connecter"
            return text
        
        translator = Translator()
        translator.translate_text = mock_translate_text
        
        # Test _translate_nested_dict
        result = translator._translate_nested_dict(nested_dict, "en", "fr")
        
        # Verify the translation
        assert result == expected_translation

    def test_translate_with_algebras_ai(self, monkeypatch):
        """Test translation with Algebras AI provider"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock requests.post
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "Hallo Welt"}
        
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr("algebras.services.translator.requests.post", mock_post)

        # Initialize Translator
        translator = Translator()
        # Clear cache to ensure we make a fresh API call
        translator.cache.clear()
        result = translator.translate_text("Hello world", "en", "de")

        # Verify the translation
        assert result == "Hallo Welt"
        
        # Verify the correct URL and headers were used
        expected_url = "https://platform.algebras.ai/api/v1/translation/translate"
        expected_headers = {
            "accept": "application/json",
            "X-Api-Key": "test-api-key"
        }
        
        # Check that requests.post was called with the correct arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == expected_url
        assert kwargs["headers"] == expected_headers
        
        # Check that files dict contains appropriate values
        assert "sourceLanguage" in kwargs["files"]
        assert "targetLanguage" in kwargs["files"]
        assert "textContent" in kwargs["files"]
        assert kwargs["files"]["sourceLanguage"][1] == "en"
        assert kwargs["files"]["targetLanguage"][1] == "de"
        assert kwargs["files"]["textContent"][1] == "Hello world"

    def test_normalize_translation_string(self, monkeypatch):
        """Test normalize_translation_string method"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_setting.return_value = True  # normalization enabled

        # Patch Config class
        monkeypatch.setattr("algebras.services.translator.Config", lambda: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Test 1: Normal case - should normalize escaped apostrophe
        source_text = "More"
        translated_text = "Ko\\'proq"
        result = translator.normalize_translation_string(source_text, translated_text)
        assert result == "Ko'proq"

        # Test 2: Source has escaped character - should NOT normalize
        source_text = "Say \\'hello\\'"
        translated_text = "Salom \\'aytish\\'"
        result = translator.normalize_translation_string(source_text, translated_text)
        assert result == "Salom \\'aytish\\'"  # Should remain escaped

        # Test 3: Multiple escaped characters
        source_text = "Hello world"
        translated_text = "Salom \\'dunyo\\' va \\\"odam\\\""
        result = translator.normalize_translation_string(source_text, translated_text)
        assert result == "Salom 'dunyo' va \"odam\""

        # Test 4: Mixed case - some should normalize, some shouldn't
        source_text = "Text with \\'existing\\' escapes"
        translated_text = "Matn \\'mavjud\\' va \\\"yangi\\\" qochishlar bilan"
        result = translator.normalize_translation_string(source_text, translated_text)
        # Should NOT normalize apostrophes (present in source) but SHOULD normalize quotes (not in source)
        assert result == "Matn \\'mavjud\\' va \"yangi\" qochishlar bilan"

        # Test 5: Test with normalization disabled
        mock_config.get_setting.return_value = False  # normalization disabled
        source_text = "More"
        translated_text = "Ko\\'proq"
        result = translator.normalize_translation_string(source_text, translated_text)
        assert result == "Ko\\'proq"  # Should remain unchanged

        # Test 6: Test newlines and tabs (should be preserved as actual characters)
        mock_config.get_setting.return_value = True  # normalization enabled
        source_text = "Line one"
        translated_text = "Birinchi qator\\nIkkinchi qator"
        result = translator.normalize_translation_string(source_text, translated_text)
        assert result == "Birinchi qator\nIkkinchi qator"

        # Test 7: Test backslash normalization
        source_text = "File path"
        translated_text = "Fayl yo\\\\li"
        result = translator.normalize_translation_string(source_text, translated_text)
        assert result == "Fayl yo\\li" 