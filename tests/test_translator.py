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
            from algebras.services.batch_processor import BatchResult
            
            translator = Translator()
            # Mock the batch processor
            mock_batch_processor = MagicMock()
            mock_batch_processor.process.return_value = BatchResult(
                translations=["Bienvenue dans notre application!", "Connexion", "Se connecter"],
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )
            translator._batch_processor = mock_batch_processor
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
            from algebras.services.batch_processor import BatchResult
            
            translator = Translator()
            # Mock the batch processor
            mock_batch_processor = MagicMock()
            mock_batch_processor.process.return_value = BatchResult(
                translations=["Bienvenue dans notre application!", "Connexion", "Se connecter"],
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )
            translator._batch_processor = mock_batch_processor
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
        """Test nested dict translation using strategy"""
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

        from algebras.services.batch_processor import BatchResult
        
        # Mock batch processor result
        def mock_process(texts, source_lang, target_lang, ui_safe=False, glossary_id="", on_batch_complete=None, translate_text_func=None):
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
            return BatchResult(
                translations=translations,
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )
        
        translator = Translator()
        # Mock the batch processor
        mock_batch_processor = MagicMock()
        mock_batch_processor.process = mock_process
        translator._batch_processor = mock_batch_processor
        
        # Test using nested dict strategy
        from algebras.services.strategies.strategy_factory import TranslationStrategyFactory
        strategy = TranslationStrategyFactory.get_nested_dict_strategy(translator)
        result = strategy.translate(nested_dict, "en", "fr")
        
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
        result = translator.string_normalizer.normalize(source_text, translated_text)
        assert result == "Ko'proq"

        # Test 2: Source has escaped character - should NOT normalize
        source_text = "Say \\'hello\\'"
        translated_text = "Salom \\'aytish\\'"
        result = translator.string_normalizer.normalize(source_text, translated_text)
        assert result == "Salom \\'aytish\\'"  # Should remain escaped

        # Test 3: Multiple escaped characters
        source_text = "Hello world"
        translated_text = "Salom \\'dunyo\\' va \\\"odam\\\""
        result = translator.string_normalizer.normalize(source_text, translated_text)
        assert result == "Salom 'dunyo' va \"odam\""

        # Test 4: Mixed case - some should normalize, some shouldn't
        source_text = "Text with \\'existing\\' escapes"
        translated_text = "Matn \\'mavjud\\' va \\\"yangi\\\" qochishlar bilan"
        result = translator.string_normalizer.normalize(source_text, translated_text)
        # Should NOT normalize apostrophes (present in source) but SHOULD normalize quotes (not in source)
        assert result == "Matn \\'mavjud\\' va \"yangi\" qochishlar bilan"

        # Test 5: Test with normalization disabled
        mock_config.get_setting.return_value = False  # normalization disabled
        source_text = "More"
        translated_text = "Ko\\'proq"
        result = translator.string_normalizer.normalize(source_text, translated_text)
        assert result == "Ko\\'proq"  # Should remain unchanged

        # Test 6: Test newlines and tabs (should be preserved as actual characters)
        mock_config.get_setting.return_value = True  # normalization enabled
        source_text = "Line one"
        translated_text = "Birinchi qator\\nIkkinchi qator"
        result = translator.string_normalizer.normalize(source_text, translated_text)
        assert result == "Birinchi qator\nIkkinchi qator"

        # Test 7: Test backslash normalization
        source_text = "File path"
        translated_text = "Fayl yo\\\\li"
        result = translator.string_normalizer.normalize(source_text, translated_text)
        assert result == "Fayl yo\\li"

    def test_retry_with_exponential_backoff_success(self, monkeypatch):
        """Test retry helper with successful response"""
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Test retry helper with successful response
        def api_call():
            return mock_response

        result = retry_handler.execute_with_retry(api_call)
        assert result.status_code == 200

    def test_retry_with_exponential_backoff_429_retry_success(self, monkeypatch):
        """Test retry helper with 429 error that succeeds on retry"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=3, initial_wait=0.1)

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
            result = retry_handler.execute_with_retry(api_call)

        assert result.status_code == 200
        assert call_count[0] == 2  # Should have retried once

    def test_retry_with_exponential_backoff_429_exhausted(self, monkeypatch):
        """Test retry helper with 429 error that exhausts all retries"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=2, initial_wait=0.1)

        # Mock 429 response
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        def api_call():
            return mock_response_429

        # Mock time.sleep to avoid actual delays in tests
        with patch('time.sleep'):
            with pytest.raises(Exception, match="429 Too Many Requests"):
                retry_handler.execute_with_retry(api_call)

    def test_retry_with_exponential_backoff_non_429_error(self, monkeypatch):
        """Test retry helper with non-429 error (should not retry)"""
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Mock 500 error response
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_500.text = "Internal Server Error"

        call_count = [0]

        def api_call():
            call_count[0] += 1
            return mock_response_500

        # Should not retry on non-429 errors (5xx errors are immediately raised)
        with pytest.raises(Exception, match="Error from Algebras AI API"):
            retry_handler.execute_with_retry(api_call)
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
        monkeypatch.setattr("algebras.services.api_client.requests.post", mock_post)

        # Test with empty strings mixed in
        from algebras.services.api_client import AlgebrasAIClient
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler
        
        rate_limiter = RateLimiter()
        retry_handler = RetryHandler(rate_limiter=rate_limiter)
        api_client = AlgebrasAIClient(config=mock_config, retry_handler=retry_handler)
        
        texts = ["Hello", "", "World", ""]
        result = api_client.translate_batch(texts, "en", "fr")

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

        # Test with all empty strings
        from algebras.services.api_client import AlgebrasAIClient
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler
        
        rate_limiter = RateLimiter()
        retry_handler = RetryHandler(rate_limiter=rate_limiter)
        api_client = AlgebrasAIClient(config=mock_config, retry_handler=retry_handler)
        
        texts = ["", "", ""]
        result = api_client.translate_batch(texts, "en", "fr")

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

        from algebras.services.batch_processor import BatchResult
        
        # Mock batch processor result
        def mock_process(texts, source_lang, target_lang, ui_safe=False, glossary_id="", on_batch_complete=None, translate_text_func=None):
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
            return BatchResult(
                translations=translations,
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )

        # Mock the batch processor
        mock_batch_processor = MagicMock()
        mock_batch_processor.process = mock_process
        translator._batch_processor = mock_batch_processor

        # Test with empty strings using flat dict strategy
        from algebras.services.strategies.strategy_factory import TranslationStrategyFactory
        strategy = TranslationStrategyFactory.get_flat_dict_strategy(translator)
        
        data = {
            "greeting": "Hello",
            "empty1": "",
            "name": "World",
            "empty2": "",
            "empty3": "   "  # Whitespace only
        }

        result = strategy.translate(data, "en", "fr")

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

        from algebras.services.batch_processor import BatchResult
        
        # Mock batch processor result
        def mock_process(texts, source_lang, target_lang, ui_safe=False, glossary_id="", on_batch_complete=None, translate_text_func=None):
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
            return BatchResult(
                translations=translations,
                error_stats={"5xx": [], "429": [], "other": []},
                failed_batches=[],
                successful_batches=1,
                total_batches=1,
            )

        # Mock the batch processor
        mock_batch_processor = MagicMock()
        mock_batch_processor.process = mock_process
        translator._batch_processor = mock_batch_processor

        # Test with empty strings in nested structure using nested dict strategy
        from algebras.services.strategies.strategy_factory import TranslationStrategyFactory
        strategy = TranslationStrategyFactory.get_nested_dict_strategy(translator)
        
        data = {
            "greeting": "Hello",
            "empty": "",
            "nested": {
                "name": "World",
                "empty_nested": ""
            }
        }

        result = strategy.translate(data, "en", "fr")

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

        # Mock batch processor instead
        from algebras.services.batch_processor import BatchResult
        
        mock_batch_processor = MagicMock()
        mock_batch_processor.process.return_value = BatchResult(
            translations=["Bonjour", "Monde"],
            error_stats={"5xx": [], "429": [], "other": []},
            failed_batches=[],
            successful_batches=1,
            total_batches=1,
        )
        translator._batch_processor = mock_batch_processor

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

        # Mock batch processor instead
        from algebras.services.batch_processor import BatchResult
        
        mock_batch_processor = MagicMock()
        mock_batch_processor.process.return_value = BatchResult(
            translations=["Bonjour", "Monde"],
            error_stats={"5xx": [], "429": [], "other": []},
            failed_batches=[],
            successful_batches=1,
            total_batches=1,
        )
        translator._batch_processor = mock_batch_processor

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

        monkeypatch.setattr("algebras.services.api_client.requests.post", mock_post)

        # Mock time.sleep to avoid actual delays in tests
        from algebras.services.api_client import AlgebrasAIClient
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler
        
        rate_limiter = RateLimiter()
        retry_handler = RetryHandler(rate_limiter=rate_limiter)
        api_client = AlgebrasAIClient(config=mock_config, retry_handler=retry_handler)
        
        with patch('time.sleep'):
            result = api_client.translate("Hello", "en", "fr")

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

        monkeypatch.setattr("algebras.services.api_client.requests.post", mock_post)

        # Mock time.sleep to avoid actual delays in tests
        from algebras.services.api_client import AlgebrasAIClient
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler
        
        rate_limiter = RateLimiter()
        retry_handler = RetryHandler(rate_limiter=rate_limiter)
        api_client = AlgebrasAIClient(config=mock_config, retry_handler=retry_handler)
        
        with patch('time.sleep'):
            result = api_client.translate_batch(["Hello"], "en", "fr")

        assert result == ["Bonjour"]
        assert call_count[0] == 2  # Should have retried once

    def test_wait_for_rate_limit_below_limit(self, monkeypatch):
        """Test rate limiter when below the limit"""
        from algebras.services.rate_limiter import RateLimiter

        # Create RateLimiter directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)

        # Make a few requests (below limit)
        for i in range(5):
            rate_limiter.wait_if_needed()

        # Should have 5 timestamps
        assert len(rate_limiter._request_timestamps) == 5

    def test_wait_for_rate_limit_at_limit(self, monkeypatch):
        """Test rate limiter when at the limit - should wait"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter

        # Create RateLimiter directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)

        # Fill up the rate limit (30 requests)
        current_time = time.time()
        rate_limiter._request_timestamps = [current_time - i * 0.1 for i in range(30)]

        # Mock time.sleep to verify it's called
        with patch('time.sleep') as mock_sleep:
            rate_limiter.wait_if_needed()
            # Should have waited
            assert mock_sleep.called
            # Should have 31 timestamps now (30 old + 1 new)
            assert len(rate_limiter._request_timestamps) == 31

    def test_wait_for_rate_limit_old_timestamps_removed(self, monkeypatch):
        """Test that old timestamps (>60 seconds) are removed"""
        import time
        from algebras.services.rate_limiter import RateLimiter

        # Create RateLimiter directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)

        # Add old timestamps (>60 seconds old)
        current_time = time.time()
        rate_limiter._request_timestamps = [
            current_time - 70,  # 70 seconds ago
            current_time - 65,  # 65 seconds ago
            current_time - 5,   # 5 seconds ago
            current_time - 2,   # 2 seconds ago
        ]

        # Call rate limiter
        rate_limiter.wait_if_needed()

        # Should only have timestamps from last 60 seconds
        assert len(rate_limiter._request_timestamps) == 3  # 2 old + 1 new
        for ts in rate_limiter._request_timestamps:
            assert current_time - ts < 60.0

    def test_retry_with_rate_limit_enforcement(self, monkeypatch):
        """Test that rate limiter is called before API calls"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Track if rate limiter was called
        rate_limit_called = [False]
        original_wait_if_needed = rate_limiter.wait_if_needed

        def wait_if_needed():
            rate_limit_called[0] = True
            original_wait_if_needed()

        # Replace the method temporarily
        rate_limiter.wait_if_needed = wait_if_needed

        def api_call():
            return mock_response

        # Mock time.sleep to avoid actual delays
        with patch('time.sleep'):
            result = retry_handler.execute_with_retry(api_call)

        # Verify rate limiter was called
        assert rate_limit_called[0]
        assert result.status_code == 200

    def test_consecutive_429_tracking(self, monkeypatch):
        """Test that consecutive 429 errors are tracked and increase backoff"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Mock 429 responses
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200

        call_count = [0]
        consecutive_counts = []

        def api_call():
            call_count[0] += 1
            # Track consecutive count before each retry
            consecutive_counts.append(retry_handler._consecutive_429_count)
            if call_count[0] <= 3:
                return mock_response_429
            return mock_response_200

        # Mock time.sleep to track wait times
        wait_times = []

        def mock_sleep(duration):
            wait_times.append(duration)

        with patch('time.sleep', side_effect=mock_sleep):
            with patch('time.time', return_value=time.time()):
                result = retry_handler.execute_with_retry(api_call)

        # Should have succeeded after retries
        assert result.status_code == 200
        # Should have tracked consecutive 429s during retries (count increases)
        # Note: count is reset to 0 on success, so check during retries
        assert any(count > 0 for count in consecutive_counts), "Consecutive 429 count should have increased during retries"
        # Wait times should increase (with extra backoff for consecutive 429s)
        assert len(wait_times) >= 2

    def test_consecutive_429_reset_on_success(self, monkeypatch):
        """Test that consecutive 429 counter resets on successful request"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Set consecutive 429 count
        retry_handler._consecutive_429_count = 5

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        def api_call():
            return mock_response

        with patch('time.sleep'):
            result = retry_handler.execute_with_retry(api_call)

        # Consecutive 429 count should be reset
        assert retry_handler._consecutive_429_count == 0
        assert result.status_code == 200

    def test_consecutive_429_reset_after_60_seconds(self, monkeypatch):
        """Test that consecutive 429 counter resets after 60 seconds"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=1, initial_wait=0.1)

        # Set consecutive 429 count and last 429 time to 70 seconds ago
        retry_handler._consecutive_429_count = 5
        retry_handler._last_429_time = time.time() - 70

        # Mock 429 response
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.text = "Too Many Requests"

        def api_call():
            return mock_response_429

        # Mock time.time to return current time
        with patch('time.sleep'):
            with patch('time.time', return_value=time.time()):
                try:
                    retry_handler.execute_with_retry(api_call)
                except Exception:
                    pass  # Expected to fail after retries

        # Consecutive 429 count should be reset to 1 (not 6) because it was reset
        assert retry_handler._consecutive_429_count == 1

    def test_aggressive_backoff_with_multiple_429s(self, monkeypatch):
        """Test that backoff increases more aggressively with multiple consecutive 429s"""
        import time
        from unittest.mock import patch
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=3, initial_wait=1.0)

        # Set consecutive 429 count to simulate multiple batches hitting 429
        retry_handler._consecutive_429_count = 5
        retry_handler._last_429_time = time.time()

        # Mock 429 response
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

        wait_times = []

        def mock_sleep(duration):
            wait_times.append(duration)

        with patch('time.sleep', side_effect=mock_sleep):
            with patch('time.time', return_value=time.time()):
                result = retry_handler.execute_with_retry(api_call)

        # Should have succeeded
        assert result.status_code == 200
        # Should have waited with extra backoff (1.0 + 2.5 = 3.5s minimum for 5 consecutive 429s)
        assert len(wait_times) > 0
        # Wait time should include extra backoff for consecutive 429s
        assert wait_times[0] >= 3.5  # 1.0 base + 2.5 extra (5 * 0.5, capped at 5.0) + jitter

    def test_shared_rate_limit_coordination(self, monkeypatch):
        """Test that shared rate limit backoff coordinates across batches"""
        import time
        from unittest.mock import patch
        import threading
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Set shared backoff to 5 seconds in the future
        retry_handler._backoff_until = time.time() + 5.0

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        wait_times = []

        def mock_sleep(duration):
            wait_times.append(duration)

        def api_call():
            return mock_response

        with patch('time.sleep', side_effect=mock_sleep):
            with patch('time.time', return_value=time.time()):
                result = retry_handler.execute_with_retry(api_call)

        # Should have waited for shared backoff
        assert len(wait_times) > 0
        # Should have waited approximately 5 seconds
        assert 4.9 <= wait_times[0] <= 5.1
        assert result.status_code == 200

    def test_rate_limit_with_parallel_batches(self, monkeypatch):
        """Test rate limiting works correctly with parallel batches"""
        import time
        from unittest.mock import patch
        import concurrent.futures
        from algebras.services.rate_limiter import RateLimiter
        from algebras.services.retry_handler import RetryHandler

        # Create RateLimiter and RetryHandler directly
        rate_limiter = RateLimiter(max_requests_per_minute=30)
        retry_handler = RetryHandler(rate_limiter=rate_limiter, max_retries=5, initial_wait=1.0)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200

        def api_call():
            return mock_response

        request_count = [0]
        original_wait_if_needed = rate_limiter.wait_if_needed

        def wait_if_needed():
            original_wait_if_needed()
            request_count[0] += 1

        # Replace method to track calls
        rate_limiter.wait_if_needed = wait_if_needed

        # Simulate multiple parallel batches making requests
        with patch('time.sleep'):
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(retry_handler.execute_with_retry, api_call) for _ in range(10)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # All requests should have succeeded
        assert all(r.status_code == 200 for r in results)
        # Rate limiter should have been called for each request
        assert request_count[0] == 10 