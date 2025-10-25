"""
Tests for key counting logic in status command
"""

import tempfile
import os
import json
import pytest
from unittest.mock import patch, MagicMock

from algebras.commands.status_command import count_translated_keys, count_current_and_outdated_keys


class TestKeyCounting:
    """Tests for key counting functionality"""

    def test_count_translated_keys_json_flat(self):
        """Test counting keys in flat JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {
                'key1': 'translated value 1',
                'key2': 'translated value 2',
                'key3': '',  # empty value
                'key4': '   ',  # whitespace only
                'key5': 'translated value 5'
            }
            json.dump(test_data, f)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            assert translated == 3  # Only non-empty values
            assert total == 5  # All keys
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_json_nested(self):
        """Test counting keys in nested JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {
                'title': 'Welcome',
                'description': 'This is a test',
                'navigation': {
                    'home': 'Home',
                    'about': 'About',
                    'contact': 'Contact'
                },
                'buttons': {
                    'submit': 'Submit',
                    'cancel': '',  # empty value
                    'login': 'Log In'
                },
                'errors': {
                    'required': 'This field is required',
                    'invalid_email': 'Please enter a valid email'
                }
            }
            json.dump(test_data, f)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count only leaf keys (strings), not parent objects
            # Leaf keys: title, description, navigation.home, navigation.about, 
            # navigation.contact, buttons.submit, buttons.cancel, buttons.login,
            # errors.required, errors.invalid_email = 10 total
            # Translated: all except buttons.cancel (empty) = 9 translated
            assert translated == 9
            assert total == 10
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_po(self):
        """Test counting keys in PO file"""
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.po', delete=False) as f:
            po_content = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Hola"

msgid "Goodbye"
msgstr "Adiós"

msgid "Welcome"
msgstr ""  # empty translation

msgid "Thank you"
msgstr "   "  # whitespace only

