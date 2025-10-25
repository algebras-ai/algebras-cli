# TypeScript Format Guide

[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)

## Overview

TypeScript translation files are TypeScript modules that export translation objects with type safety. This format is commonly used in TypeScript-based applications for better developer experience with IntelliSense, type checking, and refactoring support.

## When to Use TypeScript

- **TypeScript Applications**: Any project using TypeScript
- **React with TypeScript**: React apps with TypeScript support
- **Next.js with TypeScript**: Next.js projects using TypeScript
- **Angular Applications**: Angular i18n with TypeScript
- **Node.js with TypeScript**: Backend applications using TypeScript
- **Type Safety**: When you need compile-time type checking for translations

## File Structure

TypeScript translation files typically follow this structure:

```typescript
// en.ts
export default {
  common: {
    welcome: "Welcome to our application!",
    login: "Log In",
    logout: "Log Out",
    save: "Save",
    cancel: "Cancel"
  },
  navigation: {
    home: "Home",
    about: "About",
    contact: "Contact",
    settings: "Settings"
  },
  messages: {
    success: "Operation completed successfully",
    error: "An error occurred",
    loading: "Loading..."
  }
} as const;

// Type definitions (optional but recommended)
export type TranslationKeys = typeof default;
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "fr", "es", "de"]
source_files:
  "src/locales/en.ts":
    destination_path: "src/locales/%algebras_locale_code%.ts"
  "locales/en.ts":
    destination_path: "locales/%algebras_locale_code%.ts"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**React with TypeScript:**
```yaml
source_files:
  "src/locales/en.ts":
    destination_path: "src/locales/%algebras_locale_code%.ts"
```

**Next.js with TypeScript:**
```yaml
source_files:
  "public/locales/en.ts":
    destination_path: "public/locales/%algebras_locale_code%.ts"
```

**Angular with TypeScript:**
```yaml
source_files:
  "src/assets/i18n/en.ts":
    destination_path: "src/assets/i18n/%algebras_locale_code%.ts"
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

### 1. Type Safety

- **Use `as const`**: Ensures literal types instead of string types
- **Export types**: Create type definitions for better IntelliSense
- **Nested types**: Use recursive types for nested objects

```typescript
// en.ts
export default {
  common: {
    welcome: "Welcome to our application!",
    login: "Log In"
  },
  navigation: {
    home: "Home",
    about: "About"
  }
} as const;

// types.ts
export type TranslationKeys = typeof default;
export type CommonKeys = keyof TranslationKeys['common'];
export type NavigationKeys = keyof TranslationKeys['navigation'];
```

### 2. File Organization

- **Separate files**: One file per language
- **Consistent naming**: Use language codes as filenames
- **Type definitions**: Keep types in separate files or at the bottom

```typescript
// en.ts
export default {
  // ... translations
} as const;

// types.ts
export type TranslationKeys = typeof default;
export type TranslationKey = keyof TranslationKeys;
```

### 3. Key Naming Conventions

- **Hierarchical structure**: `section.subsection.key`
- **CamelCase**: Use camelCase for multi-word keys
- **Descriptive names**: Use clear, descriptive key names

```typescript
export default {
  userProfile: {
    personalInfo: {
      firstName: "First Name",
      lastName: "Last Name",
      emailAddress: "Email Address"
    },
    accountSettings: {
      changePassword: "Change Password",
      privacySettings: "Privacy Settings"
    }
  }
} as const;
```

### 4. String Interpolation

- **Template literals**: Use template literals for dynamic content
- **Type-safe parameters**: Define parameter types
- **Consistent formatting**: Use consistent parameter naming

```typescript
export default {
  welcome: "Welcome, {{name}}!",
  itemsCount: "{{count}} items",
  dateRange: "From {{startDate}} to {{endDate}}"
} as const;

// Type for parameters
export interface TranslationParams {
  name?: string;
  count?: number;
  startDate?: string;
  endDate?: string;
}
```

### 5. Comments and Documentation

- **JSDoc comments**: Document complex translations
- **Inline comments**: Explain context or usage
- **Type documentation**: Document parameter types

```typescript
export default {
  /**
   * Welcome message for logged-in users
   * @param name - User's display name
   */
  welcome: "Welcome, {{name}}!",
  
  // Used in navigation menu
  navigation: {
    home: "Home",
    about: "About"
  }
} as const;
```

## Common Use Cases

### React with TypeScript

