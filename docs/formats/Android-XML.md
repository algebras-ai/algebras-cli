# Android XML Format Guide

[![Android](https://img.shields.io/badge/Android-3DDC84?style=flat&logo=android&logoColor=white)](https://developer.android.com/)

## Overview

Android XML files are used for storing string resources in Android applications. They follow a specific directory structure with `values/` for the base language and `values-{language}/` for localized versions. Algebras CLI automatically detects and handles this Android-specific structure.

## When to Use Android XML

- **Android Applications**: Native Android apps using string resources
- **Kotlin/Java Projects**: Android projects written in Kotlin or Java
- **React Native**: React Native apps with Android string resources
- **Flutter**: Flutter apps with Android-specific strings
- **Cordova/PhoneGap**: Hybrid mobile apps targeting Android
- **Xamarin**: Xamarin apps with Android string resources

## File Structure

Android projects use a specific directory structure for localization:

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

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "app/src/main/res/values/strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/strings.xml"
  "app/src/main/res/values/app_strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/app_strings.xml"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Standard Android Project:**
```yaml
source_files:
  "app/src/main/res/values/strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/strings.xml"
```

**Multiple String Files:**
```yaml
source_files:
  "app/src/main/res/values/strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/strings.xml"
  "app/src/main/res/values/app_strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/app_strings.xml"
  "app/src/main/res/values/plurals.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/plurals.xml"
```

**React Native with Android:**
```yaml
source_files:
  "android/app/src/main/res/values/strings.xml":
    destination_path: "android/app/src/main/res/values-%algebras_locale_code%/strings.xml"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your Android project directory
cd your-android-project

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

### 1. XML Structure

- **Proper XML formatting**: Use consistent indentation and structure
- **Resource naming**: Use descriptive names for string resources
- **Comments**: Add comments for complex strings
- **CDATA sections**: Use CDATA for strings with special characters

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- App name and basic strings -->
    <string name="app_name">My Android App</string>
    <string name="welcome_message">Welcome to our app!</string>
    
    <!-- Navigation strings -->
    <string name="nav_home">Home</string>
    <string name="nav_settings">Settings</string>
    
    <!-- Strings with special characters -->
    <string name="special_message"><![CDATA[This is a "special" message with <b>HTML</b> tags]]></string>
</resources>
```

### 2. String Naming Conventions

- **Snake case**: Use underscores for multi-word names
- **Descriptive names**: Use clear, descriptive names
- **Hierarchical naming**: Use prefixes for related strings
- **Consistent prefixes**: Use consistent prefixes across files

```xml
<!-- Good naming conventions -->
<string name="user_profile_title">User Profile</string>
<string name="user_profile_edit_button">Edit Profile</string>
<string name="user_profile_save_button">Save Changes</string>

<!-- Avoid generic names -->
<string name="title">User Profile</string>
<string name="button1">Edit Profile</string>
<string name="button2">Save Changes</string>
```

### 3. Pluralization

- **Use plurals.xml**: Create separate files for plural strings
- **Proper quantities**: Use correct quantity attributes
- **Consistent structure**: Keep plural structure consistent across languages

```xml
<!-- plurals.xml -->
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <plurals name="items_count">
        <item quantity="zero">No items</item>
        <item quantity="one">One item</item>
        <item quantity="other">%d items</item>
    </plurals>
    
    <plurals name="messages_count">
        <item quantity="zero">No messages</item>
        <item quantity="one">One message</item>
        <item quantity="other">%d messages</item>
    </plurals>
</resources>
```

### 4. String Formatting

- **String formatting**: Use proper string formatting for dynamic content
- **Escape sequences**: Use proper escape sequences for special characters
- **HTML formatting**: Use HTML tags for text formatting when needed

```xml
<!-- String formatting -->
<string name="welcome_user">Welcome, %1$s!</string>
<string name="item_count">You have %1$d items in your cart</string>
<string name="price_format">Price: $%1$.2f</string>

<!-- HTML formatting -->
<string name="formatted_text">This is <b>bold</b> and <i>italic</i> text</string>
<string name="link_text">Visit our <a href="%1$s">website</a></string>
```

### 5. Accessibility

- **Content descriptions**: Include content descriptions for images
- **Accessibility labels**: Use proper accessibility labels
- **Screen reader support**: Ensure strings work well with screen readers

```xml
<!-- Accessibility strings -->
<string name="button_save_content_description">Save changes</string>
<string name="image_logo_content_description">Company logo</string>
<string name="edit_text_email_hint">Enter your email address</string>
```

## Common Use Cases

### Basic Android App

```xml
<!-- values/strings.xml -->
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">My Android App</string>
    <string name="welcome_message">Welcome to our app!</string>
    <string name="login_button">Log In</string>
    <string name="logout_button">Log Out</string>
    <string name="save_button">Save</string>
    <string name="cancel_button">Cancel</string>
</resources>
```

### E-commerce App

```xml
<!-- values/strings.xml -->
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Shopping App</string>
    <string name="product_title">Product Details</string>
    <string name="add_to_cart">Add to Cart</string>
    <string name="remove_from_cart">Remove from Cart</string>
    <string name="checkout">Checkout</string>
    <string name="total_price">Total: $%1$.2f</string>
</resources>

<!-- values/plurals.xml -->
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <plurals name="cart_items_count">
        <item quantity="zero">Your cart is empty</item>
        <item quantity="one">1 item in cart</item>
        <item quantity="other">%d items in cart</item>
    </plurals>
</resources>
```

### Settings Screen

```xml
<!-- values/strings.xml -->
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="settings_title">Settings</string>
    <string name="settings_notifications">Notifications</string>
    <string name="settings_privacy">Privacy</string>
    <string name="settings_about">About</string>
    <string name="settings_version">Version %1$s</string>
    <string name="settings_language">Language</string>
</resources>
```

## Example Files

### Before Translation (values/strings.xml)
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">My Android App</string>
    <string name="welcome_message">Welcome to our app!</string>
    <string name="login_button">Log In</string>
    <string name="logout_button">Log Out</string>
    <string name="save_button">Save</string>
    <string name="cancel_button">Cancel</string>
    <string name="delete_button">Delete</string>
    <string name="edit_button">Edit</string>
    <string name="user_profile_title">User Profile</string>
    <string name="user_profile_edit_hint">Tap to edit your profile</string>
    <string name="success_message">Operation completed successfully</string>
    <string name="error_message">An error occurred</string>
    <string name="loading_message">Loading...</string>
</resources>
```

### After Translation (values-es/strings.xml)
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Mi Aplicación Android</string>
    <string name="welcome_message">¡Bienvenido a nuestra aplicación!</string>
    <string name="login_button">Iniciar Sesión</string>
    <string name="logout_button">Cerrar Sesión</string>
    <string name="save_button">Guardar</string>
    <string name="cancel_button">Cancelar</string>
    <string name="delete_button">Eliminar</string>
    <string name="edit_button">Editar</string>
    <string name="user_profile_title">Perfil de Usuario</string>
    <string name="user_profile_edit_hint">Toca para editar tu perfil</string>
    <string name="success_message">Operación completada exitosamente</string>
    <string name="error_message">Ocurrió un error</string>
    <string name="loading_message">Cargando...</string>
</resources>
```

## Advanced Features

### 1. String Arrays

```xml
<!-- string-array resources -->
<string-array name="countries">
    <item>United States</item>
    <item>Canada</item>
    <item>Mexico</item>
    <item>United Kingdom</item>
</string-array>
```

### 2. Quantity Strings

```xml
<!-- quantity strings for different quantities -->
<plurals name="items_count">
    <item quantity="zero">No items</item>
    <item quantity="one">One item</item>
    <item quantity="two">Two items</item>
    <item quantity="few">%d items</item>
    <item quantity="many">%d items</item>
    <item quantity="other">%d items</item>
</plurals>
```

### 3. String Formatting with Arguments

```xml
<!-- String formatting with multiple arguments -->
<string name="welcome_user_with_count">Welcome %1$s! You have %2$d messages.</string>
<string name="price_with_currency">Price: %1$s %2$.2f</string>
```

## Troubleshooting

### Common Issues

**XML parsing errors:**
- Ensure valid XML structure
- Check for unclosed tags
- Validate XML before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Save files as UTF-8
- Include proper XML encoding declaration
- Check for BOM (Byte Order Mark)

**Android-specific issues:**
- Ensure proper directory structure
- Check that values directories exist
- Verify language codes match Android standards

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Android Language Codes

Use standard Android language codes:
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `ru` - Russian
- `ja` - Japanese
- `ko` - Korean
- `zh` - Chinese
- `pt` - Portuguese
- `it` - Italian

## Related Examples

- [Android Example](../../examples/android-app/) - Complete Android setup
- [React Native Example](../../examples/react-native-app/) - React Native with Android
- [Flutter Example](../../examples/flutter-app/) - Flutter with Android strings
