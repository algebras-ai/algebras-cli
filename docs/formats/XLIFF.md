# XLIFF Format Guide

[![Angular](https://img.shields.io/badge/Angular-DD0031?style=flat&logo=angular&logoColor=white)](https://angular.io/) [![XML](https://img.shields.io/badge/XML-FF6600?style=flat&logo=xml&logoColor=white)](https://www.w3.org/XML/)

## Overview

XLIFF (XML Localization Interchange File Format) is a standard format for exchanging localization data between different tools and systems. It's widely used in enterprise applications, Angular i18n, and professional translation workflows.

## When to Use XLIFF

- **Angular Applications**: Angular i18n with XLIFF files
- **Enterprise Applications**: Large-scale applications requiring professional translation
- **Translation Management Systems**: TMS integration and workflow
- **Professional Translation**: When working with translation agencies
- **Multi-platform Projects**: Projects targeting multiple platforms
- **Complex Localization**: Projects with complex localization requirements

## File Structure

XLIFF projects use a specific directory structure for XLIFF files:

```
src/
├── locale/
│   ├── messages.en.xlf     # English (base language)
│   ├── messages.es.xlf     # Spanish translations
│   ├── messages.fr.xlf     # French translations
│   └── messages.ru.xlf     # Russian translations
└── app/
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "src/locale/messages.en.xlf":
    destination_path: "src/locale/messages.%algebras_locale_code%.xlf"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Angular Project:**
```yaml
source_files:
  "src/locale/messages.en.xlf":
    destination_path: "src/locale/messages.%algebras_locale_code%.xlf"
```

**Multiple XLIFF Files:**
```yaml
source_files:
  "src/locale/messages.en.xlf":
    destination_path: "src/locale/messages.%algebras_locale_code%.xlf"
  "src/locale/admin.en.xlf":
    destination_path: "src/locale/admin.%algebras_locale_code%.xlf"
```

**Custom Localization Directory:**
```yaml
source_files:
  "assets/i18n/messages.en.xlf":
    destination_path: "assets/i18n/messages.%algebras_locale_code%.xlf"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your project directory
cd your-project

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

### 1. XLIFF File Structure

- **Proper XML formatting**: Use consistent formatting and structure
- **Namespace declarations**: Include proper namespace declarations
- **File attributes**: Use proper file attributes for metadata
- **Unit organization**: Organize translation units logically

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="ng2.template" datatype="html" source-language="en" target-language="en">
    <header>
      <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    </header>
    <body>
      <trans-unit id="app.title" datatype="html">
        <source>My Angular App</source>
        <target>My Angular App</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

### 2. Translation Unit Structure

- **Unique IDs**: Use unique IDs for translation units
- **Source and target**: Include both source and target text
- **Context information**: Add context when needed
- **Notes**: Include notes for translators

```xml
<trans-unit id="welcome.message" datatype="html">
  <source>Welcome to our application!</source>
  <target>Welcome to our application!</target>
  <note from="developer">Welcome message displayed on the home screen</note>
</trans-unit>
```

### 3. Pluralization Support

- **Plural forms**: Use proper plural forms for different quantities
- **ICU format**: Use ICU message format for pluralization
- **Language-specific rules**: Consider language-specific plural rules

```xml
<trans-unit id="items.count" datatype="html">
  <source>{count, plural, =0 {No items} =1 {One item} other {{count} items}}</source>
  <target>{count, plural, =0 {No items} =1 {One item} other {{count} items}}</target>
  <note from="developer">Item count with pluralization</note>
</trans-unit>
```

### 4. String Formatting

- **ICU format**: Use ICU message format for string formatting
- **Parameters**: Use proper parameter syntax
- **HTML formatting**: Use HTML tags for text formatting when needed

```xml
<trans-unit id="welcome.user" datatype="html">
  <source>Welcome, {userName}!</source>
  <target>Welcome, {userName}!</target>
  <note from="developer">Welcome message with user name</note>
</trans-unit>

<trans-unit id="formatted.text" datatype="html">
  <source>This is <b>bold</b> and <i>italic</i> text</source>
  <target>This is <b>bold</b> and <i>italic</i> text</target>
  <note from="developer">Formatted text with HTML tags</note>
</trans-unit>
```

### 5. Metadata and Documentation

- **File attributes**: Include proper file attributes
- **Tool information**: Include tool information in header
- **Notes**: Add notes for translators and developers
- **Context**: Provide context for complex strings

```xml
<file original="ng2.template" datatype="html" source-language="en" target-language="en">
  <header>
    <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    <note>This file contains translations for the Angular application</note>
  </header>
  <body>
    <trans-unit id="complex.string" datatype="html">
      <source>This is a complex string with multiple parameters</source>
      <target>This is a complex string with multiple parameters</target>
      <note from="developer">This string is used in the user dashboard</note>
      <note from="translator">Please maintain the technical tone</note>
    </trans-unit>
  </body>
</file>
```

## Common Use Cases

### Angular Application

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="ng2.template" datatype="html" source-language="en" target-language="en">
    <header>
      <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    </header>
    <body>
      <trans-unit id="app.title" datatype="html">
        <source>My Angular App</source>
        <target>My Angular App</target>
      </trans-unit>
      
      <trans-unit id="welcome.message" datatype="html">
        <source>Welcome to our application!</source>
        <target>Welcome to our application!</target>
      </trans-unit>
      
      <trans-unit id="login.button" datatype="html">
        <source>Log In</source>
        <target>Log In</target>
      </trans-unit>
      
      <trans-unit id="logout.button" datatype="html">
        <source>Log Out</source>
        <target>Log Out</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

### E-commerce Application

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="ng2.template" datatype="html" source-language="en" target-language="en">
    <header>
      <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    </header>
    <body>
      <trans-unit id="app.title" datatype="html">
        <source>Shopping App</source>
        <target>Shopping App</target>
      </trans-unit>
      
      <trans-unit id="product.title" datatype="html">
        <source>Product Details</source>
        <target>Product Details</target>
      </trans-unit>
      
      <trans-unit id="add.to.cart" datatype="html">
        <source>Add to Cart</source>
        <target>Add to Cart</target>
      </trans-unit>
      
      <trans-unit id="cart.items.count" datatype="html">
        <source>{count, plural, =0 {Your cart is empty} =1 {1 item in cart} other {{count} items in cart}}</source>
        <target>{count, plural, =0 {Your cart is empty} =1 {1 item in cart} other {{count} items in cart}}</target>
      </trans-unit>
      
      <trans-unit id="total.price" datatype="html">
        <source>Total: ${price}</source>
        <target>Total: ${price}</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

### User Profile Application

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="ng2.template" datatype="html" source-language="en" target-language="en">
    <header>
      <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    </header>
    <body>
      <trans-unit id="user.profile.title" datatype="html">
        <source>User Profile</source>
        <target>User Profile</target>
      </trans-unit>
      
      <trans-unit id="edit.profile" datatype="html">
        <source>Edit Profile</source>
        <target>Edit Profile</target>
      </trans-unit>
      
      <trans-unit id="save.changes" datatype="html">
        <source>Save Changes</source>
        <target>Save Changes</target>
      </trans-unit>
      
      <trans-unit id="cancel.changes" datatype="html">
        <source>Cancel Changes</source>
        <target>Cancel Changes</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

## Example Files

### Before Translation (messages.en.xlf)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="ng2.template" datatype="html" source-language="en" target-language="en">
    <header>
      <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    </header>
    <body>
      <trans-unit id="app.title" datatype="html">
        <source>My Angular App</source>
        <target>My Angular App</target>
      </trans-unit>
      
      <trans-unit id="welcome.message" datatype="html">
        <source>Welcome to our application!</source>
        <target>Welcome to our application!</target>
      </trans-unit>
      
      <trans-unit id="login.button" datatype="html">
        <source>Log In</source>
        <target>Log In</target>
      </trans-unit>
      
      <trans-unit id="logout.button" datatype="html">
        <source>Log Out</source>
        <target>Log Out</target>
      </trans-unit>
      
      <trans-unit id="save.button" datatype="html">
        <source>Save</source>
        <target>Save</target>
      </trans-unit>
      
      <trans-unit id="cancel.button" datatype="html">
        <source>Cancel</source>
        <target>Cancel</target>
      </trans-unit>
      
      <trans-unit id="delete.button" datatype="html">
        <source>Delete</source>
        <target>Delete</target>
      </trans-unit>
      
      <trans-unit id="edit.button" datatype="html">
        <source>Edit</source>
        <target>Edit</target>
      </trans-unit>
      
      <trans-unit id="user.profile.title" datatype="html">
        <source>User Profile</source>
        <target>User Profile</target>
      </trans-unit>
      
      <trans-unit id="user.profile.edit.hint" datatype="html">
        <source>Tap to edit your profile</source>
        <target>Tap to edit your profile</target>
      </trans-unit>
      
      <trans-unit id="success.message" datatype="html">
        <source>Operation completed successfully</source>
        <target>Operation completed successfully</target>
      </trans-unit>
      
      <trans-unit id="error.message" datatype="html">
        <source>An error occurred</source>
        <target>An error occurred</target>
      </trans-unit>
      
      <trans-unit id="loading.message" datatype="html">
        <source>Loading...</source>
        <target>Loading...</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

### After Translation (messages.es.xlf)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:oasis:names:tc:xliff:document:1.2 http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd">
  <file original="ng2.template" datatype="html" source-language="en" target-language="es">
    <header>
      <tool tool-id="ng-xi18n" tool-name="Angular i18n" tool-version="2.0.0" tool-company="Google Inc."/>
    </header>
    <body>
      <trans-unit id="app.title" datatype="html">
        <source>My Angular App</source>
        <target>Mi Aplicación Angular</target>
      </trans-unit>
      
      <trans-unit id="welcome.message" datatype="html">
        <source>Welcome to our application!</source>
        <target>¡Bienvenido a nuestra aplicación!</target>
      </trans-unit>
      
      <trans-unit id="login.button" datatype="html">
        <source>Log In</source>
        <target>Iniciar Sesión</target>
      </trans-unit>
      
      <trans-unit id="logout.button" datatype="html">
        <source>Log Out</source>
        <target>Cerrar Sesión</target>
      </trans-unit>
      
      <trans-unit id="save.button" datatype="html">
        <source>Save</source>
        <target>Guardar</target>
      </trans-unit>
      
      <trans-unit id="cancel.button" datatype="html">
        <source>Cancel</source>
        <target>Cancelar</target>
      </trans-unit>
      
      <trans-unit id="delete.button" datatype="html">
        <source>Delete</source>
        <target>Eliminar</target>
      </trans-unit>
      
      <trans-unit id="edit.button" datatype="html">
        <source>Edit</source>
        <target>Editar</target>
      </trans-unit>
      
      <trans-unit id="user.profile.title" datatype="html">
        <source>User Profile</source>
        <target>Perfil de Usuario</target>
      </trans-unit>
      
      <trans-unit id="user.profile.edit.hint" datatype="html">
        <source>Tap to edit your profile</source>
        <target>Toca para editar tu perfil</target>
      </trans-unit>
      
      <trans-unit id="success.message" datatype="html">
        <source>Operation completed successfully</source>
        <target>Operación completada exitosamente</target>
      </trans-unit>
      
      <trans-unit id="error.message" datatype="html">
        <source>An error occurred</source>
        <target>Ocurrió un error</target>
      </trans-unit>
      
      <trans-unit id="loading.message" datatype="html">
        <source>Loading...</source>
        <target>Cargando...</target>
      </trans-unit>
    </body>
  </file>
</xliff>
```

## Advanced Features

### 1. Complex Pluralization

```xml
<trans-unit id="items.count" datatype="html">
  <source>{count, plural, =0 {No items} =1 {One item} =2 {Two items} few {{count} items} many {{count} items} other {{count} items}}</source>
  <target>{count, plural, =0 {No items} =1 {One item} =2 {Two items} few {{count} items} many {{count} items} other {{count} items}}</target>
  <note from="developer">Item count with complex pluralization</note>
</trans-unit>
```

### 2. Multiple Parameters

```xml
<trans-unit id="user.items.count" datatype="html">
  <source>{userName} has {count, plural, =0 {no items} =1 {one item} other {{count} items}}</source>
  <target>{userName} has {count, plural, =0 {no items} =1 {one item} other {{count} items}}</target>
  <note from="developer">User item count with pluralization</note>
</trans-unit>
```

### 3. HTML Formatting

```xml
<trans-unit id="formatted.text" datatype="html">
  <source>This is <b>bold</b> and <i>italic</i> text</source>
  <target>This is <b>bold</b> and <i>italic</i> text</target>
  <note from="developer">Formatted text with HTML tags</note>
</trans-unit>
```

## Troubleshooting

### Common Issues

**XLIFF parsing errors:**
- Ensure valid XML structure
- Check for proper namespace declarations
- Validate XLIFF file structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Pluralization issues:**
- Verify ICU format is correct
- Check language-specific plural rules
- Ensure proper format specifiers

**Namespace issues:**
- Ensure proper namespace declarations
- Check schema location URLs
- Verify XLIFF version compatibility

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Related Examples

- [Angular Example](../../examples/angular-app/) - Complete Angular setup
- [XLIFF Example](../../examples/xliff-app/) - XLIFF specific example
- [Enterprise Example](../../examples/enterprise-app/) - Enterprise XLIFF workflow
