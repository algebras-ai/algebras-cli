# Android App Example

This example demonstrates how to use Algebras CLI with an Android project that follows the standard Android localization structure.

## Android Project Structure

Android projects typically use the following directory structure for localization:

```
app/src/main/res/
├── values/           # Base language files (usually English)
│   ├── strings.xml
│   ├── app_strings.xml
│   └── plurals.xml
├── values-es/        # Spanish translations
│   ├── strings.xml
│   ├── app_strings.xml
│   └── plurals.xml
├── values-fr/        # French translations
│   ├── strings.xml
│   ├── app_strings.xml
│   └── plurals.xml
└── values-ru/        # Russian translations
    ├── strings.xml
    ├── app_strings.xml
    └── plurals.xml
```

## How Algebras CLI Handles Android Projects

### Base Language Detection
- Files in `values/` directories are automatically detected as base language files
- The base language is determined by the first language in your configuration
- Filenames are preserved exactly when creating translations

### Translation Organization
- Translated files are organized in `values-{lang}/` directories
- Example: `values/strings.xml` → `values-es/strings.xml` for Spanish
- Supports nested subdirectories: `app/src/main/res/values/` → `app/src/main/res/values-{lang}/`

### Priority Handling
- Android values pattern takes priority over other naming patterns
- If you have both `values/strings.xml` and `strings.en.xml`, the Android pattern is used
- Only `.xml` files in values directories get Android-specific treatment

## Configuration

Create a `.algebras.config` file in your project root:

```json
{
  "languages": ["en", "es", "fr", "ru"],
  "path_rules": [
    "**/*.xml",
    "!**/build/**",
    "!**/node_modules/**"
  ],
  "api": {
    "provider": "algebras-ai",
    "normalize_strings": true
  }
}
```

## Usage Examples

### Initialize the project
```bash
algebras init
```

### Translate all missing keys
```bash
algebras translate
```

### Translate specific language
```bash
algebras translate --language es
```

### Check translation status
```bash
algebras status
```

## Example XML Files

### Base Language (`values/strings.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">My Android App</string>
    <string name="welcome_message">Welcome to our app!</string>
    <string name="login_button">Log In</string>
    
    <plurals name="items_count">
        <item quantity="zero">No items</item>
        <item quantity="one">One item</item>
        <item quantity="other">%d items</item>
    </plurals>
</resources>
```

### Spanish Translation (`values-es/strings.xml`)
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Mi App Android</string>
    <string name="welcome_message">¡Bienvenido a nuestra app!</string>
    <string name="login_button">Iniciar Sesión</string>
    
    <plurals name="items_count">
        <item quantity="zero">Sin elementos</item>
        <item quantity="one">Un elemento</item>
        <item quantity="other">%d elementos</item>
    </plurals>
</resources>
```

## Benefits

1. **Automatic Detection**: Base language files in `values/` are automatically recognized
2. **Standard Structure**: Follows Android's standard localization conventions
3. **Filename Preservation**: Original filenames are maintained across all languages
4. **Nested Support**: Works with any depth of subdirectories
5. **Priority Handling**: Android pattern takes precedence over other naming schemes