msgid "Please"
msgstr "Por favor"
'''
            f.write(po_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count all msgid entries (excluding empty msgid)
            # Total: Hello, Goodbye, Welcome, Thank you, Please = 5
            # Translated: Hello, Goodbye, Please = 3 (Welcome and Thank you are empty)
            assert translated == 3
            assert total == 5
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_xml(self):
        """Test counting keys in Android XML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Test App</string>
    <string name="welcome">Welcome</string>
    <string name="goodbye">Goodbye</string>
    <string name="empty_key"></string>
    <string name="whitespace_key">   </string>
    <string name="login">Log In</string>
</resources>'''
            f.write(xml_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count all string entries
            # Total: app_name, welcome, goodbye, empty_key, whitespace_key, login = 6
            # Translated: app_name, welcome, goodbye, login = 4 (empty_key and whitespace_key are empty)
            assert translated == 4
            assert total == 6
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_yaml(self):
        """Test counting keys in YAML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = '''title: "Welcome"
description: "This is a test"
navigation:
  home: "Home"
  about: "About"
  contact: ""
buttons:
  submit: "Submit"
  cancel: "   "
  login: "Log In"
'''
            f.write(yaml_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count only leaf keys (strings)
            # Leaf keys: title, description, navigation.home, navigation.about, 
            # navigation.contact, buttons.submit, buttons.cancel, buttons.login = 8 total
            # Translated: all except navigation.contact (empty) and buttons.cancel (whitespace) = 6
            assert translated == 6
            assert total == 8
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_html(self):
        """Test counting keys in HTML file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            html_content = '''<!DOCTYPE html>
<html>
<head>
    <title data-i18n="title">Welcome</title>
</head>
<body>
    <h1 data-i18n="heading">Hello World</h1>
    <p data-i18n="description">This is a test</p>
    <button data-i18n="submit">Submit</button>
    <span data-i18n="empty"></span>
    <div data-i18n="whitespace">   </div>
</body>
</html>'''
            f.write(html_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # HTML handler extracts text content and uses hash-based keys
            # Only non-empty text content is extracted
            # Total: 4 keys (Welcome, Hello World, This is a test, Submit)
            # Translated: 4 keys (all are non-empty)
            assert translated == 4
            assert total == 4
        finally:
            os.unlink(temp_file)

    def test_count_current_and_outdated_keys_json_nested(self):
        """Test counting current and outdated keys in nested JSON files"""
        # Create source file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as source_f:
            source_data = {
                'title': 'Welcome',
                'description': 'This is a test',
                'navigation': {
                    'home': 'Home',
                    'about': 'About',
                    'contact': 'Contact'
                },
                'buttons': {
                    'submit': 'Submit',
                    'cancel': 'Cancel',
                    'login': 'Log In'
                },
                'errors': {
                    'required': 'This field is required',
                    'invalid_email': 'Please enter a valid email'
                }
            }
            json.dump(source_data, source_f)
            source_file = source_f.name

        # Create target file (partially translated)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as target_f:
            target_data = {
                'title': 'Bienvenue',
                'description': 'Ceci est un test',
                'navigation': {
                    'home': 'Accueil',
                    'about': 'À propos',
                    'contact': 'Contact'
                },
                'buttons': {
                    'submit': 'Soumettre',
                    'cancel': '',  # empty translation
                    'login': 'Connexion'
                },
                # Missing errors section entirely
                'old_key': 'Old value'  # outdated key
            }
            json.dump(target_data, target_f)
            target_file = target_f.name

        try:
            current, outdated = count_current_and_outdated_keys(source_file, target_file)
            
            # Source has 11 leaf keys: title, description, navigation.home, navigation.about,
            # navigation.contact, buttons.submit, buttons.cancel, buttons.login,
            # errors.required, errors.invalid_email
            # Target has 8 leaf keys: title, description, navigation.home, navigation.about,
            # navigation.contact, buttons.submit, buttons.cancel (empty), buttons.login, old_key
            
            # Current translated: title, description, navigation.home, navigation.about,
            # navigation.contact, buttons.submit, buttons.login = 7
            # (buttons.cancel is empty, errors.required and errors.invalid_email are missing)
            
            # Outdated: old_key (exists in target but not in source)
            assert current == 7
            assert outdated == 1
        finally:
            os.unlink(source_file)
            os.unlink(target_file)

    def test_count_current_and_outdated_keys_po(self):
        """Test counting current and outdated keys in PO files"""
        # Create source PO file
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.po', delete=False) as source_f:
            source_content = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Hello"

msgid "Goodbye"
msgstr "Goodbye"

msgid "Welcome"
msgstr "Welcome"

msgid "Thank you"
msgstr "Thank you"
'''
            source_f.write(source_content)
            source_file = source_f.name

        # Create target PO file (partially translated)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.po', delete=False) as target_f:
            target_content = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Hola"

msgid "Goodbye"
msgstr "Adiós"

msgid "Welcome"
msgstr ""  # empty translation

msgid "Old message"
msgstr "Mensaje antiguo"  # outdated key
'''
            target_f.write(target_content)
            target_file = target_f.name

        try:
            current, outdated = count_current_and_outdated_keys(source_file, target_file)
            
            # Source has 4 keys: Hello, Goodbye, Welcome, Thank you
            # Target has 4 keys: Hello, Goodbye, Welcome (empty), Old message
            
            # Current translated: Hello, Goodbye = 2
            # (Welcome is empty, Thank you is missing)
            
            # Outdated: Old message (exists in target but not in source)
            assert current == 2
            assert outdated == 1
        finally:
            os.unlink(source_file)
            os.unlink(target_file)

    def test_count_current_and_outdated_keys_xml(self):
        """Test counting current and outdated keys in Android XML files"""
        # Create source XML file
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.xml', delete=False) as source_f:
            source_content = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Test App</string>
    <string name="welcome">Welcome</string>
    <string name="goodbye">Goodbye</string>
    <string name="login">Log In</string>
</resources>'''
            source_f.write(source_content)
            source_file = source_f.name

        # Create target XML file (partially translated)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.xml', delete=False) as target_f:
            target_content = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Aplicación de Prueba</string>
    <string name="welcome">Bienvenido</string>
    <string name="goodbye"></string>  <!-- empty translation -->
    <string name="old_key">Clave antigua</string>  <!-- outdated key -->
</resources>'''
            target_f.write(target_content)
            target_file = target_f.name

        try:
            current, outdated = count_current_and_outdated_keys(source_file, target_file)
            
            # Source has 4 keys: app_name, welcome, goodbye, login
            # Target has 4 keys: app_name, welcome, goodbye (empty), old_key
            
            # Current translated: app_name, welcome = 2
            # (goodbye is empty, login is missing)
            
            # Outdated: old_key (exists in target but not in source)
            assert current == 2
            assert outdated == 1
        finally:
            os.unlink(source_file)
            os.unlink(target_file)

    def test_count_translated_keys_nonexistent_file(self):
        """Test counting keys for non-existent file"""
        translated, total = count_translated_keys('nonexistent_file.json')
        assert translated == 0
        assert total == 0

    def test_count_current_and_outdated_keys_nonexistent_files(self):
        """Test counting keys for non-existent files"""
        current, outdated = count_current_and_outdated_keys('source.json', 'target.json')
        assert current == 0
        assert outdated == 0

    def test_count_translated_keys_malformed_json(self):
        """Test counting keys for malformed JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"invalid": json}')  # Invalid JSON
            temp_file = f.name

        try:
            with patch('click.echo') as mock_echo:
                translated, total = count_translated_keys(temp_file)
                assert translated == 0
                assert total == 0
                # Should show warning message
                assert mock_echo.called
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_empty_file(self):
        """Test counting keys for empty file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('')  # Empty file
            temp_file = f.name

        try:
            with patch('click.echo') as mock_echo:
                translated, total = count_translated_keys(temp_file)
                assert translated == 0
                assert total == 0
                # Should show warning message
                assert mock_echo.called
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_whitespace_values(self):
        """Test counting keys with various whitespace values"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {
                'normal': 'Normal value',
                'empty': '',
                'spaces': '   ',
                'tabs': '\t\t\t',
                'newlines': '\n\n\n',
                'mixed_whitespace': ' \t\n ',
                'zero_width': '\u200B',  # Zero-width space
                'another_normal': 'Another normal value'
            }
            json.dump(test_data, f)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Only 'normal', 'another_normal', and 'zero_width' should be counted as translated
            # 'zero_width' contains a zero-width space which is not stripped by str.strip()
            # All others are empty or whitespace-only
            assert translated == 3
            assert total == 8
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_none_values(self):
        """Test counting keys with None values"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {
                'normal': 'Normal value',
                'none_value': None,
                'empty': '',
                'another_normal': 'Another normal value'
            }
            json.dump(test_data, f)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Only 'normal' and 'another_normal' should be counted as translated
            # 'none_value' is not a string so not counted as leaf key
            # 'empty' is a string but empty so not counted as translated
            # Total leaf keys: normal, empty, another_normal = 3
            # Translated: normal, another_normal = 2
            assert translated == 2
            assert total == 3
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_typescript(self):
        """Test counting keys in TypeScript file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
            ts_content = '''export const translations = {
  title: "Welcome",
  description: "This is a test",
  navigation: {
    home: "Home",
    about: "About",
    contact: ""
  },
  buttons: {
    submit: "Submit",
    cancel: "   ",
    login: "Log In"
  }
};'''
            f.write(ts_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count only leaf keys (strings)
            # Leaf keys: title, description, navigation.home, navigation.about, 
            # navigation.contact, buttons.submit, buttons.cancel, buttons.login = 8 total
            # Translated: all except navigation.contact (empty) and buttons.cancel (whitespace) = 6
            assert translated == 6
            assert total == 8
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_ios_strings(self):
        """Test counting keys in iOS strings file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.strings', delete=False) as f:
            strings_content = '''/* 
  Localizable.strings
  TestApp
*/

"app_name" = "Test App";
"welcome" = "Welcome";
"goodbye" = "Goodbye";
"empty_key" = "";
"whitespace_key" = "   ";
"login" = "Log In";
"register" = "Register";
'''
            f.write(strings_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count all string entries
            # Total: app_name, welcome, goodbye, empty_key, whitespace_key, login, register = 7
            # Translated: app_name, welcome, goodbye, login, register = 5 (empty_key and whitespace_key are empty)
            assert translated == 5
            assert total == 7
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_ios_stringsdict(self):
        """Test counting keys in iOS stringsdict file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.stringsdict', delete=False) as f:
            stringsdict_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>one</key>
            <string>%d item</string>
            <key>other</key>
            <string>%d items</string>
        </dict>
    </dict>
    <key>empty_key</key>
    <string></string>
    <key>normal_key</key>
    <string>Normal value</string>
</dict>
</plist>'''
            f.write(stringsdict_content)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Should count all string entries (stringsdict extracts nested strings as flat keys)
            # Total: items_count.count.one, items_count.count.other, empty_key, normal_key = 4
            # Translated: items_count.count.one, items_count.count.other, normal_key = 3 (empty_key is empty)
            assert translated == 3
            assert total == 4
        finally:
            os.unlink(temp_file)

    def test_count_translated_keys_mixed_whitespace_unicode(self):
        """Test counting keys with various Unicode whitespace characters"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {
                'normal': 'Normal value',
                'empty': '',
                'regular_spaces': '   ',
                'tabs': '\t\t\t',
                'newlines': '\n\n\n',
                'zero_width_space': '\u200B',  # Zero-width space
                'zero_width_non_joiner': '\u200C',  # Zero-width non-joiner
                'zero_width_joiner': '\u200D',  # Zero-width joiner
                'narrow_no_break_space': '\u202F',  # Narrow no-break space
                'word_joiner': '\u2060',  # Word joiner
                'another_normal': 'Another normal value'
            }
            json.dump(test_data, f)
            temp_file = f.name

        try:
            translated, total = count_translated_keys(temp_file)
            # Only 'normal', 'another_normal', and Unicode characters that aren't stripped
            # by str.strip() should be counted as translated
            # Most Unicode whitespace characters are not stripped by str.strip()
            assert translated == 6  # normal, another_normal, and 4 Unicode chars
            assert total == 11
        finally:
            os.unlink(temp_file)
