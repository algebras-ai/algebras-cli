# In-Place Updates Example

This example demonstrates how Algebras CLI updates translation files in-place, preserving structure, formatting, comments, and HTML entities.

## Overview

When translating with `--only-missing`, Algebras CLI by default updates existing target files in-place rather than regenerating them from scratch. This preserves:

- **File structure and formatting**
- **Comments and metadata**
- **Element order**
- **HTML entities** (like `&#160;` for non-breaking spaces)

## Example: Android XML

### Before Translation

**Source file** (`values/generic_strings.xml`):
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="Auth.eula">user&#160;agreement</string>
    <string name="Auth.privacy_policy">privacy&#160;policy</string>
    <string name="Auth.sign_in_with">Sign in with %1$s</string>
</resources>
```

**Target file** (`values-it/generic_strings.xml`):
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="Auth.sign_in_with">Accedi con %1$s</string>
    <!-- Note: Auth.eula and Auth.privacy_policy are missing -->
</resources>
```

### After Translation (In-Place Update)

Running `algebras translate --only-missing --language it` updates only the missing keys:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="Auth.sign_in_with">Accedi con %1$s</string>
    <!-- Note: Auth.eula and Auth.privacy_policy are missing -->
    <string name="Auth.eula">termini&#160;di&#160;utilizzo</string>
    <string name="Auth.privacy_policy">informativa&#160;sulla&#160;privacy</string>
</resources>
```

**Key features preserved:**
- ✅ Existing translation (`Auth.sign_in_with`) remains unchanged
- ✅ Comment preserved
- ✅ HTML entities (`&#160;`) preserved in new translations
- ✅ New keys added at the end

### After Translation (Regenerate from Scratch)

Running `algebras translate --only-missing --language it --regenerate-from-scratch` regenerates the entire file:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="Auth.eula">termini di utilizzo</string>
    <string name="Auth.privacy_policy">informativa sulla privacy</string>
    <string name="Auth.sign_in_with">Accedi con %1$s</string>
</resources>
```

**Note:** The file is regenerated with keys sorted alphabetically, and comments are lost.

## Command Examples

### Update in-place (default)
```bash
# Update only missing keys, preserving file structure
algebras translate --only-missing --language it
```

### Force regenerate from scratch
```bash
# Regenerate entire file from scratch
algebras translate --only-missing --language it --regenerate-from-scratch
```

## When to Use Each Mode

### In-Place Updates (Default)
✅ **Use when:**
- You want to preserve comments and formatting
- You have manually edited translation files
- You want to maintain element order
- You need to preserve HTML entities like `&#160;`

### Regenerate from Scratch
✅ **Use when:**
- You want to normalize file structure
- You've made manual changes that need to be reset
- You want consistent formatting across all files

## Supported Formats

Currently, in-place updates are fully supported for:
- ✅ **Android XML** (`.xml`) - Preserves structure, comments, and HTML entities
- ✅ **Gettext PO** (`.po`) - Preserves comments and metadata

Other formats show a warning and fall back to regeneration:
- ⚠️ JSON, YAML, TypeScript, iOS Strings, HTML, XLIFF, etc.

## Files in This Example

- `example_before.xml` - Target file before translation
- `example_after_inplace.xml` - Target file after in-place update
- `example_after_regenerate.xml` - Target file after regeneration

