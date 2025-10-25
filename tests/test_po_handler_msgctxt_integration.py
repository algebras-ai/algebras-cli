"""
Integration tests for PO handler msgctxt functionality
"""

import unittest
import tempfile
import os
from algebras.utils.po_handler import read_po_file, write_po_file


class TestPOHandlerMsgctxtIntegration(unittest.TestCase):
    """Integration tests for PO handler msgctxt functionality"""
    
    def test_translation_workflow_with_msgctxt(self):
        """Test the complete translation workflow with msgctxt files
        
        Note: This test demonstrates the current limitation where msgctxt information
        is lost when using read_po_file/write_po_file because read_po_file only returns
        a simple key-value dictionary. The msgctxt fix works when writing to existing
        files that already have the structure, but not when creating new files.
        """
        
        # Create a test PO file with msgctxt
        test_content = '''#. Key:	Core_TempSymb_Lore
#. SourceLocation:	/Game/Tempest/UI/Texts/ST_Veti_Codex.ST_Veti_Codex
#: /Game/Tempest/UI/Texts/ST_Veti_Codex.ST_Veti_Codex
msgctxt "ST_Veti_Codex"
msgid "The lesser beings view the Tempest as a resource to be harvested, a commodity to be fought over. This is a profound, infantile misunderstanding. To the Veti, the Tempest is not separate from their being; it is their being. It is their externalized circulatory system, a planetary network of life-giving energy that connects them to the Earth itself. Their warriors move through its crimson fields not as trespassers, but as a body's own cells moving through the bloodstream. The debilitating Tempest Charge that cripples foreign technology is, to them, a nurturing and invigorating flow.\\n\\nThis symbiotic relationship dictates their method of energy acquisition. The humans crudely rip Tempest from the earth, leaving behind dead, barren chasms. The Veti Refinement Altar does not deplete; it recirculates. It acts as a localized heart, drawing in ambient Tempest energy and channeling it into the Veti's synthesis systems while simultaneously stimulating the field's regenerative growth. This is not harvesting; it is conscious and deliberate self-regulation.\\n\\nWhile a Veti can function in a world barren of Tempest, this state is seen as a diminished existence, a separation from their vital essence. To be cut off from the Tempest is to be cut off from the whole of the Veti consciousness. Reconnecting with the network is therefore not merely about refueling; it is about returning to a state of biological and psychic completeness."
msgstr ""
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(test_content)
            source_file = f.name
        
        try:
            # Step 1: Read the source file
            source_content = read_po_file(source_file)
            self.assertEqual(len(source_content), 1)
            
            # Find the target key
            target_key = None
            for key in source_content.keys():
                if 'The lesser beings view the Tempest' in key:
                    target_key = key
                    break
            
            self.assertIsNotNone(target_key, "Target key not found")
            
            # Step 2: Create target content with translation
            target_content = source_content.copy()
            target_content[target_key] = "Низшие существа рассматривают Бурю как ресурс для добычи, товар, за который нужно сражаться. Это глубокое, инфантильное непонимание. Для Вети Буря не отделима от их существа; она и есть их существо. Это их экстернализированная система кровообращения, планетарная сеть жизненной энергии, которая соединяет их с самой Землёй. Их воины движутся через её багровые поля не как нарушители, а как клетки тела, движущиеся по кровотоку. Изнуряющий Заряд Бури, который парализует чужеродные технологии, для них является питательным и бодрящим потоком.\\n\\nЭти симбиотические отношения определяют их метод получения энергии. Люди грубо вырывают Бурю из земли, оставляя после себя мёртвые, бесплодные пропасти. Алтарь Очищения Вети не истощает; он перенаправляет. Он действует как локализованное сердце, втягивая окружающую энергию Бури и направляя её в системы синтеза Вети, одновременно стимулируя регенеративный рост поля. Это не сбор урожая; это сознательная и целенаправленная саморегуляция.\\n\\nХотя Вети может функционировать в мире, лишённом Бури, такое состояние рассматривается как ущербное существование, отделение от их жизненной сущности. Быть отрезанным от Бури — значит быть отрезанным от всего сознания Вети. Поэтому воссоединение с сетью — это не просто вопрос пополнения запасов; это возвращение к состоянию биологической и психической целостности."
            
            # Step 3: Write the target file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
                target_file = f.name
            
            write_po_file(target_file, target_content)
            
            # Step 4: Verify the written file doesn't have the bug pattern
            with open(target_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Note: msgctxt information is lost when using read_po_file/write_po_file
            # because read_po_file only returns a simple key-value dictionary.
            # The msgctxt fix works when writing to existing files that already
            # have the structure, but not when creating new files.
            
            # Check that the basic structure is correct (no bug pattern)
            self.assertTrue('The lesser beings view the Tempest' in written_content)
            self.assertTrue('Низшие существа рассматривают Бурю' in written_content)
            
            # Check that we don't have the bug pattern
            lines = written_content.split('\n')
            empty_msgid_count = sum(1 for line in lines if line.strip() == 'msgid ""')
            
            # When writing to a new file, there should be 0 empty msgid entries (no header)
            # When writing to an existing file, there should be 1 empty msgid entry (header)
            self.assertLessEqual(empty_msgid_count, 1, f"Found {empty_msgid_count} empty msgid entries, expected 0 or 1")
            
            # Check for the specific bug pattern: empty msgid/msgstr followed by another msgid
            bug_pattern_found = False
            for i in range(len(lines) - 2):
                if (lines[i].strip() == 'msgid ""' and 
                    lines[i+1].strip() == 'msgstr ""'):
                    # Look for the next non-empty line that starts with msgid
                    for j in range(i+2, len(lines)):
                        if lines[j].strip():  # Skip empty lines
                            if lines[j].strip().startswith('msgid'):
                                bug_pattern_found = True
                                break
                            break
                    if bug_pattern_found:
                        break
            
            self.assertFalse(bug_pattern_found, "Bug pattern detected: empty msgid/msgstr followed by another msgid")
            
        finally:
            # Clean up
            if os.path.exists(source_file):
                os.unlink(source_file)
            if 'target_file' in locals() and os.path.exists(target_file):
                os.unlink(target_file)

    def test_multiple_entries_with_msgctxt_workflow(self):
        """Test translation workflow with multiple entries containing msgctxt
        
        Note: This test demonstrates the current limitation where msgctxt information
        is lost when using read_po_file/write_po_file because read_po_file only returns
        a simple key-value dictionary.
        """
        
        # Create a test PO file with multiple entries
        test_content = '''#. Key:	Test_Key1
