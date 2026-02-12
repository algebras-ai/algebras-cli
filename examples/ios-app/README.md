# iOS App Localization Example

This example demonstrates iOS app localization using `.strings` and `.stringsdict` files.

## Directory Structure

```
MyiOSApp/
├── en.lproj/                   # English localization
│   ├── Localizable.strings     # Main app strings
│   ├── Localizable.stringsdict # Plural rules
│   └── InfoPlist.strings       # Info.plist localizations
└── es.lproj/                   # Spanish localization
    ├── Localizable.strings     # Main app strings (Spanish)
    ├── Localizable.stringsdict # Plural rules (Spanish)
    └── InfoPlist.strings       # Info.plist localizations (Spanish)
```

## File Types

### Localizable.strings
The main file for app UI text translations. Format:
```
/* Comment */
"key" = "value";
```

### Localizable.stringsdict
Used for pluralization rules following Unicode CLDR. This allows proper handling of:
- Zero, one, two, few, many, other forms
- Language-specific plural rules
- Variable substitution with proper grammar

### InfoPlist.strings
Localizes Info.plist keys like:
- `CFBundleDisplayName` - App display name
- Privacy permission descriptions (NSCameraUsageDescription, etc.)

## Usage in Swift

```swift
// Load localized string
let welcomeText = NSLocalizedString("welcome_message", comment: "Welcome message")

// Load with default value
let title = NSLocalizedString("settings_title", value: "Settings", comment: "Settings screen title")

// Formatted strings
let greeting = String(format: NSLocalizedString("greeting_user", comment: ""), username)

// Plurals from stringsdict
let itemsText = String.localizedStringWithFormat(
    NSLocalizedString("items_count", comment: ""),
    count
)
```

## Adding New Languages

1. Create a new `.lproj` directory (e.g., `fr.lproj` for French)
2. Copy the `.strings` and `.stringsdict` files from `en.lproj`
3. Translate the values (keep keys unchanged)
4. Add the language to your Xcode project settings

## Best Practices

1. **Always use keys**: Never hardcode user-facing strings in code
2. **Add comments**: Help translators understand context
3. **Use stringsdict for plurals**: Ensures grammatically correct translations
4. **Test with pseudo-localization**: Verify your layout handles long strings
5. **Keep InfoPlist.strings updated**: Essential for privacy permissions

## Common Xcode Integration

1. Add localization in Xcode: Project Settings → Info → Localizations
2. Xcode will create `.lproj` directories automatically
3. Use `genstrings` to extract strings from code:
   ```bash
   find . -name "*.swift" -print0 | xargs -0 genstrings -o en.lproj
   ```

## Notes

- iOS uses ISO 639-1 language codes (e.g., `en`, `es`, `fr`)
- Regional variants use hyphens (e.g., `en-GB`, `es-MX`)
- Base.lproj can be used for development language fallbacks
- Strings files must use UTF-16 encoding for special characters
