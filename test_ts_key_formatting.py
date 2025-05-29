#!/usr/bin/env python3

"""
Test script to verify TypeScript key formatting works correctly
"""

import sys
import os

# Add the algebras directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'algebras'))

from utils.ts_handler import _python_dict_to_ts_object, _format_ts_key

def test_key_formatting():
    """Test the _format_ts_key function"""
    test_cases = [
        ("hello", "hello"),  # Simple key - no quotes needed
        ("en-US", '"en-US"'),  # Hyphen - needs quotes
        ("zh-CN", '"zh-CN"'),  # Hyphen - needs quotes  
        ("user_name", "user_name"),  # Underscore - no quotes needed
        ("userName", "userName"),  # Camel case - no quotes needed
        ("123key", '"123key"'),  # Starts with number - needs quotes
        ("key with spaces", '"key with spaces"'),  # Spaces - needs quotes
        ("key.with.dots", '"key.with.dots"'),  # Dots - needs quotes
        ("key@symbol", '"key@symbol"'),  # Special symbols - needs quotes
        ("$validKey", "$validKey"),  # Starts with $ - valid identifier
        ("_validKey", "_validKey"),  # Starts with _ - valid identifier
    ]
    
    print("Testing key formatting:")
    all_passed = True
    
    for input_key, expected in test_cases:
        result = _format_ts_key(input_key)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{input_key}' -> {result} (expected: {expected})")
        if result != expected:
            all_passed = False
    
    return all_passed

def test_object_conversion():
    """Test the full object conversion"""
    test_object = {
        "hello": "world",
        "en-US": "Hello",
        "zh-CN": "你好", 
        "user_name": "John",
        "nested": {
            "en-GB": "Hello there",
            "simple": "value"
        }
    }
    
    print("\nTesting object conversion:")
    result = _python_dict_to_ts_object(test_object, indent=0)
    print(result)
    
    # Check that the output contains quoted keys for special characters
    expected_patterns = [
        '"en-US": "Hello"',
        '"zh-CN": "你好"',
        '"en-GB": "Hello there"',
        'hello: "world"',  # Should not be quoted
        'user_name: "John"',  # Should not be quoted
        'simple: "value"'  # Should not be quoted
    ]
    
    all_found = True
    for pattern in expected_patterns:
        if pattern in result:
            print(f"  ✓ Found expected pattern: {pattern}")
        else:
            print(f"  ✗ Missing expected pattern: {pattern}")
            all_found = False
    
    return all_found

if __name__ == "__main__":
    print("Testing TypeScript key formatting fixes...")
    
    key_test_passed = test_key_formatting()
    object_test_passed = test_object_conversion()
    
    if key_test_passed and object_test_passed:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1) 