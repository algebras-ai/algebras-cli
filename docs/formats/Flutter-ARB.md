# Flutter ARB Format Guide

[![Flutter](https://img.shields.io/badge/Flutter-02569B?style=flat&logo=flutter&logoColor=white)](https://flutter.dev/)

## Overview

ARB (Application Resource Bundle) files are the standard format for Flutter internationalization. They are JSON-based files that store localized strings with metadata for Flutter's i18n system. ARB files support pluralization, parameterization, and other advanced localization features.

## When to Use Flutter ARB

- **Flutter Applications**: Native Flutter apps using internationalization
- **Dart Projects**: Any Dart project requiring localization
- **Cross-platform Apps**: Flutter apps targeting multiple platforms
- **Pluralization Support**: When you need advanced pluralization rules
- **Parameterized Strings**: When using string interpolation and parameters
- **Metadata Support**: When you need to store additional translation metadata

## File Structure

Flutter projects use a specific directory structure for ARB files:

```
lib/
├── l10n/              # Localization directory
│   ├── app_en.arb     # English (base language)
│   ├── app_es.arb     # Spanish translations
│   ├── app_fr.arb     # French translations
│   └── app_ru.arb     # Russian translations
└── main.dart
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "lib/l10n/app_en.arb":
    destination_path: "lib/l10n/app_%algebras_locale_code%.arb"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Standard Flutter Project:**
```yaml
source_files:
  "lib/l10n/app_en.arb":
    destination_path: "lib/l10n/app_%algebras_locale_code%.arb"
```

**Multiple ARB Files:**
```yaml
source_files:
  "lib/l10n/app_en.arb":
    destination_path: "lib/l10n/app_%algebras_locale_code%.arb"
  "lib/l10n/messages_en.arb":
    destination_path: "lib/l10n/messages_%algebras_locale_code%.arb"
```

**Custom Localization Directory:**
```yaml
source_files:
  "assets/locales/app_en.arb":
    destination_path: "assets/locales/app_%algebras_locale_code%.arb"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your Flutter project directory
cd your-flutter-project

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

### 1. ARB File Structure

- **Proper JSON formatting**: Use consistent formatting and structure
- **Key naming**: Use descriptive names for string keys
- **Metadata**: Include proper metadata for Flutter i18n
- **Comments**: Add comments for complex strings

```json
{
  "appTitle": "My Flutter App",
  "@appTitle": {
    "description": "The title of the application"
  },
  "welcomeMessage": "Welcome to our app!",
  "@welcomeMessage": {
    "description": "Welcome message displayed on the home screen"
  },
  "loginButton": "Log In",
  "@loginButton": {
    "description": "Text for the login button"
  }
}
```

### 2. Key Naming Conventions

- **CamelCase**: Use camelCase for multi-word names
- **Descriptive names**: Use clear, descriptive names
- **Hierarchical naming**: Use prefixes for related strings
- **Consistent prefixes**: Use consistent prefixes across files

```json
{
  "userProfileTitle": "User Profile",
  "userProfileEditButton": "Edit Profile",
  "userProfileSaveButton": "Save Changes",
  "userProfileCancelButton": "Cancel Changes"
}
```

### 3. String Parameterization

- **Placeholder format**: Use `{parameterName}` for parameters
- **Type hints**: Include type information in metadata
- **Consistent naming**: Use consistent parameter names

```json
{
  "welcomeUser": "Welcome, {userName}!",
  "@welcomeUser": {
    "description": "Welcome message with user name",
    "placeholders": {
      "userName": {
        "type": "String",
        "description": "The name of the user"
      }
    }
  },
  "itemCount": "You have {count} items",
  "@itemCount": {
    "description": "Item count message",
    "placeholders": {
      "count": {
        "type": "int",
        "description": "The number of items"
      }
    }
  }
}
```

### 4. Pluralization Support

- **Plural forms**: Use proper plural forms for different quantities
- **Quantity rules**: Include quantity rules in metadata
- **Language-specific rules**: Consider language-specific plural rules

```json
{
  "itemsCount": "{count, plural, =0{No items} =1{One item} other{{count} items}}",
  "@itemsCount": {
    "description": "Item count with pluralization",
    "placeholders": {
      "count": {
        "type": "int",
        "description": "The number of items"
      }
    }
  }
}
```

### 5. Metadata and Documentation

- **Description**: Include descriptions for all strings
- **Context**: Provide context for complex strings
- **Placeholder documentation**: Document all placeholders
- **Usage examples**: Include usage examples when helpful

```json
{
  "deleteConfirmation": "Are you sure you want to delete {itemName}?",
  "@deleteConfirmation": {
    "description": "Confirmation dialog for deleting an item",
    "placeholders": {
      "itemName": {
        "type": "String",
        "description": "The name of the item to be deleted"
      }
    }
  }
}
```

## Common Use Cases

### Basic Flutter App

```json
{
  "appTitle": "My Flutter App",
  "@appTitle": {
    "description": "The title of the application"
  },
  "welcomeMessage": "Welcome to our app!",
  "@welcomeMessage": {
    "description": "Welcome message displayed on the home screen"
  },
  "loginButton": "Log In",
  "@loginButton": {
    "description": "Text for the login button"
  },
  "logoutButton": "Log Out",
  "@logoutButton": {
    "description": "Text for the logout button"
  }
}
```

### E-commerce App

```json
{
  "appTitle": "Shopping App",
  "@appTitle": {
    "description": "The title of the shopping application"
  },
  "productTitle": "Product Details",
  "@productTitle": {
    "description": "Title for product details screen"
  },
  "addToCart": "Add to Cart",
  "@addToCart": {
    "description": "Button text for adding item to cart"
  },
  "cartItemsCount": "{count, plural, =0{Your cart is empty} =1{1 item in cart} other{{count} items in cart}}",
  "@cartItemsCount": {
    "description": "Cart item count with pluralization",
    "placeholders": {
      "count": {
        "type": "int",
        "description": "The number of items in the cart"
      }
    }
  },
  "totalPrice": "Total: \${price}",
  "@totalPrice": {
    "description": "Total price display",
    "placeholders": {
      "price": {
        "type": "String",
        "description": "The formatted price"
      }
    }
  }
}
```

### User Profile

```json
{
  "userProfileTitle": "User Profile",
  "@userProfileTitle": {
    "description": "Title for user profile screen"
  },
  "editProfile": "Edit Profile",
  "@editProfile": {
    "description": "Button text for editing profile"
  },
  "saveChanges": "Save Changes",
  "@saveChanges": {
    "description": "Button text for saving changes"
  },
  "cancelChanges": "Cancel Changes",
  "@cancelChanges": {
    "description": "Button text for canceling changes"
  },
  "profileUpdated": "Profile updated successfully",
  "@profileUpdated": {
    "description": "Success message when profile is updated"
  }
}
```

## Example Files

### Before Translation (app_en.arb)
```json
{
  "appTitle": "My Flutter App",
  "@appTitle": {
    "description": "The title of the application"
  },
  "welcomeMessage": "Welcome to our app!",
  "@welcomeMessage": {
    "description": "Welcome message displayed on the home screen"
  },
  "loginButton": "Log In",
  "@loginButton": {
    "description": "Text for the login button"
  },
  "logoutButton": "Log Out",
  "@logoutButton": {
    "description": "Text for the logout button"
  },
  "saveButton": "Save",
  "@saveButton": {
    "description": "Text for the save button"
  },
  "cancelButton": "Cancel",
  "@cancelButton": {
    "description": "Text for the cancel button"
  },
  "deleteButton": "Delete",
  "@deleteButton": {
    "description": "Text for the delete button"
  },
  "editButton": "Edit",
  "@editButton": {
    "description": "Text for the edit button"
  },
  "userProfileTitle": "User Profile",
  "@userProfileTitle": {
    "description": "Title for user profile screen"
  },
  "userProfileEditHint": "Tap to edit your profile",
  "@userProfileEditHint": {
    "description": "Hint text for editing profile"
  },
  "successMessage": "Operation completed successfully",
  "@successMessage": {
    "description": "Success message for completed operations"
  },
  "errorMessage": "An error occurred",
  "@errorMessage": {
    "description": "Error message for failed operations"
  },
  "loadingMessage": "Loading...",
  "@loadingMessage": {
    "description": "Loading indicator text"
  }
}
```

### After Translation (app_es.arb)
```json
{
  "appTitle": "Mi Aplicación Flutter",
  "@appTitle": {
    "description": "The title of the application"
  },
  "welcomeMessage": "¡Bienvenido a nuestra aplicación!",
  "@welcomeMessage": {
    "description": "Welcome message displayed on the home screen"
  },
  "loginButton": "Iniciar Sesión",
  "@loginButton": {
    "description": "Text for the login button"
  },
  "logoutButton": "Cerrar Sesión",
  "@logoutButton": {
    "description": "Text for the logout button"
  },
  "saveButton": "Guardar",
  "@saveButton": {
    "description": "Text for the save button"
  },
  "cancelButton": "Cancelar",
  "@cancelButton": {
    "description": "Text for the cancel button"
  },
  "deleteButton": "Eliminar",
  "@deleteButton": {
    "description": "Text for the delete button"
  },
  "editButton": "Editar",
  "@editButton": {
    "description": "Text for the edit button"
  },
  "userProfileTitle": "Perfil de Usuario",
  "@userProfileTitle": {
    "description": "Title for user profile screen"
  },
  "userProfileEditHint": "Toca para editar tu perfil",
  "@userProfileEditHint": {
    "description": "Hint text for editing profile"
  },
  "successMessage": "Operación completada exitosamente",
  "@successMessage": {
    "description": "Success message for completed operations"
  },
  "errorMessage": "Ocurrió un error",
  "@errorMessage": {
    "description": "Error message for failed operations"
  },
  "loadingMessage": "Cargando...",
  "@loadingMessage": {
    "description": "Loading indicator text"
  }
}
```

## Advanced Features

### 1. Complex Pluralization

```json
{
  "itemsCount": "{count, plural, =0{No items} =1{One item} =2{Two items} few{{count} items} many{{count} items} other{{count} items}}",
  "@itemsCount": {
    "description": "Item count with complex pluralization",
    "placeholders": {
      "count": {
        "type": "int",
        "description": "The number of items"
      }
    }
  }
}
```

### 2. Multiple Parameters

```json
{
  "userItemsCount": "{userName} has {count, plural, =0{no items} =1{one item} other{{count} items}}",
  "@userItemsCount": {
    "description": "User item count with pluralization",
    "placeholders": {
      "userName": {
        "type": "String",
        "description": "The name of the user"
      },
      "count": {
        "type": "int",
        "description": "The number of items"
      }
    }
  }
}
```

### 3. Date and Time Formatting

```json
{
  "lastUpdated": "Last updated: {date}",
  "@lastUpdated": {
    "description": "Last updated message with date",
    "placeholders": {
      "date": {
        "type": "DateTime",
        "description": "The date when last updated"
      }
    }
  }
}
```

## Troubleshooting

### Common Issues

**ARB parsing errors:**
- Ensure valid JSON structure
- Check for proper metadata format
- Validate ARB file structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Pluralization issues:**
- Verify plural rules are correct
- Check language-specific plural rules
- Ensure proper format specifiers

**Metadata issues:**
- Ensure metadata is properly formatted
- Check that placeholders are documented
- Verify type information is correct

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Flutter Integration

### pubspec.yaml Configuration

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter

flutter:
  generate: true
```

### l10n.yaml Configuration

```yaml
arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
```

### Usage in Flutter Code

```dart
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_gen/gen_l10n/app_localizations.dart';

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: MyHomePage(),
    );
  }
}

class MyHomePage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.appTitle),
      ),
      body: Center(
        child: Column(
          children: [
            Text(l10n.welcomeMessage),
            ElevatedButton(
              onPressed: () {},
              child: Text(l10n.loginButton),
            ),
          ],
        ),
      ),
    );
  }
}
```

## Related Examples

- [Flutter Example](../../examples/flutter-app/) - Complete Flutter setup
- [Flutter ARB Example](../../examples/flutter-arb/) - Flutter ARB specific example
- [Cross-platform Example](../../examples/cross-platform-app/) - Multi-platform Flutter app
