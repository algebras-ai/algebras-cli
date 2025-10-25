# CSV Translations Example

This example demonstrates how to use algebras-cli with CSV files for multi-language translations.

## Project Structure

```
csv-translations/
├── locales/
│   └── strings.csv             # Multi-language CSV file
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

## CSV File Format

CSV translation files use a simple structure with:

- **First column**: Translation keys
- **Subsequent columns**: Language codes (en, de, fr, es, etc.)
- **Header row**: Contains column names
- **Data rows**: Key-value pairs for each language

## Example CSV Content

```csv
key,en,de,fr,es
app.title,My Application,Meine Anwendung,Mon Application,Mi Aplicación
welcome.message,Welcome to our amazing application!,Willkommen zu unserer erstaunlichen Anwendung!,Bienvenue dans notre application incroyable!,¡Bienvenido a nuestra increíble aplicación!
login.button,Log In,Anmelden,Se connecter,Iniciar sesión
```

## Usage

CSV files are great for:

- **Simple applications**: When you don't need complex localization features
- **Spreadsheet editing**: Easy to edit in Excel or Google Sheets
- **Multi-language management**: All languages in one file
- **Import/export**: Easy to share with translators

## Supported Features

- ✅ Multi-language CSV reading and writing
- ✅ Language column detection
- ✅ Batch translation
- ✅ UI-safe translations
- ✅ Glossary support
- ✅ Distinction from glossary CSV files
