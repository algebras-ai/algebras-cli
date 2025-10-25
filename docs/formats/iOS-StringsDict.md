# iOS StringsDict Format Guide

[![iOS](https://img.shields.io/badge/iOS-000000?style=flat&logo=ios&logoColor=white)](https://developer.apple.com/ios/)

## Overview

iOS StringsDict files (`.stringsdict`) are used for storing localized strings with pluralization rules in iOS applications. They provide more sophisticated pluralization support than regular `.strings` files and are essential for proper localization in languages with complex plural rules.

## When to Use iOS StringsDict

- **iOS Applications**: Native iOS apps requiring advanced pluralization
- **Pluralization Support**: When you need proper plural forms for different languages
- **Complex Plural Rules**: Languages with multiple plural forms (e.g., Polish, Russian)
- **Quantity Strings**: When displaying counts, quantities, or measurements
- **Swift/Objective-C Projects**: iOS projects written in Swift or Objective-C
- **React Native**: React Native apps with iOS pluralization support

## File Structure

iOS projects use a specific directory structure for StringsDict files:

```
MyApp/
├── en.lproj/           # English (base language)
│   ├── Localizable.strings
│   ├── Localizable.stringsdict
│   └── Main.stringsdict
├── es.lproj/           # Spanish translations
│   ├── Localizable.strings
│   ├── Localizable.stringsdict
│   └── Main.stringsdict
├── fr.lproj/           # French translations
│   ├── Localizable.strings
│   ├── Localizable.stringsdict
│   └── Main.stringsdict
└── ru.lproj/           # Russian translations
    ├── Localizable.strings
    ├── Localizable.stringsdict
    └── Main.stringsdict
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "ios/MyApp/en.lproj/Localizable.stringsdict":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.stringsdict"
  "ios/MyApp/en.lproj/Main.stringsdict":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Main.stringsdict"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Standard iOS Project:**
```yaml
source_files:
  "ios/MyApp/en.lproj/Localizable.stringsdict":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.stringsdict"
```

**Multiple StringsDict Files:**
```yaml
source_files:
  "ios/MyApp/en.lproj/Localizable.stringsdict":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.stringsdict"
  "ios/MyApp/en.lproj/Main.stringsdict":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Main.stringsdict"
```

**React Native with iOS:**
```yaml
source_files:
  "ios/MyApp/en.lproj/Localizable.stringsdict":
    destination_path: "ios/MyApp/%algebras_locale_code%.lproj/Localizable.stringsdict"
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

### 1. StringsDict Structure

- **Proper XML formatting**: Use consistent formatting and structure
- **Key naming**: Use descriptive names for string keys
- **Comments**: Add comments for complex pluralization rules
- **Quantity rules**: Use proper quantity attributes

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>No items</string>
            <key>one</key>
            <string>One item</string>
            <key>other</key>
            <string>%d items</string>
        </dict>
    </dict>
</dict>
</plist>
```

### 2. Key Naming Conventions

- **Snake case**: Use underscores for multi-word names
- **Descriptive names**: Use clear, descriptive names
- **Quantity indicators**: Use names that indicate quantity/pluralization
- **Consistent prefixes**: Use consistent prefixes across files

```xml
<!-- Good naming conventions -->
<key>user_messages_count</key>
<key>cart_items_count</key>
<key>unread_notifications_count</key>

<!-- Avoid generic names -->
<key>count1</key>
<key>count2</key>
<key>count3</key>
```

### 3. Pluralization Rules

- **Zero quantity**: Handle zero items appropriately
- **One quantity**: Handle single items
- **Other quantities**: Handle multiple items
- **Language-specific rules**: Consider language-specific plural rules

```xml
<!-- English pluralization rules -->
<key>items_count</key>
<dict>
    <key>NSStringLocalizedFormatKey</key>
    <string>%#@count@</string>
    <key>count</key>
    <dict>
        <key>NSStringFormatSpecTypeKey</key>
        <string>NSStringPluralRuleType</string>
        <key>NSStringFormatValueTypeKey</key>
        <string>d</string>
        <key>zero</key>
        <string>No items</string>
        <key>one</key>
        <string>One item</string>
        <key>other</key>
        <string>%d items</string>
    </dict>
</dict>
```

### 4. Complex Pluralization

- **Multiple variables**: Handle multiple variables in pluralization
- **Nested rules**: Use nested rules for complex scenarios
- **Context-aware**: Consider context when defining plural rules

```xml
<!-- Complex pluralization with multiple variables -->
<key>user_items_count</key>
<dict>
    <key>NSStringLocalizedFormatKey</key>
    <string>%#@user@ has %#@count@</string>
    <key>user</key>
    <dict>
        <key>NSStringFormatSpecTypeKey</key>
        <string>NSStringPluralRuleType</string>
        <key>NSStringFormatValueTypeKey</key>
        <string>@</string>
        <key>one</key>
        <string>%@</string>
        <key>other</key>
        <string>%@</string>
    </dict>
    <key>count</key>
    <dict>
        <key>NSStringFormatSpecTypeKey</key>
        <string>NSStringPluralRuleType</string>
        <key>NSStringFormatValueTypeKey</key>
        <string>d</string>
        <key>zero</key>
        <string>no items</string>
        <key>one</key>
        <string>one item</string>
        <key>other</key>
        <string>%d items</string>
    </dict>
</dict>
```

### 5. Language-Specific Rules

- **Polish**: 5 plural forms (zero, one, few, many, other)
- **Russian**: 4 plural forms (one, few, many, other)
- **Arabic**: 6 plural forms (zero, one, two, few, many, other)
- **English**: 2 plural forms (one, other)

```xml
<!-- Polish pluralization rules -->
<key>items_count</key>
<dict>
    <key>NSStringLocalizedFormatKey</key>
    <string>%#@count@</string>
    <key>count</key>
    <dict>
        <key>NSStringFormatSpecTypeKey</key>
        <string>NSStringPluralRuleType</string>
        <key>NSStringFormatValueTypeKey</key>
        <string>d</string>
        <key>zero</key>
        <string>Brak elementów</string>
        <key>one</key>
        <string>Jeden element</string>
        <key>few</key>
        <string>%d elementy</string>
        <key>many</key>
        <string>%d elementów</string>
        <key>other</key>
        <string>%d elementów</string>
    </dict>
</dict>
```

## Common Use Cases

### Basic Item Count

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>No items</string>
            <key>one</key>
            <string>One item</string>
            <key>other</key>
            <string>%d items</string>
        </dict>
    </dict>
</dict>
</plist>
```

### E-commerce Cart

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>cart_items_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@ in cart</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>No items in cart</string>
            <key>one</key>
            <string>One item in cart</string>
            <key>other</key>
            <string>%d items in cart</string>
        </dict>
    </dict>
    
    <key>cart_total_price</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>Total: $%#@price@</string>
        <key>price</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>@</string>
            <key>one</key>
            <string>%.2f</string>
            <key>other</key>
            <string>%.2f</string>
        </dict>
    </dict>
</dict>
</plist>
```

### User Messages

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>user_messages_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@user@ has %#@count@</string>
        <key>user</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>@</string>
            <key>one</key>
            <string>%@</string>
            <key>other</key>
            <string>%@</string>
        </dict>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>no messages</string>
            <key>one</key>
            <string>one message</string>
            <key>other</key>
            <string>%d messages</string>
        </dict>
    </dict>
</dict>
</plist>
```

## Example Files

### Before Translation (en.lproj/Localizable.stringsdict)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>No items</string>
            <key>one</key>
            <string>One item</string>
            <key>other</key>
            <string>%d items</string>
        </dict>
    </dict>
    
    <key>messages_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>No messages</string>
            <key>one</key>
            <string>One message</string>
            <key>other</key>
            <string>%d messages</string>
        </dict>
    </dict>
    
    <key>users_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>No users</string>
            <key>one</key>
            <string>One user</string>
            <key>other</key>
            <string>%d users</string>
        </dict>
    </dict>
</dict>
</plist>
```

### After Translation (es.lproj/Localizable.stringsdict)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>Sin elementos</string>
            <key>one</key>
            <string>Un elemento</string>
            <key>other</key>
            <string>%d elementos</string>
        </dict>
    </dict>
    
    <key>messages_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>Sin mensajes</string>
            <key>one</key>
            <string>Un mensaje</string>
            <key>other</key>
            <string>%d mensajes</string>
        </dict>
    </dict>
    
    <key>users_count</key>
    <dict>
        <key>NSStringLocalizedFormatKey</key>
        <string>%#@count@</string>
        <key>count</key>
        <dict>
            <key>NSStringFormatSpecTypeKey</key>
            <string>NSStringPluralRuleType</string>
            <key>NSStringFormatValueTypeKey</key>
            <string>d</string>
            <key>zero</key>
            <string>Sin usuarios</string>
            <key>one</key>
            <string>Un usuario</string>
            <key>other</key>
            <string>%d usuarios</string>
        </dict>
    </dict>
</dict>
</plist>
```

## Troubleshooting

### Common Issues

**StringsDict parsing errors:**
- Ensure valid XML structure
- Check for proper plist format
- Validate XML before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Pluralization issues:**
- Verify quantity rules are correct
- Check language-specific plural rules
- Ensure proper format specifiers

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