msgctxt "Context1"
msgid "Hello"
msgstr ""

#. Key:	Test_Key2
msgctxt "Context2"
msgid "World"
msgstr ""
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
            f.write(test_content)
            source_file = f.name
        
        try:
            # Read the source file
            source_content = read_po_file(source_file)
            self.assertEqual(len(source_content), 2)
            
            # Create target content with translations
            target_content = source_content.copy()
            target_content['Hello'] = 'Hola'
            target_content['World'] = 'Mundo'
            
            # Write the target file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.po', delete=False) as f:
                target_file = f.name
            
            write_po_file(target_file, target_content)
            
            # Verify the written file
            with open(target_file, 'r', encoding='utf-8') as f:
                written_content = f.read()
            
            # Note: msgctxt information is lost when using read_po_file/write_po_file
            # because read_po_file only returns a simple key-value dictionary.
            
            # Check that both entries are present (without msgctxt)
            self.assertIn('msgid "Hello"', written_content)
            self.assertIn('msgid "World"', written_content)
            self.assertIn('msgstr "Hola"', written_content)
            self.assertIn('msgstr "Mundo"', written_content)
            
            # Check that we don't have the bug pattern
            lines = written_content.split('\n')
            empty_msgid_count = sum(1 for line in lines if line.strip() == 'msgid ""')
            # When writing to a new file, there should be 0 empty msgid entries (no header)
            # When writing to an existing file, there should be 1 empty msgid entry (header)
            self.assertLessEqual(empty_msgid_count, 1, f"Found {empty_msgid_count} empty msgid entries, expected 0 or 1")
            
        finally:
            # Clean up
            if os.path.exists(source_file):
                os.unlink(source_file)
            if 'target_file' in locals() and os.path.exists(target_file):
                os.unlink(target_file)


if __name__ == '__main__':
    unittest.main()
