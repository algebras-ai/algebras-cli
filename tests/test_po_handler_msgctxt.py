"""
Unit tests for PO handler msgctxt functionality
"""

import unittest
import tempfile
import os
from algebras.utils.po_handler import (
    read_po_file, 
    write_po_file, 
    _parse_po_content, 
    _reconstruct_po_content
)


class TestPOHandlerMsgctxt(unittest.TestCase):
    """Test cases for PO handler msgctxt functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_content_with_msgctxt = '''#. Key:	Core_TempSymb_Lore
#. SourceLocation:	/Game/Tempest/UI/Texts/ST_Veti_Codex.ST_Veti_Codex
#: /Game/Tempest/UI/Texts/ST_Veti_Codex.ST_Veti_Codex
msgctxt "ST_Veti_Codex"
msgid "The lesser beings view the Tempest as a resource to be harvested, a commodity to be fought over. This is a profound, infantile misunderstanding. To the Veti, the Tempest is not separate from their being; it is their being. It is their externalized circulatory system, a planetary network of life-giving energy that connects them to the Earth itself. Their warriors move through its crimson fields not as trespassers, but as a body's own cells moving through the bloodstream. The debilitating Tempest Charge that cripples foreign technology is, to them, a nurturing and invigorating flow.\\n\\nThis symbiotic relationship dictates their method of energy acquisition. The humans crudely rip Tempest from the earth, leaving behind dead, barren chasms. The Veti Refinement Altar does not deplete; it recirculates. It acts as a localized heart, drawing in ambient Tempest energy and channeling it into the Veti's synthesis systems while simultaneously stimulating the field's regenerative growth. This is not harvesting; it is conscious and deliberate self-regulation.\\n\\nWhile a Veti can function in a world barren of Tempest, this state is seen as a diminished existence, a separation from their vital essence. To be cut off from the Tempest is to be cut off from the whole of the Veti consciousness. Reconnecting with the network is therefore not merely about refueling; it is about returning to a state of biological and psychic completeness."
msgstr ""
'''

        self.test_content_simple_msgctxt = '''#. Key:	Test_Key
msgctxt "TestContext"
msgid "Hello world"
msgstr "Hola mundo"
'''

        self.test_content_multiline_msgctxt = '''#. Key:	Test_Multiline
msgctxt "TestContext"
msgid "This is a long message that should be formatted as multiline in the PO file format because it exceeds the typical line length limits and contains multiple sentences that need to be properly handled."
msgstr "Esta es un mensaje largo que debería formatearse como multilínea en el formato de archivo PO porque excede los límites típicos de longitud de línea y contiene múltiples oraciones que necesitan ser manejadas adecuadamente."
'''

    def test_parse_msgctxt_simple(self):
        """Test parsing a simple PO entry with msgctxt"""
        entries = _parse_po_content(self.test_content_simple_msgctxt)
        
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        
        # Check msgctxt parsing
        self.assertEqual(entry['msgctxt'], 'TestContext')
        self.assertEqual(entry['msgid'], 'Hello world')
        self.assertEqual(entry['msgstr'], 'Hola mundo')
        
        # Check that comments are preserved
        self.assertEqual(len(entry['comments']), 1)
        self.assertEqual(entry['comments'][0], '#. Key:\tTest_Key')

    def test_parse_msgctxt_complex(self):
        """Test parsing a complex PO entry with msgctxt and long text"""
        entries = _parse_po_content(self.test_content_with_msgctxt)
        
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        
        # Check msgctxt parsing
        self.assertEqual(entry['msgctxt'], 'ST_Veti_Codex')
        self.assertTrue(entry['msgid'].startswith('The lesser beings view the Tempest'))
        self.assertEqual(entry['msgstr'], '')
        
        # Check that comments are preserved
        self.assertEqual(len(entry['comments']), 3)
        self.assertIn('Core_TempSymb_Lore', entry['comments'][0])

    def test_parse_msgctxt_multiline(self):
        """Test parsing msgctxt with multiline content"""
        entries = _parse_po_content(self.test_content_multiline_msgctxt)
        
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        
        # Check msgctxt parsing
        self.assertEqual(entry['msgctxt'], 'TestContext')
        self.assertTrue(entry['msgid'].startswith('This is a long message'))
        self.assertTrue(entry['msgstr'].startswith('Esta es un mensaje largo'))

    def test_reconstruct_msgctxt_simple(self):
        """Test reconstructing a simple PO entry with msgctxt"""
        entries = _parse_po_content(self.test_content_simple_msgctxt)
        
        # Update the msgstr with a translation
        entries[0]['msgstr'] = 'Bonjour le monde'
        
        reconstructed = _reconstruct_po_content(entries, self.test_content_simple_msgctxt)
        
        # Check that the structure is correct
        lines = reconstructed.split('\n')
        
        # Should have: comments, msgctxt, msgid, msgstr
        self.assertIn('msgctxt "TestContext"', reconstructed)
        self.assertIn('msgid "Hello world"', reconstructed)
        self.assertIn('msgstr "Bonjour le monde"', reconstructed)
        
        # Should not have the bug pattern (empty msgid/msgstr followed by another msgid)
        self.assertFalse(self._has_bug_pattern(reconstructed))

    def test_reconstruct_msgctxt_complex(self):
        """Test reconstructing a complex PO entry with msgctxt"""
        entries = _parse_po_content(self.test_content_with_msgctxt)
        
        # Update the msgstr with a translation
        entries[0]['msgstr'] = 'Низшие существа рассматривают Бурю как ресурс для добычи, товар, за который нужно сражаться. Это глубокое, инфантильное непонимание. Для Вети Буря не отделима от их существа; она и есть их существо. Это их экстернализированная система кровообращения, планетарная сеть жизненной энергии, которая соединяет их с самой Землёй. Их воины движутся через её багровые поля не как нарушители, а как клетки тела, движущиеся по кровотоку. Изнуряющий Заряд Бури, который парализует чужеродные технологии, для них является питательным и бодрящим потоком.\\n\\nЭти симбиотические отношения определяют их метод получения энергии. Люди грубо вырывают Бурю из земли, оставляя после себя мёртвые, бесплодные пропасти. Алтарь Очищения Вети не истощает; он перенаправляет. Он действует как локализованное сердце, втягивая окружающую энергию Бури и направляя её в системы синтеза Вети, одновременно стимулируя регенеративный рост поля. Это не сбор урожая; это сознательная и целенаправленная саморегуляция.\\n\\nХотя Вети может функционировать в мире, лишённом Бури, такое состояние рассматривается как ущербное существование, отделение от их жизненной сущности. Быть отрезанным от Бури — значит быть отрезанным от всего сознания Вети. Поэтому воссоединение с сетью — это не просто вопрос пополнения запасов; это возвращение к состоянию биологической и психической целостности.'
        
        reconstructed = _reconstruct_po_content(entries, self.test_content_with_msgctxt)
        
        # Check that the structure is correct
        self.assertIn('msgctxt "ST_Veti_Codex"', reconstructed)
        self.assertIn('Core_TempSymb_Lore', reconstructed)
        self.assertTrue('The lesser beings view the Tempest' in reconstructed)
        self.assertTrue('Низшие существа рассматривают Бурю' in reconstructed)
        
        # Should not have the bug pattern
        self.assertFalse(self._has_bug_pattern(reconstructed))

    def test_read_write_msgctxt_roundtrip(self):
        """Test reading and writing a PO file with msgctxt (roundtrip)"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(self.test_content_simple_msgctxt)
            temp_file = f.name
        
        try:
            # Read the file
            content = read_po_file(temp_file)
            
            # Should have the correct content
            self.assertEqual(len(content), 1)
            self.assertIn('Hello world', content)
            self.assertEqual(content['Hello world'], 'Hola mundo')
            
            # Write it back
            write_po_file(temp_file, content)
            
            # Read it again and verify structure
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should not have the bug pattern
            self.assertFalse(self._has_bug_pattern(written_content))
            
            # Should preserve msgctxt
            self.assertIn('msgctxt "TestContext"', written_content)
            
        finally:
            os.unlink(temp_file)

    def test_read_write_msgctxt_new_file(self):
        """Test writing a new PO file with msgctxt content"""
        content = {
            'Hello world': 'Hola mundo',
            'Goodbye': 'Adiós'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            temp_file = f.name
        
        try:
            # Write the content
            write_po_file(temp_file, content)
            
            # Read it back
            with open(temp_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Should not have the bug pattern
            self.assertFalse(self._has_bug_pattern(written_content))
            
            # Should have the correct entries
            self.assertIn('msgid "Hello world"', written_content)
            self.assertIn('msgstr "Hola mundo"', written_content)
            self.assertIn('msgid "Goodbye"', written_content)
            self.assertIn('msgstr "Adiós"', written_content)
            
        finally:
            os.unlink(temp_file)

    def test_msgctxt_without_msgid(self):
        """Test handling of msgctxt without msgid (edge case)"""
        content_without_msgid = '''#. Key:	Test_Key
msgctxt "TestContext"
msgstr "Some translation"
'''
        
        entries = _parse_po_content(content_without_msgid)
        
        # Should still parse the msgctxt
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['msgctxt'], 'TestContext')
        self.assertEqual(entry['msgid'], '')
        self.assertEqual(entry['msgstr'], 'Some translation')

    def test_multiple_entries_with_msgctxt(self):
        """Test parsing multiple entries with msgctxt"""
        content_multiple = '''#. Key:	Test_Key1
msgctxt "Context1"
msgid "Hello"
msgstr "Hola"

#. Key:	Test_Key2
msgctxt "Context2"
msgid "World"
msgstr "Mundo"
'''
        
        entries = _parse_po_content(content_multiple)
        
        self.assertEqual(len(entries), 2)
        
        # First entry
        self.assertEqual(entries[0]['msgctxt'], 'Context1')
        self.assertEqual(entries[0]['msgid'], 'Hello')
        self.assertEqual(entries[0]['msgstr'], 'Hola')
        
        # Second entry
        self.assertEqual(entries[1]['msgctxt'], 'Context2')
        self.assertEqual(entries[1]['msgid'], 'World')
        self.assertEqual(entries[1]['msgstr'], 'Mundo')

    def _has_bug_pattern(self, content):
        """
        Check if the content has the bug pattern:
        empty msgid/msgstr followed by another msgid
        """
        lines = content.split('\n')
        
        for i in range(len(lines) - 2):
            if (lines[i].strip() == 'msgid ""' and 
                lines[i+1].strip() == 'msgstr ""'):
                # Look for the next non-empty line that starts with msgid
                for j in range(i+2, len(lines)):
                    if lines[j].strip():  # Skip empty lines
                        if lines[j].strip().startswith('msgid'):
                            return True
                        break
        
        return False

    def test_bug_pattern_detection(self):
        """Test that our bug pattern detection works correctly"""
        # Content with the bug pattern
        buggy_content = '''msgid ""
msgstr ""

msgid "Hello"
msgstr "Hola"
'''
        
        self.assertTrue(self._has_bug_pattern(buggy_content))
        
        # Content without the bug pattern
        correct_content = '''msgctxt "Context"
msgid "Hello"
msgstr "Hola"
'''
        
        self.assertFalse(self._has_bug_pattern(correct_content))

    def test_msgctxt_preservation_in_reconstruction(self):
        """Test that msgctxt is preserved during reconstruction"""
        entries = _parse_po_content(self.test_content_simple_msgctxt)
        
        # Modify the msgstr
        entries[0]['msgstr'] = 'Modified translation'
        
        reconstructed = _reconstruct_po_content(entries, self.test_content_simple_msgctxt)
        
        # Check that msgctxt is preserved
        self.assertIn('msgctxt "TestContext"', reconstructed)
        self.assertIn('msgid "Hello world"', reconstructed)
        self.assertIn('msgstr "Modified translation"', reconstructed)
        
        # Check order: comments, msgctxt, msgid, msgstr
        lines = reconstructed.split('\n')
        msgctxt_line = None
        msgid_line = None
        msgstr_line = None
        
        for i, line in enumerate(lines):
            if line.strip().startswith('msgctxt'):
                msgctxt_line = i
            elif line.strip().startswith('msgid') and not line.strip().startswith('msgid ""'):
                msgid_line = i
            elif line.strip().startswith('msgstr') and not line.strip().startswith('msgstr ""'):
                msgstr_line = i
        
        # Check that the order is correct
        self.assertIsNotNone(msgctxt_line)
        self.assertIsNotNone(msgid_line)
        self.assertIsNotNone(msgstr_line)
        
        self.assertLess(msgctxt_line, msgid_line)
        self.assertLess(msgid_line, msgstr_line)


if __name__ == '__main__':
    unittest.main()
