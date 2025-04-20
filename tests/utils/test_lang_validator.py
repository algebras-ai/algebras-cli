import os
import json
import pytest
import tempfile
from algebras.utils.lang_validator import extract_all_keys, validate_language_files


def test_extract_all_keys():
    """Test that all keys are correctly extracted from a nested dictionary"""
    # Test data
    data = {
        "Index": {
            "meta_title": "Title",
            "meta_description": "Description"
        },
        "Navbar": {
            "sign_in": "Sign in",
            "sign_up": "Sign up",
            "product": "Product"
        }
    }
    
    # Extract keys
    keys = extract_all_keys(data)
    
    # Expected keys
    expected_keys = {
        "Index", "Index.meta_title", "Index.meta_description",
        "Navbar", "Navbar.sign_in", "Navbar.sign_up", "Navbar.product"
    }
    
    assert keys == expected_keys


def test_validate_language_files():
    """Test validation of language files"""
    # Create temporary source file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as source_file:
        source_data = {
            "Index": {
                "meta_title": "Title",
                "meta_description": "Description"
            },
            "Navbar": {
                "sign_in": "Sign in",
                "sign_up": "Sign up",
                "product": "Product"
            }
        }
        source_file.write(json.dumps(source_data).encode('utf-8'))
        source_path = source_file.name
    
    # Create temporary target file with all keys (valid)
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as target_valid_file:
        target_valid_data = {
            "Index": {
                "meta_title": "Заголовок",
                "meta_description": "Описание"
            },
            "Navbar": {
                "sign_in": "Войти",
                "sign_up": "Зарегистрироваться",
                "product": "Продукт"
            }
        }
        target_valid_file.write(json.dumps(target_valid_data).encode('utf-8'))
        target_valid_path = target_valid_file.name
    
    # Create temporary target file with missing keys (invalid)
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as target_invalid_file:
        target_invalid_data = {
            "Index": {
                "meta_title": "Заголовок"
                # meta_description is missing
            },
            "Navbar": {
                "sign_in": "Войти",
                "sign_up": "Зарегистрироваться"
                # product is missing
            }
        }
        target_invalid_file.write(json.dumps(target_invalid_data).encode('utf-8'))
        target_invalid_path = target_invalid_file.name
    
    try:
        # Test valid file
        is_valid, missing_keys = validate_language_files(source_path, target_valid_path)
        assert is_valid is True
        assert len(missing_keys) == 0
        
        # Test invalid file
        is_valid, missing_keys = validate_language_files(source_path, target_invalid_path)
        assert is_valid is False
        assert len(missing_keys) == 2
        assert "Index.meta_description" in missing_keys
        assert "Navbar.product" in missing_keys
    
    finally:
        # Clean up temporary files
        os.unlink(source_path)
        os.unlink(target_valid_path)
        os.unlink(target_invalid_path) 