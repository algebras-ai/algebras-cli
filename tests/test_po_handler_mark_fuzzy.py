"""
Unit tests for PO handler mark_fuzzy functionality
"""

import unittest
import tempfile
import os
from algebras.utils.po_handler import (
    read_po_file, 
    write_po_file, 
    _parse_po_content,
    _add_fuzzy_comment_if_needed
)


class TestPOHandlerMarkFuzzy(unittest.TestCase):
    """Test cases for PO handler mark_fuzzy functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_content_simple = '''msgid "Hello"
msgstr "Hola"

msgid "World"
msgstr "Mundo"
'''

        self.test_content_with_comments = '''#. Key: Test_Key1
msgid "Hello"
msgstr "Hola"

#. Key: Test_Key2
msgid "World"
msgstr "Mundo"
'''

    def test_write_po_file_with_mark_fuzzy_new_file(self):
        """Test writing a new PO file with mark_fuzzy=True adds fuzzy comments"""
        content = {
            'Hello': 'Hola',
            'World': 'Mundo'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write with mark_fuzzy=True
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have fuzzy comments for both entries
            self.assertIn('#, fuzzy', written_content)
            # Count fuzzy comments - should be 2 (one per entry)
            fuzzy_count = written_content.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 2)
            
            # Verify structure: fuzzy comment should be before msgid
            lines = written_content.split('\n')
            fuzzy_indices = [i for i, line in enumerate(lines) if line.strip() == '#, fuzzy']
            msgid_indices = [i for i, line in enumerate(lines) if line.strip().startswith('msgid "') and line.strip() != 'msgid ""']
            
            # Each fuzzy should be before its corresponding msgid
            self.assertEqual(len(fuzzy_indices), 2)
            self.assertEqual(len(msgid_indices), 2)
            self.assertLess(fuzzy_indices[0], msgid_indices[0])
            self.assertLess(fuzzy_indices[1], msgid_indices[1])
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_without_mark_fuzzy_new_file(self):
        """Test writing a new PO file with mark_fuzzy=False does not add fuzzy comments"""
        content = {
            'Hello': 'Hola',
            'World': 'Mundo'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write with mark_fuzzy=False (default)
            write_po_file(temp_file, content, mark_fuzzy=False)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should NOT have fuzzy comments
            self.assertNotIn('#, fuzzy', written_content)
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_with_mark_fuzzy_existing_file(self):
        """Test updating an existing PO file with mark_fuzzy=True adds fuzzy comments only for changed translations"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(self.test_content_simple)
            temp_file = f.name
        
        try:
            # Update with new translations and mark_fuzzy=True
            # Original: Hello -> Hola, World -> Mundo
            # New: Hello -> Bonjour (changed), World -> Monde (changed)
            content = {
                'Hello': 'Bonjour',  # Changed from Hola
                'World': 'Monde'      # Changed from Mundo
            }
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have fuzzy comments for both entries (both changed)
            self.assertIn('#, fuzzy', written_content)
            fuzzy_count = written_content.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 2)
            
            # Verify translations were updated
            self.assertIn('msgstr "Bonjour"', written_content)
            self.assertIn('msgstr "Monde"', written_content)
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_with_mark_fuzzy_unchanged_translations(self):
        """Test that unchanged translations don't get fuzzy comments"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(self.test_content_simple)
            temp_file = f.name
        
        try:
            # Update with same translations (unchanged) and mark_fuzzy=True
            content = {
                'Hello': 'Hola',  # Unchanged
                'World': 'Mundo'  # Unchanged
            }
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should NOT have fuzzy comments since translations didn't change
            self.assertNotIn('#, fuzzy', written_content)
            
            # Verify translations are still there
            self.assertIn('msgstr "Hola"', written_content)
            self.assertIn('msgstr "Mundo"', written_content)
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_with_mark_fuzzy_partial_changes(self):
        """Test that only changed translations get fuzzy comments"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(self.test_content_simple)
            temp_file = f.name
        
        try:
            # Update with one changed and one unchanged translation
            content = {
                'Hello': 'Bonjour',  # Changed
                'World': 'Mundo'      # Unchanged
            }
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have fuzzy comment only for the changed translation
            self.assertIn('#, fuzzy', written_content)
            fuzzy_count = written_content.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 1)  # Only for 'Hello'
            
            # Verify translations
            self.assertIn('msgstr "Bonjour"', written_content)
            self.assertIn('msgstr "Mundo"', written_content)
            
            # Verify fuzzy is only before the changed entry
            lines = written_content.split('\n')
            hello_has_fuzzy = False
            world_has_fuzzy = False
            for i, line in enumerate(lines):
                if 'msgid "Hello"' in line:
                    # Check if fuzzy is before this msgid
                    for j in range(max(0, i-3), i):
                        if lines[j].strip() == '#, fuzzy':
                            hello_has_fuzzy = True
                            break
                elif 'msgid "World"' in line:
                    # Check if fuzzy is before this msgid
                    for j in range(max(0, i-3), i):
                        if lines[j].strip() == '#, fuzzy':
                            world_has_fuzzy = True
                            break
            
            self.assertTrue(hello_has_fuzzy, "Hello should have fuzzy comment")
            self.assertFalse(world_has_fuzzy, "World should NOT have fuzzy comment")
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_with_mark_fuzzy_preserves_existing_comments(self):
        """Test that mark_fuzzy adds fuzzy comment while preserving existing comments"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(self.test_content_with_comments)
            temp_file = f.name
        
        try:
            # Update with new translations and mark_fuzzy=True
            content = {
                'Hello': 'Bonjour',
                'World': 'Monde'
            }
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have fuzzy comments
            self.assertIn('#, fuzzy', written_content)
            
            # Should preserve existing comments
            self.assertIn('#. Key: Test_Key1', written_content)
            self.assertIn('#. Key: Test_Key2', written_content)
            
            # Verify fuzzy is before msgid but after other comments
            lines = written_content.split('\n')
            for i, line in enumerate(lines):
                if line.strip() == '#, fuzzy':
                    # Check that there's a comment before it and msgid after it
                    has_comment_before = i > 0 and lines[i-1].strip().startswith('#')
                    has_msgid_after = any(lines[j].strip().startswith('msgid "') and not lines[j].strip().startswith('msgid ""') 
                                         for j in range(i+1, min(i+5, len(lines))))
                    self.assertTrue(has_comment_before or has_msgid_after)
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_with_mark_fuzzy_empty_translations(self):
        """Test that mark_fuzzy does not add fuzzy to empty translations"""
        content = {
            'Hello': 'Hola',
            'World': '',  # Empty translation
            'Test': '   '  # Whitespace-only translation
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write with mark_fuzzy=True
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have fuzzy comment only for non-empty translation
            fuzzy_count = written_content.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 1)  # Only for 'Hello'
            
            # Verify 'Hello' has fuzzy
            lines = written_content.split('\n')
            hello_section = False
            has_fuzzy_for_hello = False
            for i, line in enumerate(lines):
                if 'msgid "Hello"' in line:
                    hello_section = True
                    # Check if fuzzy is before this msgid
                    for j in range(max(0, i-3), i):
                        if lines[j].strip() == '#, fuzzy':
                            has_fuzzy_for_hello = True
                            break
                elif hello_section and line.strip().startswith('msgid'):
                    break
            
            self.assertTrue(has_fuzzy_for_hello)
            
        finally:
            os.unlink(temp_file)

    def test_write_po_file_with_mark_fuzzy_does_not_duplicate(self):
        """Test that mark_fuzzy does not add duplicate fuzzy comments"""
        test_content_with_fuzzy = '''#, fuzzy
msgid "Hello"
msgstr "Hola"
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(test_content_with_fuzzy)
            temp_file = f.name
        
        try:
            # Update with mark_fuzzy=True
            content = {
                'Hello': 'Bonjour'
            }
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have only one fuzzy comment
            fuzzy_count = written_content.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 1)
            
        finally:
            os.unlink(temp_file)

    def test_add_fuzzy_comment_if_needed_with_translation(self):
        """Test _add_fuzzy_comment_if_needed adds fuzzy for non-empty translation"""
        entry = {
            'msgid': 'Hello',
            'msgstr': 'Hola',
            'comments': []
        }
        
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy=True)
        
        self.assertEqual(len(entry['comments']), 1)
        self.assertEqual(entry['comments'][0], '#, fuzzy')

    def test_add_fuzzy_comment_if_needed_without_translation(self):
        """Test _add_fuzzy_comment_if_needed does not add fuzzy for empty translation"""
        entry = {
            'msgid': 'Hello',
            'msgstr': '',
            'comments': []
        }
        
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy=True)
        
        self.assertEqual(len(entry['comments']), 0)

    def test_add_fuzzy_comment_if_needed_whitespace_only(self):
        """Test _add_fuzzy_comment_if_needed does not add fuzzy for whitespace-only translation"""
        entry = {
            'msgid': 'Hello',
            'msgstr': '   ',
            'comments': []
        }
        
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy=True)
        
        self.assertEqual(len(entry['comments']), 0)

    def test_add_fuzzy_comment_if_needed_mark_fuzzy_false(self):
        """Test _add_fuzzy_comment_if_needed does not add fuzzy when mark_fuzzy=False"""
        entry = {
            'msgid': 'Hello',
            'msgstr': 'Hola',
            'comments': []
        }
        
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy=False)
        
        self.assertEqual(len(entry['comments']), 0)

    def test_add_fuzzy_comment_if_needed_preserves_existing_comments(self):
        """Test _add_fuzzy_comment_if_needed preserves existing comments"""
        entry = {
            'msgid': 'Hello',
            'msgstr': 'Hola',
            'comments': ['#. Key: Test_Key', '#: file.py:123']
        }
        
        _add_fuzzy_comment_if_needed(entry, mark_fuzzy=True)
        
        # Should have 3 comments: fuzzy + 2 existing
        self.assertEqual(len(entry['comments']), 3)
        self.assertEqual(entry['comments'][0], '#, fuzzy')
        self.assertIn('#. Key: Test_Key', entry['comments'])
        self.assertIn('#: file.py:123', entry['comments'])

    def test_write_po_file_with_mark_fuzzy_template_based(self):
        """Test mark_fuzzy works when creating from template"""
        # Create a source template file
        template_content = '''msgid "Hello"
msgstr ""

msgid "World"
msgstr ""
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as template_file:
            template_file.write(template_content)
            template_path = template_file.name
        
        # Create target file path (different language)
        target_path = template_path.replace('.po', '_es.po')
        
        try:
            # Write with translations and mark_fuzzy=True
            content = {
                'Hello': 'Hola',
                'World': 'Mundo'
            }
            write_po_file(target_path, content, mark_fuzzy=True)
            
            # Read it back
            with open(target_path, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should have fuzzy comments
            self.assertIn('#, fuzzy', written_content)
            fuzzy_count = written_content.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 2)
            
        finally:
            if os.path.exists(template_path):
                os.unlink(template_path)
            if os.path.exists(target_path):
                os.unlink(target_path)

    def test_write_po_file_roundtrip_with_mark_fuzzy(self):
        """Test reading and writing PO file with mark_fuzzy preserves fuzzy comments"""
        content = {
            'Hello': 'Hola',
            'World': 'Mundo'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write with mark_fuzzy=True
            write_po_file(temp_file, content, mark_fuzzy=True)
            
            # Read it back
            read_content = read_po_file(temp_file)
            
            # Verify content
            self.assertEqual(read_content['Hello'], 'Hola')
            self.assertEqual(read_content['World'], 'Mundo')
            
            # Read raw file to verify fuzzy comments are still there
            with open(temp_file, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            self.assertIn('#, fuzzy', raw_content)
            
            # Write again with mark_fuzzy=True (should not duplicate)
            write_po_file(temp_file, read_content, mark_fuzzy=True)
            
            # Read raw again
            with open(temp_file, 'r', encoding='utf-8') as f:
                raw_content_after = f.read()
            
            # Should still have only 2 fuzzy comments
            fuzzy_count = raw_content_after.count('#, fuzzy')
            self.assertEqual(fuzzy_count, 2)
            
        finally:
            os.unlink(temp_file)


if __name__ == '__main__':
    unittest.main()

