# Gettext PO Format Guide

[![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com/) [![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![Rails](https://img.shields.io/badge/Rails-CC0000?style=flat&logo=ruby-on-rails&logoColor=white)](https://rubyonrails.org/)

## Overview

Gettext PO (Portable Object) files are the standard format for GNU gettext internationalization. They are widely used in web frameworks like Django, Flask, Rails, and many other applications for storing translated strings with metadata.

## When to Use Gettext PO

- **Django Applications**: Django projects using i18n
- **Flask Applications**: Flask apps with Flask-Babel
- **Ruby on Rails**: Rails applications with i18n
- **PHP Applications**: PHP apps using gettext
- **Python Applications**: Any Python app using gettext
- **Web Frameworks**: Most web frameworks support gettext
- **Desktop Applications**: GTK, Qt, and other desktop apps

## File Structure

Gettext projects use a specific directory structure for PO files:

```
locale/
├── en/                 # English (base language)
│   └── LC_MESSAGES/
│       ├── django.po
│       └── messages.po
├── es/                 # Spanish translations
│   └── LC_MESSAGES/
│       ├── django.po
│       └── messages.po
├── fr/                 # French translations
│   └── LC_MESSAGES/
│       ├── django.po
│       └── messages.po
└── ru/                 # Russian translations
    └── LC_MESSAGES/
        ├── django.po
        └── messages.po
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "locale/en/LC_MESSAGES/django.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
  "locale/en/LC_MESSAGES/messages.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/messages.po"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Django Project:**
```yaml
source_files:
  "locale/en/LC_MESSAGES/django.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
```

**Flask Project:**
```yaml
source_files:
  "translations/en/LC_MESSAGES/messages.po":
    destination_path: "translations/%algebras_locale_code%/LC_MESSAGES/messages.po"
```

**Rails Project:**
```yaml
source_files:
  "config/locales/en.po":
    destination_path: "config/locales/%algebras_locale_code%.po"
```

**Multiple PO Files:**
```yaml
source_files:
  "locale/en/LC_MESSAGES/django.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
  "locale/en/LC_MESSAGES/djangojs.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/djangojs.po"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your project directory
cd your-project

# Initialize algebras-cli
algebras init

# Add target languages
algebras add es fr ru
```

### 2. Basic Translation

```bash
# Translate all missing keys
algebras translate

# Translate specific language
algebras translate --language es

# Force translation (even if up-to-date)
algebras translate --force
```

### 3. Update Translations

```bash
# Update missing keys only
algebras update

# Update specific language
algebras update --language fr

# Full translation update
algebras update --full
```

### 4. Check Status

```bash
# Check all languages
algebras status

# Check specific language
algebras status --language ru
```

### 5. Review Translations

```bash
# Review all languages
algebras review

# Review specific language
algebras review --language es
```

## Best Practices

### 1. PO File Structure

- **Proper formatting**: Use consistent formatting and structure
- **Header information**: Include proper header information
- **Comments**: Add comments for translators
- **Context**: Use msgctxt for context when needed

```po
# SOME DESCRIPTIVE TITLE.
# Copyright (C) YEAR THE PACKAGE'S COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
#
msgid ""
msgstr ""
"Project-Id-Version: PACKAGE VERSION\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

#: views.py:123
msgid "Welcome to our application!"
msgstr "Welcome to our application!"

#: templates/base.html:45
msgid "Log In"
msgstr "Log In"
```

### 2. Key Naming Conventions

- **Descriptive strings**: Use clear, descriptive strings
- **Context when needed**: Use msgctxt for ambiguous strings
- **Consistent terminology**: Use consistent terminology across files
- **Avoid abbreviations**: Use full words when possible

```po
# Good: Clear and descriptive
msgid "User profile settings"
msgstr "User profile settings"

# Good: With context for disambiguation
msgctxt "button"
msgid "Save"
msgstr "Save"

msgctxt "file"
msgid "Save"
msgstr "Save"

# Avoid: Unclear abbreviations
msgid "Usr Prof Set"
msgstr "Usr Prof Set"
```

### 3. Pluralization Support

- **Plural forms**: Use proper plural forms for different quantities
- **Plural rules**: Include plural rules in header
- **Language-specific rules**: Consider language-specific plural rules

```po
# Header with plural rules
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

# Pluralization example
msgid "You have %d message"
msgid_plural "You have %d messages"
msgstr[0] "You have %d message"
msgstr[1] "You have %d messages"
```

### 4. String Formatting

- **String formatting**: Use proper string formatting for dynamic content
- **Escape sequences**: Use proper escape sequences for special characters
- **HTML formatting**: Use HTML tags for text formatting when needed

```po
# String formatting
msgid "Welcome, %(name)s!"
msgstr "Welcome, %(name)s!"

# HTML formatting
msgid "This is <b>bold</b> and <i>italic</i> text"
msgstr "This is <b>bold</b> and <i>italic</i> text"

# Escape sequences
msgid "This is a \"quoted\" string"
msgstr "This is a \"quoted\" string"
```

### 5. Comments and Documentation

- **Translator comments**: Add comments for translators
- **Developer comments**: Add comments for developers
- **Context information**: Provide context for complex strings

```po
# Translator comment
#. This string is used in the login screen
#. It should be friendly and welcoming
msgid "Welcome! Please sign in to continue"
msgstr "Welcome! Please sign in to continue"

# Developer comment
#: views.py:123
msgid "User profile updated successfully"
msgstr "User profile updated successfully"
```

## Common Use Cases

### Django Application

```po
# django.po
msgid ""
msgstr ""
"Project-Id-Version: My Django App\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: models.py:45
msgid "User"
msgstr "User"

#: views.py:123
msgid "Welcome to our application!"
msgstr "Welcome to our application!"

#: templates/base.html:45
msgid "Log In"
msgstr "Log In"

#: templates/base.html:46
msgid "Log Out"
msgstr "Log Out"
```

### Flask Application

```po
# messages.po
msgid ""
msgstr ""
"Project-Id-Version: My Flask App\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: app.py:45
msgid "Welcome to our Flask application!"
msgstr "Welcome to our Flask application!"

#: templates/index.html:23
msgid "Home"
msgstr "Home"

#: templates/index.html:24
msgid "About"
msgstr "About"
```

### Ruby on Rails Application

```po
# en.po
msgid ""
msgstr ""
"Project-Id-Version: My Rails App\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: app/views/layouts/application.html.erb:23
msgid "My Rails Application"
msgstr "My Rails Application"

#: app/views/home/index.html.erb:12
msgid "Welcome to our Rails application!"
msgstr "Welcome to our Rails application!"
```

## Example Files

### Before Translation (en/LC_MESSAGES/django.po)
```po
# SOME DESCRIPTIVE TITLE.
# Copyright (C) 2024 THE PACKAGE'S COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2024.
#
msgid ""
msgstr ""
"Project-Id-Version: My Django App\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: 2024-01-01 12:00+0000\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: en\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: models.py:45
msgid "User"
msgstr "User"

#: views.py:123
msgid "Welcome to our application!"
msgstr "Welcome to our application!"

#: templates/base.html:45
msgid "Log In"
msgstr "Log In"

#: templates/base.html:46
msgid "Log Out"
msgstr "Log Out"

#: templates/base.html:47
msgid "Save"
msgstr "Save"

#: templates/base.html:48
msgid "Cancel"
msgstr "Cancel"

#: templates/base.html:49
msgid "Delete"
msgstr "Delete"

#: templates/base.html:50
msgid "Edit"
msgstr "Edit"

#: templates/profile.html:23
msgid "User Profile"
msgstr "User Profile"

#: templates/profile.html:24
msgid "Tap to edit your profile"
msgstr "Tap to edit your profile"

#: views.py:124
msgid "Operation completed successfully"
msgstr "Operation completed successfully"

#: views.py:125
msgid "An error occurred"
msgstr "An error occurred"

#: templates/base.html:51
msgid "Loading..."
msgstr "Loading..."
```

### After Translation (es/LC_MESSAGES/django.po)
```po
# SOME DESCRIPTIVE TITLE.
# Copyright (C) 2024 THE PACKAGE'S COPYRIGHT HOLDER
# This file is distributed under the same license as the PACKAGE package.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2024.
#
msgid ""
msgstr ""
"Project-Id-Version: My Django App\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: 2024-01-01 12:00+0000\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: LANGUAGE <LL@li.org>\n"
"Language: es\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"

#: models.py:45
msgid "User"
msgstr "Usuario"

#: views.py:123
msgid "Welcome to our application!"
msgstr "¡Bienvenido a nuestra aplicación!"

#: templates/base.html:45
msgid "Log In"
msgstr "Iniciar Sesión"

#: templates/base.html:46
msgid "Log Out"
msgstr "Cerrar Sesión"

#: templates/base.html:47
msgid "Save"
msgstr "Guardar"

#: templates/base.html:48
msgid "Cancel"
msgstr "Cancelar"

#: templates/base.html:49
msgid "Delete"
msgstr "Eliminar"

#: templates/base.html:50
msgid "Edit"
msgstr "Editar"

#: templates/profile.html:23
msgid "User Profile"
msgstr "Perfil de Usuario"

#: templates/profile.html:24
msgid "Tap to edit your profile"
msgstr "Toca para editar tu perfil"

#: views.py:124
msgid "Operation completed successfully"
msgstr "Operación completada exitosamente"

#: views.py:125
msgid "An error occurred"
msgstr "Ocurrió un error"

#: templates/base.html:51
msgid "Loading..."
msgstr "Cargando..."
```

## Advanced Features

### 1. Context Support

```po
# Context for disambiguation
msgctxt "button"
msgid "Save"
msgstr "Save"

msgctxt "file"
msgid "Save"
msgstr "Save"

msgctxt "game"
msgid "Save"
msgstr "Save"
```

### 2. Pluralization with Context

```po
# Pluralization with context
msgctxt "messages"
msgid "You have %d message"
msgid_plural "You have %d messages"
msgstr[0] "You have %d message"
msgstr[1] "You have %d messages"

msgctxt "items"
msgid "You have %d item"
msgid_plural "You have %d items"
msgstr[0] "You have %d item"
msgstr[1] "You have %d items"
```

### 3. String Formatting

```po
# String formatting with named parameters
msgid "Welcome, %(name)s!"
msgstr "Welcome, %(name)s!"

# String formatting with positional parameters
msgid "You have %d items in your cart"
msgstr "You have %d items in your cart"

# HTML formatting
msgid "This is <b>bold</b> and <i>italic</i> text"
msgstr "This is <b>bold</b> and <i>italic</i> text"
```

## Troubleshooting

### Common Issues

**PO file parsing errors:**
- Ensure valid PO file format
- Check for proper header information
- Validate PO file structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Pluralization issues:**
- Verify plural rules in header
- Check language-specific plural rules
- Ensure proper plural forms

**Encoding issues:**
- Save files as UTF-8
- Check for BOM (Byte Order Mark)
- Verify special characters are properly encoded

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Related Examples

- [Django Example](../../examples/django-app/) - Complete Django setup
- [Flask Example](../../examples/flask-app/) - Flask with Babel
- [Rails Example](../../examples/rails-app/) - Ruby on Rails i18n
