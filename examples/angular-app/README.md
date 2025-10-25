# Angular App Example

This example demonstrates how to use algebras-cli with Angular XLIFF (XML Localization Interchange File Format) files.

## Project Structure

```
angular-app/
├── translations/
│   ├── messages.en.xlf         # English source file
│   ├── messages.de.xlf         # German translation (generated)
│   ├── messages.fr.xlf         # French translation (generated)
│   └── messages.es.xlf         # Spanish translation (generated)
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

## XLIFF File Format

XLIFF is a standard XML format for localization files. It supports:

- **Translation units**: Each `<trans-unit>` contains source and target text
- **Metadata**: File-level and unit-level attributes
- **Context**: Additional context information for translators

## Example XLIFF Content

```xml
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="messages" source-language="en" target-language="en" datatype="plaintext">
    <body>
      <trans-unit id="app.title">
        <source>My Angular App</source>
        <target>My Angular App</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

## Angular Integration

In your Angular app, you would typically use these XLIFF files with the `@angular/localize` package for internationalization.

## Supported Features

- ✅ XLIFF file reading and writing
- ✅ Source and target element handling
- ✅ Batch translation
- ✅ UI-safe translations
- ✅ Glossary support
