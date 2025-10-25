# XLSX Translations Example

This example demonstrates how to use algebras-cli with XLSX files for multi-language translations.

## Project Structure

```
xlsx-translations/
├── locales/
│   └── strings.xlsx            # Multi-language XLSX file
├── .algebras.config            # Algebras configuration
└── README.md                   # This file
```

## Setup

1. **Initialize algebras-cli:**
   ```bash
   algebras init
   ```

2. **Add languages:**
   ```bash
   algebras add de fr es
   ```

3. **Translate:**
   ```bash
   algebras translate
   ```

## XLSX File Format

XLSX translation files use a spreadsheet structure with:

- **First column**: Translation keys
- **Subsequent columns**: Language codes (en, de, fr, es, etc.)
- **Header row**: Contains column names
- **Data rows**: Key-value pairs for each language

## Example XLSX Content

| key | en | de | fr | es |
|-----|----|----|----|----|
| app.title | My Application | Meine Anwendung | Mon Application | Mi Aplicación |
| welcome.message | Welcome to our amazing application! | Willkommen zu unserer erstaunlichen Anwendung! | Bienvenue dans notre application incroyable! | ¡Bienvenido a nuestra increíble aplicación! |
| login.button | Log In | Anmelden | Se connecter | Iniciar sesión |

## Usage

XLSX files are great for:

- **Professional workflows**: Easy to share with professional translators
- **Rich formatting**: Support for bold, colors, comments, etc.
- **Large datasets**: Better performance with large translation files
- **Excel integration**: Native support in Microsoft Excel

## Supported Features

- ✅ Multi-language XLSX reading and writing
- ✅ Language column detection
- ✅ Batch translation
- ✅ UI-safe translations
- ✅ Glossary support
- ✅ Distinction from glossary XLSX files
