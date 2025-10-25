# YAML Format Guide

[![YAML](https://img.shields.io/badge/YAML-CB171E?style=flat&logo=yaml&logoColor=white)](https://yaml.org/)

## Overview

YAML (YAML Ain't Markup Language) is a human-readable data serialization format commonly used for configuration files and localization in various applications. It's particularly popular in DevOps tools, static site generators, and configuration-heavy applications.

## When to Use YAML

- **Configuration Files**: Application settings and preferences
- **Static Site Generators**: Jekyll, Hugo, Gatsby, Eleventy
- **DevOps Tools**: Docker Compose, Kubernetes, Ansible
- **Documentation**: MkDocs, GitBook, Docusaurus
- **CI/CD Pipelines**: GitHub Actions, GitLab CI, Azure DevOps
- **Content Management**: Headless CMS systems

## File Structure

YAML localization files typically follow this structure:

```yaml
# en.yml
common:
  welcome: "Welcome to our application!"
  login: "Log In"
  logout: "Log Out"
  save: "Save"
  cancel: "Cancel"

navigation:
  home: "Home"
  about: "About"
  contact: "Contact"
  settings: "Settings"

messages:
  success: "Operation completed successfully"
  error: "An error occurred"
  loading: "Loading..."
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "fr", "es", "de"]
source_files:
  "locales/en.yml":
    destination_path: "locales/%algebras_locale_code%.yml"
  "config/locales/en.yml":
    destination_path: "config/locales/%algebras_locale_code%.yml"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Jekyll (Jekyll i18n):**
```yaml
source_files:
  "_data/locales/en.yml":
    destination_path: "_data/locales/%algebras_locale_code%.yml"
```

**Hugo (Hugo i18n):**
```yaml
source_files:
  "i18n/en.yaml":
    destination_path: "i18n/%algebras_locale_code%.yaml"
```

**Docusaurus:**
```yaml
source_files:
  "i18n/en/docusaurus-plugin-content-docs/current.json":
    destination_path: "i18n/%algebras_locale_code%/docusaurus-plugin-content-docs/current.json"
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

- **Use consistent indentation**: 2 spaces (recommended) or 4 spaces
- **Group related keys**: Use hierarchical structure for logical grouping
- **Use meaningful comments**: Document complex configurations

```yaml
# User interface translations
ui:
  # Navigation elements
  nav:
    home: "Home"
    about: "About"
  # Form elements
  form:
    submit: "Submit"
    reset: "Reset"
```

### 2. Key Naming Conventions

- **Hierarchical structure**: `section.subsection.key`
- **Snake case**: Use underscores for multi-word keys
- **Descriptive names**: Use clear, descriptive key names

```yaml
user_profile:
  personal_info:
    first_name: "First Name"
    last_name: "Last Name"
    email_address: "Email Address"
  account_settings:
    change_password: "Change Password"
    privacy_settings: "Privacy Settings"
```

### 3. Special Characters and Escaping

- **Quotes**: Use single quotes for strings with special characters
- **Multiline strings**: Use `|` for literal block scalars or `>` for folded block scalars
- **Unicode support**: Full Unicode character support

```yaml
messages:
  # Single quotes for strings with special characters
  welcome: 'Welcome to "My App"!'
  
  # Multiline strings
  description: |
    This is a multi-line
    description that spans
    several lines.
  
  # Folded strings (single line with line breaks)
  summary: >
    This is a long description
    that will be folded into
    a single line.
```

### 4. Data Types

- **Strings**: Default type, can be quoted or unquoted
- **Numbers**: Integers and floats
- **Booleans**: true/false, yes/no, on/off
- **Lists**: Arrays of values
- **Maps**: Key-value pairs

```yaml
# Different data types
app_config:
  name: "My Application"  # String
  version: 1.2.3          # String (version numbers)
  debug: true             # Boolean
  max_users: 1000         # Integer
  features:               # List
    - "authentication"
    - "dashboard"
    - "reports"
  settings:               # Map
    theme: "dark"
    language: "en"
```

## Common Use Cases

### Jekyll i18n

```yaml
# _data/locales/en.yml
site:
  title: "My Jekyll Site"
  description: "A great Jekyll website"

navigation:
  - title: "Home"
    url: "/"
  - title: "About"
    url: "/about/"
```

### Hugo i18n

```yaml
# i18n/en.yaml
- id: "home"
  translation: "Home"
- id: "about"
  translation: "About"
- id: "contact"
  translation: "Contact"
```

### Docusaurus

```yaml
# i18n/en/docusaurus-plugin-content-docs/current.json
{
  "version.label": {
    "message": "Version",
    "description": "The label for version current"
  },
  "sidebar.docs.category.Getting Started": {
    "message": "Getting Started",
    "description": "The label for category Getting Started in sidebar docs"
  }
}
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    image: myapp:latest
    environment:
      - LANG=en_US.UTF-8
      - LC_ALL=en_US.UTF-8
    labels:
      - "com.example.description=My Application"
      - "com.example.version=1.0.0"
```

## Example Files

### Before Translation (en.yml)
```yaml
# Application configuration
app:
  name: "My Application"
  version: "1.0.0"
  description: "A powerful tool for developers"

# User interface
ui:
  navigation:
    home: "Home"
    about: "About"
    contact: "Contact"
  buttons:
    save: "Save"
    cancel: "Cancel"
    delete: "Delete"

# Messages
messages:
  success: "Operation completed successfully"
  error: "An error occurred"
  loading: "Loading..."
```

### After Translation (fr.yml)
```yaml
# Configuration de l'application
app:
  name: "Mon Application"
  version: "1.0.0"
  description: "Un outil puissant pour les développeurs"

# Interface utilisateur
ui:
  navigation:
    home: "Accueil"
    about: "À propos"
    contact: "Contact"
  buttons:
    save: "Enregistrer"
    cancel: "Annuler"
    delete: "Supprimer"

# Messages
messages:
  success: "Opération terminée avec succès"
  error: "Une erreur s'est produite"
  loading: "Chargement..."
```

## Troubleshooting

### Common Issues

**Indentation errors:**
- Ensure consistent indentation (2 or 4 spaces)
- Don't mix tabs and spaces
- Use a YAML linter to validate syntax

**Invalid YAML syntax:**
- Check for proper quoting of strings with special characters
- Ensure colons are followed by spaces
- Validate YAML structure before translation

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

## YAML vs YML

Both `.yaml` and `.yml` extensions are supported:
- `.yaml` - Full extension (recommended for clarity)
- `.yml` - Short extension (common in many projects)

Choose one and be consistent throughout your project.

## Related Examples

- [Jekyll Example](../../examples/jekyll-app/) - Complete Jekyll setup
- [Hugo Example](../../examples/hugo-app/) - Hugo static site
- [Docusaurus Example](../../examples/docusaurus-app/) - Documentation site
