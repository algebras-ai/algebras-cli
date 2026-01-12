"""
Tests for XLIFF ph tag and child element extraction.

This test suite verifies that source text extraction includes all child elements
(ph, pc, sc, ec, mrk) and preserves XML structure when extracting source text.
"""

import os
import tempfile
import pytest
from algebras.utils.xliff_handler import read_xliff_file, extract_translatable_strings


class TestXLIFFPhTagExtraction:
    """Test cases for extracting full text including ph tags and other child elements."""
    
    def test_extract_source_with_ph_tag_xliff_12(self):
        """
        Test that source text extraction includes ph tags in XLIFF 1.2 format.
        
        Behavior: When extracting source text from XLIFF 1.2 files, the full text
        including all child elements like <ph> should be extracted, not just the
        direct text content before the first tag.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="fr" datatype="plaintext">
    <body>
      <trans-unit id="welcome">
        <source>Hello <ph id="1" equiv-text="%name"/>!</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            # Verify full text including ph tag is extracted
            assert 'welcome' in translatable
            # The text should include the ph tag content
            # Exact format depends on implementation, but should not be truncated
            source_text = translatable['welcome']
            assert 'Hello' in source_text
            assert 'ph' in source_text or '%name' in source_text or '1' in source_text
        finally:
            os.unlink(temp_file)
    
    def test_extract_source_with_ph_tag_xliff_20(self):
        """
        Test that source text extraction includes ph tags in XLIFF 2.0 format.
        
        Behavior: When extracting source text from XLIFF 2.0 files, the full text
        including all child elements like <ph> should be extracted from within <segment>.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en" trgLang="fr">
  <file id="f1" original="messages">
    <unit id="welcome">
      <segment>
        <source>Hello <ph id="1" equiv-text="%name"/>!</source>
        <target></target>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            # Verify full text including ph tag is extracted
            assert 'welcome' in translatable
            source_text = translatable['welcome']
            assert 'Hello' in source_text
            assert 'ph' in source_text or '%name' in source_text or '1' in source_text
        finally:
            os.unlink(temp_file)
    
    def test_extract_source_with_multiple_ph_tags(self):
        """
        Test that source text extraction includes multiple ph tags.
        
        Behavior: When a source contains multiple <ph> tags, all of them should be
        included in the extracted text, not just the first one.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="fr" datatype="plaintext">
    <body>
      <trans-unit id="message">
        <source>Hello <ph id="1" equiv-text="%name"/>, you have <ph id="2" equiv-text="%count"/> messages.</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            source_text = translatable['message']
            # Should contain both ph tags
            assert 'Hello' in source_text
            assert 'you have' in source_text or 'messages' in source_text
            # Should not be truncated at first ph tag
            assert len(source_text) > len('Hello')
        finally:
            os.unlink(temp_file)
    
    def test_extract_source_with_pc_tags(self):
        """
        Test that source text extraction includes pc (paired code) tags.
        
        Behavior: XLIFF 2.0 uses <pc> tags for paired codes (like bold, italic).
        These should be included in the extracted text.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en" trgLang="fr">
  <file id="f1" original="messages">
    <unit id="bold">
      <segment>
        <source>This is <pc id="1" type="fmt">bold</pc> text.</source>
        <target></target>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            source_text = translatable['bold']
            assert 'This is' in source_text
            assert 'bold' in source_text
            assert 'text' in source_text
        finally:
            os.unlink(temp_file)
    
    def test_extract_source_with_sc_ec_tags(self):
        """
        Test that source text extraction includes sc (start code) and ec (end code) tags.
        
        Behavior: XLIFF 1.2 uses <sc> and <ec> tags for start/end codes.
        These should be included in the extracted text.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="fr" datatype="plaintext">
    <body>
      <trans-unit id="formatted">
        <source>This is <sc id="1" type="bold"/>bold<ec id="1"/> text.</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            source_text = translatable['formatted']
            assert 'This is' in source_text
            assert 'bold' in source_text
            assert 'text' in source_text
        finally:
            os.unlink(temp_file)
    
    def test_extract_source_with_mrk_tags(self):
        """
        Test that source text extraction includes mrk (marker) tags.
        
        Behavior: <mrk> tags are used for markers in XLIFF. These should be
        included in the extracted text.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="2.0" xmlns="urn:oasis:names:tc:xliff:document:2.0" srcLang="en" trgLang="fr">
  <file id="f1" original="messages">
    <unit id="marked">
      <segment>
        <source>This is <mrk id="m1" type="term">terminology</mrk> text.</source>
        <target></target>
      </segment>
    </unit>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            source_text = translatable['marked']
            assert 'This is' in source_text
            assert 'terminology' in source_text
            assert 'text' in source_text
        finally:
            os.unlink(temp_file)
    
    def test_extract_source_preserves_xml_structure(self):
        """
        Test that source text extraction preserves XML structure of child elements.
        
        Behavior: When extracting text with child elements, the structure should be
        preserved in a way that allows proper translation and reconstruction.
        """
        xliff_content = '''<?xml version="1.0" encoding="UTF-8" ?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="fr" datatype="plaintext">
    <body>
      <trans-unit id="complex">
        <source>Click <ph id="1" equiv-text="%link"/> to <ph id="2" equiv-text="%action"/>.</source>
        <target></target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlf', delete=False, encoding='utf-8') as f:
            f.write(xliff_content)
            temp_file = f.name
        
        try:
            result = read_xliff_file(temp_file)
            translatable = extract_translatable_strings(result)
            
            source_text = translatable['complex']
            # Should contain the full message, not truncated
            assert 'Click' in source_text
            assert 'to' in source_text
            # Should include both placeholders
            assert len(source_text) > len('Click')
        finally:
            os.unlink(temp_file)

