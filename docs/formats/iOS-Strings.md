# iOS Strings Format Guide

[![iOS](https://img.shields.io/badge/iOS-000000?style=flat&logo=ios&logoColor=white)](https://developer.apple.com/ios/)

## Overview

iOS Strings files (`.strings`) are used for storing localized strings in iOS applications. They follow a specific directory structure with `.lproj` directories for each language. Algebras CLI automatically detects and handles this iOS-specific structure.

## When to Use iOS Strings

- **iOS Applications**: Native iOS apps using string resources
- **Swift/Objective-C Projects**: iOS projects written in Swift or Objective-C
- **React Native**: React Native apps with iOS string resources
- **Flutter**: Flutter apps with iOS-specific strings
- **Cordova/PhoneGap**: Hybrid mobile apps targeting iOS
- **Xamarin**: Xamarin apps with iOS string resources

## File Structure

iOS projects use a specific directory structure for localization:

```
MyApp/
├── en.lproj/           # English (base language)
│   ├── Localizable.strings
│   ├── Main.strings
│   └── InfoPlist.strings
├── es.lproj/           # Spanish translations
│   ├── Localizable.strings
│   ├── Main.strings
│   └── InfoPlist.strings
├── fr.lproj/           # French translations
│   ├── Localizable.strings
│   ├── Main.strings
│   └── InfoPlist.strings
└── ru.lproj/           # Russian translations
    ├── Localizable.strings
    ├── Main.strings
    └── InfoPlist.strings
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "ios/MyApp/en.lproj/Localizable.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.strings"
  "ios/MyApp/en.lproj/Main.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Main.strings"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Standard iOS Project:**
```yaml
source_files:
  "ios/MyApp/en.lproj/Localizable.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.strings"
```

**Multiple String Files:**
```yaml
source_files:
  "ios/MyApp/en.lproj/Localizable.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.strings"
  "ios/MyApp/en.lproj/Main.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Main.strings"
  "ios/MyApp/en.lproj/InfoPlist.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/InfoPlist.strings"
```

**React Native with iOS:**
```yaml
source_files:
  "ios/MyApp/en.lproj/Localizable.strings":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.strings"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your iOS project directory
cd your-ios-project

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

### 1. Strings File Structure

- **Proper formatting**: Use consistent formatting and structure
- **Key naming**: Use descriptive names for string keys
- **Comments**: Add comments for complex strings
- **Escaping**: Use proper escaping for special characters

```strings
/* App name and basic strings */
"app_name" = "My iOS App";
"welcome_message" = "Welcome to our app!";

/* Navigation strings */
"nav_home" = "Home";
"nav_settings" = "Settings";

/* Strings with special characters */
"special_message" = "This is a \"special\" message with <b>HTML</b> tags";
```

### 2. Key Naming Conventions

- **Snake case**: Use underscores for multi-word names
- **Descriptive names**: Use clear, descriptive names
- **Hierarchical naming**: Use prefixes for related strings
- **Consistent prefixes**: Use consistent prefixes across files

```strings
/* Good naming conventions */
"user_profile_title" = "User Profile";
"user_profile_edit_button" = "Edit Profile";
"user_profile_save_button" = "Save Changes";

/* Avoid generic names */
"title" = "User Profile";
"button1" = "Edit Profile";
"button2" = "Save Changes";
```

### 3. String Formatting

- **String formatting**: Use proper string formatting for dynamic content
- **Escape sequences**: Use proper escape sequences for special characters
- **HTML formatting**: Use HTML tags for text formatting when needed

```strings
/* String formatting */
"welcome_user" = "Welcome, %@!";
"item_count" = "You have %d items in your cart";
"price_format" = "Price: $%.2f";

/* HTML formatting */
"formatted_text" = "This is <b>bold</b> and <i>italic</i> text";
"link_text" = "Visit our <a href=\"%@\">website</a>";
```

### 4. Accessibility

- **Accessibility labels**: Include accessibility labels for UI elements
- **VoiceOver support**: Ensure strings work well with VoiceOver
- **Screen reader support**: Use proper accessibility terminology

```strings
/* Accessibility strings */
"button_save_accessibility_label" = "Save changes";
"image_logo_accessibility_label" = "Company logo";
"edit_text_email_placeholder" = "Enter your email address";
```

### 5. Localization Comments

- **Developer comments**: Add comments for developers
- **Translator notes**: Add notes for translators
- **Context information**: Provide context for complex strings

```strings
/* 
   This string is used in the login screen
   It should be friendly and welcoming
   Maximum length: 50 characters
 */
"login_welcome_message" = "Welcome! Please sign in to continue";

/* 
   This string is used for the delete confirmation dialog
   It should be clear about the action being performed
 */
"delete_confirmation_message" = "Are you sure you want to delete this item?";
```

## Common Use Cases

### Basic iOS App

```strings
/* Localizable.strings */
"app_name" = "My iOS App";
"welcome_message" = "Welcome to our app!";
"login_button" = "Log In";
"logout_button" = "Log Out";
"save_button" = "Save";
"cancel_button" = "Cancel";
```

### E-commerce App

```strings
/* Localizable.strings */
"app_name" = "Shopping App";
"product_title" = "Product Details";
"add_to_cart" = "Add to Cart";
"remove_from_cart" = "Remove from Cart";
"checkout" = "Checkout";
"total_price" = "Total: $%.2f";
"cart_items_count" = "You have %d items in your cart";
```

### Settings Screen

```strings
/* Localizable.strings */
"settings_title" = "Settings";
"settings_notifications" = "Notifications";
"settings_privacy" = "Privacy";
"settings_about" = "About";
"settings_version" = "Version %@";
"settings_language" = "Language";
```

### Main.strings (Interface Builder)

```strings
/* Main.strings - Interface Builder strings */
"UIBarButtonItem.title" = "Save";
"UIButton.title" = "Login";
"UILabel.text" = "Welcome to our app!";
"UITextField.placeholder" = "Enter your email";
```

### InfoPlist.strings (App Info)

```strings
/* InfoPlist.strings - App information strings */
"CFBundleDisplayName" = "My App";
"CFBundleName" = "My App";
"NSHumanReadableCopyright" = "Copyright © 2024 My Company. All rights reserved.";
```

## Example Files

### Before Translation (en.lproj/Localizable.strings)
```strings
/* 
  Localizable.strings
  My iOS App
  
  Created by Developer on 2024-01-01.
  Copyright © 2024 My Company. All rights reserved.
*/

/* App name and basic strings */
"app_name" = "My iOS App";
"welcome_message" = "Welcome to our app!";
"login_button" = "Log In";
"logout_button" = "Log Out";
"save_button" = "Save";
"cancel_button" = "Cancel";
"delete_button" = "Delete";
"edit_button" = "Edit";

/* User profile strings */
"user_profile_title" = "User Profile";
"user_profile_edit_hint" = "Tap to edit your profile";
"user_profile_save_changes" = "Save Changes";
"user_profile_cancel_changes" = "Cancel Changes";

/* Messages */
"success_message" = "Operation completed successfully";
"error_message" = "An error occurred";
"loading_message" = "Loading...";
"confirm_message" = "Are you sure?";
```

### After Translation (es.lproj/Localizable.strings)
```strings
/* 
  Localizable.strings
  My iOS App
  
  Created by Developer on 2024-01-01.
  Copyright © 2024 My Company. All rights reserved.
*/

/* App name and basic strings */
"app_name" = "Mi Aplicación iOS";
"welcome_message" = "¡Bienvenido a nuestra aplicación!";
"login_button" = "Iniciar Sesión";
"logout_button" = "Cerrar Sesión";
"save_button" = "Guardar";
"cancel_button" = "Cancelar";
"delete_button" = "Eliminar";
"edit_button" = "Editar";

/* User profile strings */
"user_profile_title" = "Perfil de Usuario";
"user_profile_edit_hint" = "Toca para editar tu perfil";
"user_profile_save_changes" = "Guardar Cambios";
"user_profile_cancel_changes" = "Cancelar Cambios";

/* Messages */
"success_message" = "Operación completada exitosamente";
"error_message" = "Ocurrió un error";
"loading_message" = "Cargando...";
"confirm_message" = "¿Estás seguro?";
```

## Advanced Features

### 1. String Formatting with Arguments

```strings
/* String formatting with multiple arguments */
"welcome_user_with_count" = "Welcome %@! You have %d messages.";
"price_with_currency" = "Price: %@ %.2f";
"date_range" = "From %@ to %@";
```

### 2. Pluralization Support

```strings
/* Pluralization strings */
"items_count_zero" = "No items";
"items_count_one" = "One item";
"items_count_other" = "%d items";

"messages_count_zero" = "No messages";
"messages_count_one" = "One message";
"messages_count_other" = "%d messages";
```

### 3. HTML Formatting

```strings
/* HTML formatted strings */
"formatted_text" = "This is <b>bold</b> and <i>italic</i> text";
"link_text" = "Visit our <a href=\"%@\">website</a>";
"colored_text" = "This is <span style=\"color: red;\">red</span> text";
```

## Troubleshooting

### Common Issues

**Strings file parsing errors:**
- Ensure valid strings file format
- Check for proper semicolons at end of lines
- Validate strings file structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Save files as UTF-8
- Check for BOM (Byte Order Mark)
- Verify special characters are properly encoded

**iOS-specific issues:**
- Ensure proper directory structure
- Check that .lproj directories exist
- Verify language codes match iOS standards

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## iOS Language Codes

Use standard iOS language codes:
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `ru` - Russian
- `ja` - Japanese
- `ko` - Korean
- `zh-Hans` - Chinese (Simplified)
- `zh-Hant` - Chinese (Traditional)
- `pt` - Portuguese
- `it` - Italian

## Related Examples

- [iOS Example](../../examples/ios-app/) - Complete iOS setup
- [React Native Example](../../examples/react-native-app/) - React Native with iOS
- [Flutter Example](../../examples/flutter-app/) - Flutter with iOS strings
