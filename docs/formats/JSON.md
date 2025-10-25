# JSON Format Guide

[![JSON](https://img.shields.io/badge/JSON-000000?style=flat&logo=json&logoColor=white)](https://www.json.org/)

## Overview

JSON (JavaScript Object Notation) is the most common format for web application localization. It's widely used by modern JavaScript frameworks like React, Next.js, Vue.js, and Angular for storing translation data.

## When to Use JSON

- **Web Applications**: React, Next.js, Vue.js, Angular, Svelte
- **Node.js Applications**: Express, Fastify, NestJS
- **Static Site Generators**: Gatsby, Nuxt.js, SvelteKit
- **Progressive Web Apps**: Any PWA with i18n support
- **Simple Structure**: When you need a straightforward key-value mapping

## File Structure

JSON localization files typically follow this structure:

```json
{
  "common": {
    "welcome": "Welcome to our application!",
    "login": "Log In",
    "logout": "Log Out",
    "save": "Save",
    "cancel": "Cancel"
  },
  "navigation": {
    "home": "Home",
    "about": "About",
    "contact": "Contact",
    "settings": "Settings"
  },
  "messages": {
    "success": "Operation completed successfully",
    "error": "An error occurred",
    "loading": "Loading..."
  }
}
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "fr", "es", "de"]
source_files:
  "public/locales/en/common.json":
    destination_path: "public/locales/%algebras_locale_code%/common.json"
  "src/locales/en/translation.json":
    destination_path: "src/locales/%algebras_locale_code%/translation.json"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Next.js/React (next-i18next):**
```yaml
source_files:
  "public/locales/en/common.json":
    destination_path: "public/locales/%algebras_locale_code%/common.json"
  "public/locales/en/translation.json":
    destination_path: "public/locales/%algebras_locale_code%/translation.json"
```

**Vue.js (vue-i18n):**
```yaml
source_files:
  "src/locales/en.json":
    destination_path: "src/locales/%algebras_locale_code%.json"
```

**Angular (ngx-translate):**
```yaml
source_files:
  "src/assets/i18n/en.json":
    destination_path: "src/assets/i18n/%algebras_locale_code%.json"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your project directory
cd your-project

# Initialize algebras-cli
algebras init

# Add target languages
algebras add fr es de
```

### 2. Basic Translation

```bash
# Translate all missing keys
algebras translate

# Translate specific language
algebras translate --language fr

# Force translation (even if up-to-date)
algebras translate --force
```

### 3. Update Translations

```bash
# Update missing keys only
algebras update

# Update specific language
algebras update --language es

# Full translation update
algebras update --full
```

### 4. Check Status

```bash
# Check all languages
algebras status

# Check specific language
algebras status --language de
```

### 5. Review Translations

```bash
# Review all languages
algebras review

# Review specific language
algebras review --language fr
```

## Best Practices

### 1. File Organization

- **Group related keys**: Use nested objects for logical grouping
- **Consistent naming**: Use camelCase or snake_case consistently
- **Descriptive keys**: Use meaningful key names that describe the content

```json
{
  "user": {
    "profile": {
      "firstName": "First Name",
      "lastName": "Last Name",
      "email": "Email Address"
    },
    "actions": {
      "editProfile": "Edit Profile",
      "changePassword": "Change Password"
    }
  }
}
```

### 2. Key Naming Conventions

- **Hierarchical structure**: `section.subsection.key`
- **Action-based**: `button.save`, `button.cancel`, `button.delete`
- **Context-aware**: `form.validation.required`, `form.validation.email`

### 3. Special Characters

- **Escape quotes**: Use `\"` for quotes within strings
- **Unicode support**: JSON supports full Unicode characters
- **Line breaks**: Use `\n` for line breaks in strings

```json
{
  "message": "Hello \"World\"!\nWelcome to our app.",
  "special": "Café, naïve, résumé"
}
```

### 4. Pluralization

For languages that require pluralization, use a structure like:

```json
{
  "items": {
    "zero": "No items",
    "one": "One item",
    "other": "{{count}} items"
  }
}
```

## Common Use Cases

### React with react-i18next

```javascript
// en.json
{
  "welcome": "Welcome, {{name}}!",
  "items": "{{count}} items"
}

// Usage in component
const { t } = useTranslation();
return <h1>{t('welcome', { name: 'John' })}</h1>;
```

### Next.js with next-i18next

```javascript
// public/locales/en/common.json
{
  "title": "My App",
  "description": "A great application"
}

// Usage in page
import { useTranslation } from 'next-i18next';

export default function HomePage() {
  const { t } = useTranslation('common');
  return <h1>{t('title')}</h1>;
}
```

### Vue.js with vue-i18n

```javascript
// en.json
{
  "hello": "Hello {name}!"
}

// Usage in component
<template>
  <h1>{{ $t('hello', { name: 'World' }) }}</h1>
</template>
```

## Example Files

### Before Translation (en/common.json)
```json
{
  "app": {
    "title": "My Application",
    "description": "A powerful tool for developers"
  },
  "navigation": {
    "home": "Home",
    "about": "About",
    "contact": "Contact"
  },
  "buttons": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete"
  }
}
```

### After Translation (fr/common.json)
```json
{
  "app": {
    "title": "Mon Application",
    "description": "Un outil puissant pour les développeurs"
  },
  "navigation": {
    "home": "Accueil",
    "about": "À propos",
    "contact": "Contact"
  },
  "buttons": {
    "save": "Enregistrer",
    "cancel": "Annuler",
    "delete": "Supprimer"
  }
}
```

## Troubleshooting

### Common Issues

**Invalid JSON syntax:**
- Ensure all strings are properly quoted
- Check for trailing commas
- Validate JSON structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Ensure files are saved as UTF-8
- Check for BOM (Byte Order Mark) in files
- Verify special characters are properly encoded

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Related Examples

- [Next.js Example](../../examples/nextjs-app/) - Complete Next.js setup
- [React Example](../../examples/react-app/) - React with i18next
- [Vue.js Example](../../examples/vue-app/) - Vue.js with vue-i18n
