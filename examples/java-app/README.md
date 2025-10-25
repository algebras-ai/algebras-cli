# Java App Example

This example demonstrates how to use algebras-cli with Java Properties files for internationalization.

## Project Structure

```
java-app/
├── src/
│   └── main/
│       └── resources/
│           ├── messages_en.properties    # English source file
│           ├── messages_de.properties    # German translation (generated)
│           ├── messages_fr.properties    # French translation (generated)
│           └── messages_es.properties    # Spanish translation (generated)
├── .algebras.config                      # Algebras configuration
└── README.md                             # This file
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

## Properties File Format

Java Properties files use a simple key=value format with support for:

- **Unicode escaping**: \uXXXX format for special characters
- **Line continuation**: Using backslash at end of line
- **Comments**: Lines starting with # or !
- **Special character escaping**: For =, :, spaces, etc.

## Example Properties Content

```properties
# English messages for Java application
app.title=My Java Application
welcome.message=Welcome to our amazing Java application!
login.button=Log In
error.message=Something went wrong. Please try again.
```

## Java Integration

In your Java application, you would typically use these properties files with `ResourceBundle` for internationalization:

```java
ResourceBundle messages = ResourceBundle.getBundle("messages", locale);
String title = messages.getString("app.title");
```

## Supported Features

- ✅ Properties file reading and writing
- ✅ Unicode escaping support
- ✅ Special character handling
- ✅ Batch translation
- ✅ UI-safe translations
- ✅ Glossary support
