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

        # Patch Config class - patch algebras.config.Config since that's what gets imported inside __init__
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

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
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

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
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache to return None (cache miss)
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Mock Algebras AI API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "Bonjour le monde"}
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
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

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
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

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
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        
        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock open to return the JSON content
        m = mock_open(read_data=json.dumps(json_content))
        
        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            translations = []
            for text in texts:
                if text == "Welcome to our application!":
                    translations.append("Bienvenue dans notre application!")
                elif text == "Login":
                    translations.append("Connexion")
                elif text == "Sign In":
                    translations.append("Se connecter")
                else:
                    translations.append(text)
            return translations
        
        with patch("builtins.open", m):
            translator = Translator()
            # Mock the batch translation method
            translator._translate_with_algebras_ai_batch = mock_translate_batch
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
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        
        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock open to return the YAML content
        m = mock_open(read_data=yaml_content)
        
        # Mock yaml.safe_load to return parsed content
        monkeypatch.setattr(yaml, "safe_load", lambda f: parsed_yaml)
        
        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            translations = []
            for text in texts:
                if text == "Welcome to our application!":
                    translations.append("Bienvenue dans notre application!")
                elif text == "Login":
                    translations.append("Connexion")
                elif text == "Sign In":
                    translations.append("Se connecter")
                else:
                    translations.append(text)
            return translations
        
        with patch("builtins.open", m):
            translator = Translator()
            # Mock the batch translation method
            translator._translate_with_algebras_ai_batch = mock_translate_batch
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
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        
        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)
        
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
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)
        
        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)
        
        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            translations = []
            for text in texts:
                if text == "Welcome to our application!":
                    translations.append("Bienvenue dans notre application!")
                elif text == "Login":
                    translations.append("Connexion")
                elif text == "Sign In":
                    translations.append("Se connecter")
                else:
                    translations.append(text)
            return translations
        
        translator = Translator()
        # Mock the batch translation method
        translator._translate_with_algebras_ai_batch = mock_translate_batch
        
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
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

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
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

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

    def test_retry_with_exponential_backoff_success(self, monkeypatch):
        """Test retry helper with successful response"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Test retry helper with successful response
        def api_call():
            return mock_response

        result = translator._retry_with_exponential_backoff(api_call)
        assert result.status_code == 200

    def test_retry_with_exponential_backoff_429_retry_success(self, monkeypatch):
        """Test retry helper with 429 error that succeeds on retry"""
        import time
        from unittest.mock import patch

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Mock responses: first 429, then success
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200

        call_count = [0]

        def api_call():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_response_429
            return mock_response_200

        # Mock time.sleep to avoid actual delays in tests
        with patch('time.sleep'):
            result = translator._retry_with_exponential_backoff(api_call, max_retries=3, initial_wait=0.1)

        assert result.status_code == 200
        assert call_count[0] == 2  # Should have retried once

    def test_retry_with_exponential_backoff_429_exhausted(self, monkeypatch):
        """Test retry helper with 429 error that exhausts all retries"""
        import time
        from unittest.mock import patch

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Mock 429 response
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        def api_call():
            return mock_response_429

        # Mock time.sleep to avoid actual delays in tests
        with patch('time.sleep'):
            with pytest.raises(Exception, match="429 Too Many Requests"):
                translator._retry_with_exponential_backoff(api_call, max_retries=2, initial_wait=0.1)

    def test_retry_with_exponential_backoff_non_429_error(self, monkeypatch):
        """Test retry helper with non-429 error (should not retry)"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Mock 500 error response
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_500.text = "Internal Server Error"

        call_count = [0]

        def api_call():
            call_count[0] += 1
            return mock_response_500

        # Should not retry on non-429 errors
        result = translator._retry_with_exponential_backoff(api_call)
        assert result.status_code == 500
        assert call_count[0] == 1  # Should not have retried

    def test_translate_with_algebras_ai_batch_empty_strings(self, monkeypatch):
        """Test batch translation with empty strings - should filter them out"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = True

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "translations": [
                    {"index": 0, "content": "Bonjour"},
                    {"index": 1, "content": "Monde"}
                ]
            }
        }

        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr("algebras.services.translator.requests.post", mock_post)

        # Test with empty strings mixed in
        texts = ["Hello", "", "World", ""]
        result = translator._translate_with_algebras_ai_batch(texts, "en", "fr")

        # Verify empty strings are preserved in result
        assert len(result) == 4
        assert result[0] == "Bonjour"
        assert result[1] == ""  # Empty string preserved
        assert result[2] == "Monde"
        assert result[3] == ""  # Empty string preserved

        # Verify API was called with only non-empty strings
        call_args = mock_post.call_args
        request_data = call_args[1]["json"]
        assert len(request_data["texts"]) == 2  # Only non-empty strings
        assert request_data["texts"] == ["Hello", "World"]

    def test_translate_with_algebras_ai_batch_all_empty_strings(self, monkeypatch):
        """Test batch translation with all empty strings"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = True

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Test with all empty strings
        texts = ["", "", ""]
        result = translator._translate_with_algebras_ai_batch(texts, "en", "fr")

        # Verify all empty strings are preserved
        assert len(result) == 3
        assert result == ["", "", ""]

    def test_translate_flat_dict_empty_strings(self, monkeypatch):
        """Test flat dict translation with empty strings"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            # Should only receive non-empty strings
            assert "" not in texts
            translations = []
            for text in texts:
                if text == "Hello":
                    translations.append("Bonjour")
                elif text == "World":
                    translations.append("Monde")
                else:
                    translations.append(text)
            return translations

        translator._translate_with_algebras_ai_batch = mock_translate_batch

        # Test with empty strings
        data = {
            "greeting": "Hello",
            "empty1": "",
            "name": "World",
            "empty2": "",
            "empty3": "   "  # Whitespace only
        }

        result = translator._translate_flat_dict(data, "en", "fr")

        # Verify empty strings are preserved
        assert result["greeting"] == "Bonjour"
        assert result["empty1"] == ""
        assert result["name"] == "Monde"
        assert result["empty2"] == ""
        assert result["empty3"] == ""  # Whitespace-only treated as empty

    def test_translate_nested_dict_empty_strings(self, monkeypatch):
        """Test nested dict translation with empty strings"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            # Should only receive non-empty strings
            assert "" not in texts
            translations = []
            for text in texts:
                if text == "Hello":
                    translations.append("Bonjour")
                elif text == "World":
                    translations.append("Monde")
                else:
                    translations.append(text)
            return translations

        translator._translate_with_algebras_ai_batch = mock_translate_batch

        # Test with empty strings in nested structure
        data = {
            "greeting": "Hello",
            "empty": "",
            "nested": {
                "name": "World",
                "empty_nested": ""
            }
        }

        result = translator._translate_nested_dict(data, "en", "fr")

        # Verify empty strings are preserved
        assert result["greeting"] == "Bonjour"
        assert result["empty"] == ""
        assert result["nested"]["name"] == "Monde"
        assert result["nested"]["empty_nested"] == ""

    def test_translate_missing_keys_batch_empty_strings(self, monkeypatch):
        """Test missing keys batch translation with empty strings"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            # Should only receive non-empty strings
            assert "" not in texts
            translations = []
            for text in texts:
                if text == "Hello":
                    translations.append("Bonjour")
                elif text == "World":
                    translations.append("Monde")
                else:
                    translations.append(text)
            return translations

        translator._translate_with_algebras_ai_batch = mock_translate_batch

        # Test with empty strings
        source_content = {
            "greeting": "Hello",
            "empty1": "",
            "name": "World",
            "empty2": ""
        }
        target_content = {}
        missing_keys = ["greeting", "empty1", "name", "empty2"]

        result = translator.translate_missing_keys_batch(
            source_content, target_content, missing_keys, "fr"
        )

        # Verify empty strings are preserved
        assert result["greeting"] == "Bonjour"
        assert result["empty1"] == ""
        assert result["name"] == "Monde"
        assert result["empty2"] == ""

    def test_translate_outdated_keys_batch_empty_strings(self, monkeypatch):
        """Test outdated keys batch translation with empty strings"""
        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_source_language.return_value = "en"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Mock batch translation method
        def mock_translate_batch(texts, source_lang, target_lang, ui_safe=False, glossary_id=""):
            # Should only receive non-empty strings
            assert "" not in texts
            translations = []
            for text in texts:
                if text == "Hello":
                    translations.append("Bonjour")
                elif text == "World":
                    translations.append("Monde")
                else:
                    translations.append(text)
            return translations

        translator._translate_with_algebras_ai_batch = mock_translate_batch

        # Test with empty strings
        source_content = {
            "greeting": "Hello",
            "empty1": "",
            "name": "World",
            "empty2": ""
        }
        target_content = {
            "greeting": "Old greeting",
            "empty1": "Old empty",
            "name": "Old name",
            "empty2": "Old empty2"
        }
        outdated_keys = ["greeting", "empty1", "name", "empty2"]

        result = translator.translate_outdated_keys_batch(
            source_content, target_content, outdated_keys, "fr"
        )

        # Verify empty strings are preserved
        assert result["greeting"] == "Bonjour"
        assert result["empty1"] == ""
        assert result["name"] == "Monde"
        assert result["empty2"] == ""

    def test_translate_with_algebras_ai_uses_retry_helper(self, monkeypatch):
        """Test that _translate_with_algebras_ai uses retry helper for 429 errors"""
        import time
        from unittest.mock import patch

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = ""
        mock_config.has_setting.return_value = False

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Mock the cache
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_cache_key.return_value = "test-cache-key"
        monkeypatch.setattr("algebras.services.translator.TranslationCache", lambda: mock_cache)

        # Initialize Translator
        translator = Translator()

        # Mock responses: first 429, then success
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"data": "Bonjour"}

        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_response_429
            return mock_response_200

        monkeypatch.setattr("algebras.services.translator.requests.post", mock_post)

        # Mock time.sleep to avoid actual delays in tests
        with patch('time.sleep'):
            result = translator._translate_with_algebras_ai("Hello", "en", "fr")

        assert result == "Bonjour"
        assert call_count[0] == 2  # Should have retried once

    def test_translate_with_algebras_ai_batch_uses_retry_helper(self, monkeypatch):
        """Test that _translate_with_algebras_ai_batch uses retry helper for 429 errors"""
        import time
        from unittest.mock import patch

        # Mock Config
        mock_config = MagicMock(spec=Config)
        mock_config.exists.return_value = True
        mock_config.load.return_value = {}
        mock_config.get_api_config.return_value = {"provider": "algebras-ai"}
        mock_config.get_base_url.return_value = "https://platform.algebras.ai"
        mock_config.get_setting.return_value = True

        # Patch Config class
        monkeypatch.setattr("algebras.config.Config", lambda *args, **kwargs: mock_config)

        # Mock environment variable
        monkeypatch.setenv("ALGEBRAS_API_KEY", "test-api-key")

        # Initialize Translator
        translator = Translator()

        # Mock responses: first 429, then success
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "data": {
                "translations": [
                    {"index": 0, "content": "Bonjour"}
                ]
            }
        }

        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_response_429
            return mock_response_200

        monkeypatch.setattr("algebras.services.translator.requests.post", mock_post)

        # Mock time.sleep to avoid actual delays in tests
        with patch('time.sleep'):
            result = translator._translate_with_algebras_ai_batch(["Hello"], "en", "fr")

        assert result == ["Bonjour"]
        assert call_count[0] == 2  # Should have retried once 