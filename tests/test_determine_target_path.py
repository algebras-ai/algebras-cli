import unittest
from algebras.utils.path_utils import determine_target_path

def test_determine_target_path():
    """Test that target paths are correctly determined"""
    # Test case: source files in language-specific directories
    source_path = "public/locales/en/common.json"
    
    # For different target languages
    assert determine_target_path(source_path, "en", "fr") == "public/locales/fr/common.json"
    assert determine_target_path(source_path, "en", "es") == "public/locales/es/common.json"
    
    # Test with Windows-style paths
    win_source = "public\\locales\\en\\common.json"
    assert determine_target_path(win_source, "en", "fr") == "public\\locales\\fr\\common.json"
    
    # Test with no language marker in path
    generic_path = "locales/messages.json"
    assert determine_target_path(generic_path, "en", "fr") == "locales/messages.json" 