```typescript
// en.ts
export default {
  common: {
    welcome: "Welcome to our app!",
    loading: "Loading..."
  },
  pages: {
    home: {
      title: "Home Page",
      description: "Welcome to the home page"
    }
  }
} as const;

// Usage in component
import translations from '../locales/en';
import { TranslationKeys } from '../types';

const HomePage: React.FC = () => {
  const t = (key: keyof TranslationKeys) => translations[key];
  
  return (
    <div>
      <h1>{t('pages.home.title')}</h1>
      <p>{t('pages.home.description')}</p>
    </div>
  );
};
```

### Next.js with TypeScript

```typescript
// public/locales/en.ts
export default {
  common: {
    title: "My Next.js App",
    description: "A great Next.js application"
  }
} as const;

// Usage in page
import translations from '../public/locales/en';

export default function HomePage() {
  return (
    <div>
      <h1>{translations.common.title}</h1>
      <p>{translations.common.description}</p>
    </div>
  );
}
```

### Angular with TypeScript

```typescript
// src/assets/i18n/en.ts
export default {
  app: {
    title: "My Angular App",
    description: "A great Angular application"
  },
  navigation: {
    home: "Home",
    about: "About"
  }
} as const;

// Usage in component
import { Component } from '@angular/core';
import translations from '../assets/i18n/en';

@Component({
  selector: 'app-home',
  template: `
    <h1>{{translations.app.title}}</h1>
    <p>{{translations.app.description}}</p>
  `
})
export class HomeComponent {
  translations = translations;
}
```

## Example Files

### Before Translation (en.ts)
```typescript
// en.ts
export default {
  app: {
    title: "My Application",
    description: "A powerful tool for developers",
    version: "1.0.0"
  },
  navigation: {
    home: "Home",
    about: "About",
    contact: "Contact",
    settings: "Settings"
  },
  buttons: {
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    edit: "Edit"
  },
  messages: {
    success: "Operation completed successfully",
    error: "An error occurred",
    loading: "Loading...",
    confirm: "Are you sure?"
  }
} as const;

// Type definitions
export type TranslationKeys = typeof default;
export type AppKeys = keyof TranslationKeys['app'];
export type NavigationKeys = keyof TranslationKeys['navigation'];
export type ButtonKeys = keyof TranslationKeys['buttons'];
export type MessageKeys = keyof TranslationKeys['messages'];
```

### After Translation (fr.ts)
```typescript
// fr.ts
export default {
  app: {
    title: "Mon Application",
    description: "Un outil puissant pour les développeurs",
    version: "1.0.0"
  },
  navigation: {
    home: "Accueil",
    about: "À propos",
    contact: "Contact",
    settings: "Paramètres"
  },
  buttons: {
    save: "Enregistrer",
    cancel: "Annuler",
    delete: "Supprimer",
    edit: "Modifier"
  },
  messages: {
    success: "Opération terminée avec succès",
    error: "Une erreur s'est produite",
    loading: "Chargement...",
    confirm: "Êtes-vous sûr ?"
  }
} as const;

// Type definitions (same as English)
export type TranslationKeys = typeof default;
export type AppKeys = keyof TranslationKeys['app'];
export type NavigationKeys = keyof TranslationKeys['navigation'];
export type ButtonKeys = keyof TranslationKeys['buttons'];
export type MessageKeys = keyof TranslationKeys['messages'];
```

## Advanced Features

### 1. Conditional Translations

```typescript
export default {
  user: {
    greeting: "Hello, {{name}}!",
    status: {
      online: "Online",
      offline: "Offline",
      away: "Away"
    }
  }
} as const;
```

### 2. Pluralization Support

```typescript
export default {
  items: {
    zero: "No items",
    one: "One item",
    other: "{{count}} items"
  }
} as const;
```

### 3. Nested Object Access

```typescript
// Type-safe nested access
type NestedKey<T, K extends keyof T> = T[K] extends object 
  ? T[K] extends string 
    ? K 
    : `${K & string}.${NestedKey<T[K], keyof T[K]> & string}`
  : K;

type AllKeys = NestedKey<TranslationKeys, keyof TranslationKeys>;
// Result: "app.title" | "navigation.home" | "buttons.save" | ...
```

## Troubleshooting

### Common Issues

**Type errors:**
- Ensure `as const` is used for literal types
- Check that all keys exist in all language files
- Verify type definitions are properly exported

**Import/export issues:**
- Use consistent import/export syntax
- Check file paths are correct
- Ensure TypeScript configuration is proper

**Translation missing:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

### Performance Tips

- **Tree shaking**: Use named exports for better tree shaking
- **Lazy loading**: Load translations on demand
- **Type optimization**: Use `as const` for better type inference

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Related Examples

- [React TypeScript Example](../../examples/react-ts-app/) - Complete React setup
- [Next.js TypeScript Example](../../examples/nextjs-ts-app/) - Next.js with TypeScript
- [Angular Example](../../examples/angular-app/) - Angular with i18n
