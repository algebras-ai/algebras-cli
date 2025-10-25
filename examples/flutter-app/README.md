# Flutter App Example

This example demonstrates how to use algebras-cli with Flutter ARB (Application Resource Bundle) files.

## Project Structure

```
flutter-app/
├── lib/
│   └── l10n/
│       ├── app_en.arb          # English source file
│       ├── app_de.arb          # German translation (generated)
│       ├── app_fr.arb          # French translation (generated)
│       └── app_es.arb          # Spanish translation (generated)
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

## ARB File Format

ARB files are JSON-based localization files used by Flutter. They support:

- **Translatable strings**: Regular key-value pairs
- **Metadata**: Keys prefixed with `@` for descriptions and context
- **Pluralization**: Complex plural forms (not shown in this simple example)

## Example ARB Content

```json
{
  "@@locale": "en",
  "appTitle": "My Flutter App",
  "@appTitle": {
    "description": "The title of the application"
  },
  "welcomeMessage": "Welcome to our amazing app!",
  "@welcomeMessage": {
    "description": "A welcome message shown to users"
  }
}
```

## Flutter Integration

In your Flutter app, you would typically use these ARB files with the `flutter_localizations` package and `intl` package for internationalization.

## Supported Features

- ✅ ARB file reading and writing
- ✅ Metadata preservation (@-prefixed keys)
- ✅ Batch translation
- ✅ UI-safe translations
- ✅ Glossary support
