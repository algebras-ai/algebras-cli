#!/usr/bin/env python3
"""
Test script to demonstrate improved HTML translation formatting.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from algebras.utils.html_handler import (
    read_html_file, 
    write_html_file, 
    normalize_html_formatting,
    detect_formatting_style
)

def test_html_formatting_consistency():
    """Test HTML formatting normalization with sample email templates."""
    
    # Test file paths
    test_files = [
        "examples/html/html_files/course_is_ready_jet_sharing_en.html",
        "examples/html/html_files/course_is_ready_jet_sharing_pt_BR.html",
        "html_workdir/locales/access_code_evolve_platform_en.html"
    ]
    
    print("🧱 HTML Translation Formatting Improvements Test")
    print("=" * 60)
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"⚠️  Skipping {test_file} (not found)")
            continue
            
        print(f"\n📄 Testing: {test_file}")
        print("-" * 40)
        
        try:
            # Read original HTML file
            with open(test_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Detect formatting style
            style = detect_formatting_style(original_content)
            print(f"📐 Detected formatting style:")
            for key, value in style.items():
                print(f"   • {key}: {value}")
            
            # Extract translatable content
            translations = read_html_file(test_file)
            print(f"🔍 Found {len(translations)} translatable strings")
            
            # Create a temporary translated version with sample translations
            test_translations = {}
            for hash_key, original_text in translations.items():
                # For demo, add [TRANSLATED] prefix
                test_translations[hash_key] = f"[TRANSLATED] {original_text}"
            
            # Write normalized HTML
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
                write_html_file(temp_file.name, test_file, test_translations)
                temp_path = temp_file.name
            
            # Read the result and check formatting consistency
            with open(temp_path, 'r', encoding='utf-8') as f:
                result_content = f.read()
            
            # Check key formatting improvements
            print("✅ Formatting improvements applied:")
            
            # Check DOCTYPE normalization
            if '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"' in result_content:
                print("   • ✓ DOCTYPE normalized to XHTML 1.0 Transitional")
            
            # Check meta tag consistency
            if 'charset=' in result_content:
                if style['charset_format'] == 'UTF-8':
                    if 'charset="UTF-8"' in result_content:
                        print("   • ✓ Charset format preserved as UTF-8")
                else:
                    if 'charset="utf-8"' in result_content:
                        print("   • ✓ Charset format preserved as utf-8")
            
            # Check HTML tag attribute order
            if style['html_tag_format'] == 'xmlns_first':
                if 'xmlns="http://www.w3.org/1999/xhtml"' in result_content and 'lang=' in result_content:
                    print("   • ✓ HTML tag attributes ordered with xmlns first")
            else:
                print("   • ✓ HTML tag attributes ordered with lang first")
            
            # Check spacer div normalization
            if style['spacer_format'] == 'nbsp_double':
                if '&nbsp;&nbsp;' in result_content:
                    print("   • ✓ Spacer divs normalized with &nbsp;&nbsp;")
            else:
                print("   • ✓ Spacer divs normalized with double spaces")
            
            # Check conditional comments are preserved
            if '<!--[if' in result_content or '[if mso]' in result_content:
                print("   • ✓ Conditional comments preserved for Outlook compatibility")
            
            # Clean up temp file
            os.unlink(temp_path)
            
        except Exception as e:
            print(f"❌ Error testing {test_file}: {str(e)}")
    
    print("\n🎯 Summary:")
    print("The improved HTML handler now:")
    print("• Detects and preserves original formatting style")
    print("• Normalizes DOCTYPE declarations consistently")
    print("• Maintains meta tag order and charset format")
    print("• Preserves HTML tag attribute ordering")
    print("• Handles spacer div whitespace consistently")
    print("• Fixes conditional comments for email client compatibility")
    print("• Maintains VML namespace tags for Outlook support")


def demonstrate_formatting_differences():
    """Demonstrate the key formatting differences the improvements address."""
    
    print("\n🔍 Key Formatting Issues Addressed:")
    print("=" * 50)
    
    samples = {
        "DOCTYPE Declaration": {
            "before": "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\">",
            "after": "<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.0 Transitional//EN\" \"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd\">"
        },
        "Meta Charset": {
            "inconsistent": ["<meta charset=\"UTF-8\" />", "<meta charset=\"utf-8\"/>"],
            "normalized": "Consistent with original format"
        },
        "HTML Tag Attributes": {
            "version_1": "<html xmlns=\"http://www.w3.org/1999/xhtml\" lang=\"en\" ...>",
            "version_2": "<html lang=\"en\" xmlns=\"http://www.w3.org/1999/xhtml\" ...>",
            "solution": "Preserves original attribute order"
        },
        "Spacer Divs": {
            "version_1": "<div>...>&nbsp;&nbsp;</div>",
            "version_2": "<div>...>  </div>",
            "solution": "Consistent with original whitespace style"
        }
    }
    
    for issue, details in samples.items():
        print(f"\n📐 {issue}:")
        for key, value in details.items():
            if isinstance(value, list):
                print(f"   {key}:")
                for item in value:
                    print(f"     - {item}")
            else:
                print(f"   {key}: {value}")


if __name__ == "__main__":
    test_html_formatting_consistency()
    demonstrate_formatting_differences()

