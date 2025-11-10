# Algebras CLI

[![PyPI version](https://badge.fury.io/py/algebras-cli.svg)](https://badge.fury.io/py/algebras-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Tests](https://github.com/algebras-ai/algebras-cli/actions/workflows/python-tests.yml/badge.svg)](https://github.com/algebras-ai/algebras-cli/actions/workflows/python-tests.yml)
[![codecov](https://codecov.io/gh/algebras-ai/algebras-cli/branch/main/graph/badge.svg)](https://codecov.io/gh/algebras-ai/algebras-cli)

## Supported Frameworks

[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-4FC08D?style=flat&logo=vue.js&logoColor=white)](https://vuejs.org/)
[![Svelte](https://img.shields.io/badge/Svelte-FF3E00?style=flat&logo=svelte&logoColor=white)](https://svelte.dev/)
[![Flutter](https://img.shields.io/badge/Flutter-02569B?style=flat&logo=flutter&logoColor=white)](https://flutter.dev/)
[![Angular](https://img.shields.io/badge/Angular-DD0031?style=flat&logo=angular&logoColor=white)](https://angular.io/)
[![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com/)
[![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Android](https://img.shields.io/badge/Android-3DDC84?style=flat&logo=android&logoColor=white)](https://developer.android.com/)
[![iOS](https://img.shields.io/badge/iOS-000000?style=flat&logo=ios&logoColor=white)](https://developer.apple.com/ios/)
[![Java](https://img.shields.io/badge/Java-ED8B00?style=flat&logo=java&logoColor=white)](https://www.java.com/)
[![Spring](https://img.shields.io/badge/Spring-6DB33F?style=flat&logo=spring&logoColor=white)](https://spring.io/)
[![Rails](https://img.shields.io/badge/Rails-CC0000?style=flat&logo=ruby-on-rails&logoColor=white)](https://rubyonrails.org/)
[![Nuxt.js](https://img.shields.io/badge/Nuxt.js-00C58E?style=flat&logo=nuxt.js&logoColor=white)](https://nuxtjs.org/)
[![SvelteKit](https://img.shields.io/badge/SvelteKit-FF3E00?style=flat&logo=svelte&logoColor=white)](https://kit.svelte.dev/)
[![Gatsby](https://img.shields.io/badge/Gatsby-663399?style=flat&logo=gatsby&logoColor=white)](https://www.gatsbyjs.com/)
[![WordPress](https://img.shields.io/badge/WordPress-21759B?style=flat&logo=wordpress&logoColor=white)](https://wordpress.org/)


> Powerful AI-driven localization tool for your applications

![Algebras CLI Demo](imgs/demo-font-size-30.gif)

## Overview

Algebras CLI is a Python package that simplifies application localization by tracking translation status and automating updates. Powered by AI, it helps you manage translations across multiple languages with minimal effort.

## Supported File Formats

Algebras CLI supports a wide range of localization file formats:

[![JSON](https://img.shields.io/badge/JSON-000000?style=flat&logo=json&logoColor=white)](https://www.json.org/) [![YAML](https://img.shields.io/badge/YAML-CB171E?style=flat&logo=yaml&logoColor=white)](https://yaml.org/) [![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/) [![XML](https://img.shields.io/badge/XML-FF6600?style=flat&logo=xml&logoColor=white)](https://www.w3.org/XML/) [![HTML](https://img.shields.io/badge/HTML-E34F26?style=flat&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML) [![CSV](https://img.shields.io/badge/CSV-239120?style=flat&logo=csv&logoColor=white)](https://en.wikipedia.org/wiki/Comma-separated_values) [![Excel](https://img.shields.io/badge/Excel-217346?style=flat&logo=microsoft-excel&logoColor=white)](https://www.microsoft.com/en-us/microsoft-365/excel)

- **JSON** (`.json`) - Common for web applications (Next.js, React, etc.)
- **YAML/YML** (`.yaml`, `.yml`) - Alternative format for configuration files
- **TypeScript** (`.ts`) - TypeScript translation files
- **Android XML** (`.xml`) - Android string resources in `values/` directories
- **iOS Strings** (`.strings`) - iOS localization files
- **iOS StringsDict** (`.stringsdict`) - iOS pluralization files
- **Gettext** (`.po`) - GNU gettext files (Django, etc.)
- **HTML** (`.html`) - HTML files with translatable content
- **Flutter ARB** (`.arb`) - Application Resource Bundle for Flutter apps
- **XLIFF** (`.xlf`, `.xliff`) - XML Localization Interchange File Format
- **Java Properties** (`.properties`) - Java ResourceBundle property files
- **CSV** (`.csv`) - Comma-separated values for multi-language translations
- **XLSX** (`.xlsx`) - Excel files for multi-language translations

## Format Guides

Comprehensive guides for each supported file format with detailed usage examples, best practices, and configuration instructions:

### Web/General Formats
[![JSON](https://img.shields.io/badge/JSON-000000?style=flat&logo=json&logoColor=white)](https://www.json.org/) [![YAML](https://img.shields.io/badge/YAML-CB171E?style=flat&logo=yaml&logoColor=white)](https://yaml.org/) [![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/) [![HTML](https://img.shields.io/badge/HTML-E34F26?style=flat&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)

- **[JSON Format Guide](docs/formats/JSON.md)** - JSON localization files (Next.js, React, Vue)
- **[YAML Format Guide](docs/formats/YAML.md)** - YAML/YML configuration files
- **[TypeScript Format Guide](docs/formats/TypeScript.md)** - TypeScript translation files
- **[HTML Format Guide](docs/formats/HTML.md)** - HTML files with translatable content

### Mobile Formats
[![Android](https://img.shields.io/badge/Android-3DDC84?style=flat&logo=android&logoColor=white)](https://developer.android.com/) [![iOS](https://img.shields.io/badge/iOS-000000?style=flat&logo=ios&logoColor=white)](https://developer.apple.com/ios/) [![Flutter](https://img.shields.io/badge/Flutter-02569B?style=flat&logo=flutter&logoColor=white)](https://flutter.dev/)

- **[Android XML Format Guide](docs/formats/Android-XML.md)** - Android string resources (values directories)
- **[iOS Strings Format Guide](docs/formats/iOS-Strings.md)** - iOS .strings files
- **[iOS StringsDict Format Guide](docs/formats/iOS-StringsDict.md)** - iOS pluralization files
- **[Flutter ARB Format Guide](docs/formats/Flutter-ARB.md)** - Application Resource Bundle for Flutter

### Enterprise/Framework Formats
[![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com/) [![Angular](https://img.shields.io/badge/Angular-DD0031?style=flat&logo=angular&logoColor=white)](https://angular.io/) [![Java](https://img.shields.io/badge/Java-ED8B00?style=flat&logo=java&logoColor=white)](https://www.java.com/)

- **[Gettext PO Format Guide](docs/formats/Gettext-PO.md)** - GNU gettext files (Django, Flask, Rails)
- **[XLIFF Format Guide](docs/formats/XLIFF.md)** - XML Localization Interchange File Format (Angular)
- **[Java Properties Format Guide](docs/formats/Java-Properties.md)** - Java ResourceBundle property files

### Multi-Language Formats
[![CSV](https://img.shields.io/badge/CSV-239120?style=flat&logo=csv&logoColor=white)](https://en.wikipedia.org/wiki/Comma-separated_values) [![Excel](https://img.shields.io/badge/Excel-217346?style=flat&logo=microsoft-excel&logoColor=white)](https://www.microsoft.com/en-us/microsoft-365/excel)

- **[CSV Format Guide](docs/formats/CSV.md)** - Comma-separated values for translations
- **[XLSX Format Guide](docs/formats/XLSX.md)** - Excel files for translations

## Installation

```bash
pip install git+https://github.com/algebras-ai/algebras-cli.git
```

## Quick Start

1. **Initialize your project:**
   ```bash
   algebras init
   ```

2. **Configure source files** (if not auto-detected):
   Edit `.algebras.config` to specify your source files:
   ```yaml
   source_files:
     "src/locales/en/common.json":
       destination_path: "src/locales/%algebras_locale_code%/common.json"
   ```

3. **Add languages:**
   ```bash
   algebras add fr es de
   ```

4. **Translate:**
   ```bash
   algebras translate
   ```

## Usage

### Initialize a new Algebras project

```bash
# Basic initialization
algebras init

# Force reinitialize (overwrite existing config)
algebras init --force

# Verbose output with locale detection details
algebras init --verbose

# Set default provider during initialization
algebras init --provider algebras-ai
```

### Add a new language to your application

```bash
algebras add <language>
```

### Translate your application

```bash
# Translate all languages
algebras translate

# Translate specific language
algebras translate --language fr

# Force translation even if files are up to date
algebras translate --force

# Only translate missing keys
algebras translate --only-missing

# UI-safe translations (won't exceed original text length)
algebras translate --ui-safe

# Verbose output
algebras translate --verbose

# Use specific glossary
algebras translate --glossary-id your-glossary-id

# Use custom prompt from file
algebras translate --prompt-file custom-prompt.txt

# Regenerate files from scratch instead of updating in-place
algebras translate --regenerate-from-scratch

# Performance tuning
algebras translate --batch-size 10 --max-parallel-batches 3
```

### Use Custom Configuration Files

You can specify a custom configuration file for different translation workflows:

```bash
# Use a custom config file for specific source language
algebras -f .algebras-zh_Hans.config translate --language ja

# Use a custom config file for different source language
algebras -f .algebras-en.config translate --language es

# Apply to all commands
algebras -f .algebras-custom.config status
algebras -f .algebras-custom.config update
algebras -f .algebras-custom.config add de

# Default behavior (uses .algebras.config)
algebras translate
```

This feature enables you to maintain multiple source languages without recreating configuration files. For example:

- `.algebras.config` - Default config for `en → es, de, ru`
- `.algebras-zh_Hans.config` - Config for `zh_Hans → kr, ja`

### Update your translations

```bash
# Update missing keys only (default)
algebras update

# Update specific language
algebras update --language fr

# Translate entire file (not just missing keys)
algebras update --full

# Only translate missing keys
algebras update --only-missing

# UI-safe translations
algebras update --ui-safe

# Verbose output
algebras update --verbose
```

### Run CI checks for translations

```bash
# Check all languages
algebras ci

# Check specific language
algebras ci --language fr

# Only check for missing keys (skip git validation)
algebras ci --only-missing

# Verbose output
algebras ci --verbose
```

### Review your translations

```bash
# Review all languages
algebras review

# Review specific language
algebras review --language fr
```

### Check the status of your translations

```bash
# Check all languages
algebras status

# Check specific language
algebras status --language fr
```

### Configure settings for your Algebras project

```bash
# View current configuration
algebras configure

# Set Algebras AI as the provider
algebras configure --provider algebras-ai

# Set batch size for translation processing
algebras configure --batch-size 10

# Set maximum parallel batches
algebras configure --max-parallel-batches 3

# Set glossary ID for translations
algebras configure --glossary-id your-glossary-id

# Set default prompt for translations
algebras configure --prompt "Translate the following text to {target_language}"

# Enable/disable string normalization
algebras configure --normalize-strings true
```

### Manage glossaries

```bash
# Upload glossary from CSV file
algebras glossary push glossary.csv --name "My Glossary"

# Upload glossary from XLSX file
algebras glossary push glossary.xlsx --name "My Glossary"

# Upload with custom batch size
algebras glossary push glossary.csv --name "My Glossary" --batch-size 50

# Upload specific rows by ID
algebras glossary push glossary.csv --name "My Glossary" --rows-ids "1,2,3,4,5"

# Set maximum term length
algebras glossary push glossary.csv --name "My Glossary" --max-length 100

# Debug mode (log requests before sending)
algebras glossary push glossary.csv --name "My Glossary" --debug
```

**Note:** Source file mappings are now configured directly in the `.algebras.config` file. Use `algebras init --force` to regenerate your configuration with the new format.

## Advanced Features

[![AI](https://img.shields.io/badge/AI-FF6B6B?style=flat&logo=openai&logoColor=white)](https://openai.com/) [![Translation](https://img.shields.io/badge/Translation-4ECDC4?style=flat&logo=google-translate&logoColor=white)](https://translate.google.com/) [![Git](https://img.shields.io/badge/Git-F05032?style=flat&logo=git&logoColor=white)](https://git-scm.com/) [![CI/CD](https://img.shields.io/badge/CI/CD-2088FF?style=flat&logo=github-actions&logoColor=white)](https://github.com/features/actions)

### UI-Safe Translations

The `--ui-safe` flag ensures that translations won't exceed the original text length, which is crucial for maintaining consistent UI layouts:

```bash
algebras translate --ui-safe
algebras update --ui-safe
```

### Custom Translation Prompts

You can provide custom prompts for more specific translation requirements:

```bash
# Use a custom prompt file
algebras translate --prompt-file custom-prompt.txt

# Set a default prompt in configuration
algebras configure --prompt "Translate to {target_language} maintaining a professional tone"
```

### Glossary Management

Algebras CLI supports glossary management for consistent terminology:

1. **Upload glossaries** from CSV or XLSX files
2. **Use glossaries** in translations with `--glossary-id`
3. **Configure default glossary** in settings

### Git Integration

Algebras CLI automatically tracks translation changes using Git:

- **Detects outdated keys** by comparing modification times
- **Validates translations** against source file changes
- **Skips git validation** when using `--only-missing` flag
- **CI-friendly** with the `algebras ci` command

### Translation Caching

Algebras CLI automatically caches translations to avoid duplicate API calls:

- **Cache location**: `~/.algebras.cache` (user's home directory)
- **Automatic caching**: All successful translations are cached automatically
- **Cache hits**: Previously translated strings are retrieved from cache instantly
- **Cache persistence**: Cache persists between CLI runs
- **Cache size**: Limited to approximately 10MB to manage memory usage

The cache key includes:
- Source text
- Source language
- Target language
- UI-safe flag
- Custom prompt (if provided)

This means the same translation request will use the cache, saving API calls and improving performance.

### Batch Processing

Optimize translation performance with batch processing:

```bash
# Adjust batch size (default: 20)
algebras translate --batch-size 10

# Control parallel batches (default: 5)
algebras translate --max-parallel-batches 3

# Configure defaults
algebras configure --batch-size 10 --max-parallel-batches 3
```

### String Normalization

Control how strings are processed before translation:

```bash
# Enable string normalization (removes escaped characters like \')
algebras configure --normalize-strings true

# Disable string normalization (preserve all characters)
algebras configure --normalize-strings false
```

### In-Place Updates vs. Regenerate from Scratch

By default, when a target file exists, Algebras CLI updates keys in-place, preserving:
- File structure and formatting
- Comments and metadata
- Element order
- HTML entities (like `&#160;`)

When a target file doesn't exist, it's created from scratch.

Use `--regenerate-from-scratch` to force regeneration even when target files exist:

```bash
# Update in-place (default behavior when target file exists)
algebras translate --only-missing

# Force regenerate from scratch
algebras translate --only-missing --regenerate-from-scratch
```

**Supported formats for in-place updates:**
- ✅ Android XML (`.xml`)
- ✅ Gettext PO (`.po`)
- ⚠️ Other formats: Show warning and fall back to regeneration

**When to use each mode:**
- **In-place updates** (default): Preserves your file structure, comments, and formatting. Best for maintaining existing translation files.
- **Regenerate from scratch**: Useful when you want to normalize file structure or when you've made manual changes that need to be reset.

### Error Handling & Reliability

Algebras CLI includes robust error handling and reliability features to ensure smooth translation operations:

#### Automatic Retry Logic

The CLI automatically handles rate limit (429) and server (500) errors with intelligent retry logic:

- **Exponential backoff**: Retries use exponential backoff with jitter to prevent thundering herd problems
- **Coordinated retries**: When multiple parallel batches encounter rate limits, retries are coordinated across all batches to avoid overwhelming the API
- **Automatic recovery**: Up to 5 retry attempts with increasing wait times between attempts
- **Smart backoff**: When multiple consecutive 429 errors occur, the backoff time increases more aggressively

#### Rate Limiting

Built-in rate limiting ensures compliance with API limits:

- **30 requests per minute**: Automatic rate limiting with a sliding window approach
- **Request tracking**: Tracks requests in the last 60 seconds to enforce limits
- **Automatic throttling**: Automatically waits when approaching rate limits
- **Parallel batch coordination**: Shared rate limiting state ensures all parallel batches respect the limit

#### Empty String Handling

Empty strings are handled intelligently to avoid unnecessary API calls and improve accuracy:

- **Automatic filtering**: Empty or whitespace-only strings are automatically filtered out before API calls
- **Status counting**: Empty strings are properly counted as translated if the source is also empty
- **Improved accuracy**: Translation status reporting now correctly handles empty string scenarios

## Configuration

[![YAML](https://img.shields.io/badge/YAML-CB171E?style=flat&logo=yaml&logoColor=white)](https://yaml.org/) [![JSON](https://img.shields.io/badge/JSON-000000?style=flat&logo=json&logoColor=white)](https://www.json.org/) [![Environment](https://img.shields.io/badge/Environment-4CAF50?style=flat&logo=environment&logoColor=white)](https://en.wikipedia.org/wiki/Environment_variable)

### .algebras.config

The `.algebras.config` file is used to configure the Algebras CLI. It contains the following sections:

- `languages`: List of languages to translate the application into.
- `source_files`: Explicit mappings of source files to destination patterns using `%algebras_locale_code%` placeholder.
- `api`: API configuration for translation providers:
  - `provider`: The translation provider to use. Supported values:
    - `algebras-ai`: (Default) Use Algebras AI translation API (requires `ALGEBRAS_API_KEY` environment variable)
  - `model`: The model to use (for Algebras AI provider)

### Source Files Configuration

The new `source_files` configuration allows you to explicitly specify how source files should be mapped to destination files for different languages. This replaces the previous glob-based `path_rules` system.

#### Configuration Format

```yaml
source_files:
  "src/locales/en/common.json":
    destination_path: "src/locales/%algebras_locale_code%/common.json"
  "public/locales/en/translation.json":
    destination_path: "public/locales/%algebras_locale_code%/translation.json"
  "locale/en/LC_MESSAGES/django.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
  "app/src/main/res/values/strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/strings.xml"
```

#### Placeholder

- `%algebras_locale_code%`: Replaced with the actual locale code (e.g., `en`, `fr`, `es`, `pt_BR`)

#### Locale Code Mapping

You can map language codes to custom destination path values. This is useful when you need to use different locale codes for file paths than what you use for API translation calls.

**Example:**
```yaml
languages:
  - en
  - es
  - {uz_Cyrl: "b+uz+Cyrl"}
  - {pt_BR: "pt-rBR"}
source_files:
  "strings/values/generic_strings.xml":
    destination_path: "strings/values-%algebras_locale_code%/generic_strings.xml"
```

In this example:
- When translating to `uz_Cyrl`, the API uses `uz_Cyrl` for translation, but files are saved to `strings/values-b+uz+Cyrl/generic_strings.xml`
- When translating to `pt_BR`, the API uses `pt_BR` for translation, but files are saved to `strings/values-pt-rBR/generic_strings.xml`
- Languages without mappings (like `en` and `es`) use their own code as the destination value

**Supported YAML formats:**

1. **Dictionary format (recommended):**
   ```yaml
   languages:
     - en
     - {es: "es%sda"}
     - {uz_Cyrl: "b+uz+Cyrl"}
   ```

2. **Inline format:**
   ```yaml
   languages:
     - en
     - es: "es%sda"
     - uz_Cyrl: "b+uz+Cyrl"
   ```

**Important notes:**
- Original language codes (e.g., `uz_Cyrl`) are used for API translation calls
- Mapped codes (e.g., `b+uz+Cyrl`) are used for destination file paths (both reading and writing)
- Unmapped languages default to using their own code as the destination value

#### Examples by Project Type

**Next.js/React (next-i18next)**
```yaml
source_files:
  "public/locales/en/common.json":
    destination_path: "public/locales/%algebras_locale_code%/common.json"
```

**Django (gettext)**
```yaml
source_files:
  "locale/en/LC_MESSAGES/django.po":
    destination_path: "locale/%algebras_locale_code%/LC_MESSAGES/django.po"
```

**Android (values directories)**
```yaml
source_files:
  "app/src/main/res/values/strings.xml":
    destination_path: "app/src/main/res/values-%algebras_locale_code%/strings.xml"
```

**iOS (strings files)**
```yaml
source_files:
  "ios/App/en.lproj/Localizable.strings":
    destination_path: "ios/App/%algebras_locale_code%.lproj/Localizable.strings"
```

**HTML files**
```yaml
source_files:
  "html_files/index.html":
    destination_path: "html_files/index.%algebras_locale_code%.html"
```

### Migration from path_rules

If you're upgrading from the previous `path_rules` system, the CLI will automatically detect your existing configuration and provide backward compatibility. However, we recommend migrating to the new `source_files` format for better control and clarity.

**Old format (deprecated):**
```yaml
path_rules:
  - "public/locales/**/*.json"
  - "!**/node_modules/**"
```

**New format:**
```yaml
source_files:
  "public/locales/en/common.json":
    destination_path: "public/locales/%algebras_locale_code%/common.json"
  "public/locales/en/translation.json":
    destination_path: "public/locales/%algebras_locale_code%/translation.json"
```

To migrate:
1. Run `algebras init --force` to regenerate your configuration with the new format
2. Review and adjust the generated `source_files` mappings as needed
3. Remove any `path_rules` entries from your configuration

### Environment Variables

The following environment variables can be used to configure the Algebras CLI:

- `ALGEBRAS_API_KEY`: (Required) API key for Algebras AI translation service
- `ALGEBRAS_BASE_URL`: (Optional) Custom base URL for Algebras AI API (defaults to `https://platform.algebras.ai`)
- `ALGEBRAS_BATCH_SIZE`: (Optional) Number of translations to process in each batch (defaults to 20)
- `ALGEBRAS_MAX_PARALLEL_BATCHES`: (Optional) Maximum number of parallel batches to run (defaults to 5)

## Troubleshooting

### Common Issues

**"No Algebras configuration found"**
- Run `algebras init` to create the configuration file
- Ensure you're in the correct project directory

**"ALGEBRAS_API_KEY environment variable is not set"**
- Set your API key: `export ALGEBRAS_API_KEY=your_api_key`
- Get your API key from the [Algebras dashboard](https://platform.algebras.ai)

**"Language 'xx' is not configured"**
- Add the language: `algebras add xx`
- Check available languages: `algebras status`

**"No source files found"**
- Configure source files in `.algebras.config`
- Run `algebras init --force` to regenerate configuration
- Check file paths are correct and files exist

**Translation quality issues**
- Use `--ui-safe` flag for UI-constrained translations
- Upload a glossary for consistent terminology
- Use custom prompts for specific requirements

**Performance issues**
- Adjust batch size: `--batch-size 10`
- Control parallel batches: `--max-parallel-batches 3`
- Use `--only-missing` to skip unnecessary translations
- Translation cache is automatically used to avoid duplicate API calls
- Check cache location: `~/.algebras.cache` (cache persists between runs)

**Rate limit errors (429)**
- The CLI automatically handles rate limit errors with retry logic and exponential backoff
- Built-in rate limiting (30 requests per minute) prevents most rate limit issues
- If you see rate limit warnings, the CLI will automatically retry with increasing wait times
- No manual intervention needed - the CLI coordinates retries across parallel batches

**Empty string handling**
- Empty or whitespace-only strings are automatically filtered out before API calls
- Empty strings are properly counted as translated if the source is also empty
- This improves accuracy and avoids unnecessary API calls

### Getting Help

- Check the [GitHub Issues](https://github.com/algebras-ai/algebras-cli/issues) for known problems
- Review the [examples](examples/) directory for usage patterns
- Ensure you're using the latest version: `pip install --upgrade algebras-cli`

## Examples

We provide comprehensive examples for different frameworks and file formats:

### Framework Examples

[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/) [![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://reactjs.org/) [![Flutter](https://img.shields.io/badge/Flutter-02569B?style=flat&logo=flutter&logoColor=white)](https://flutter.dev/) [![Angular](https://img.shields.io/badge/Angular-DD0031?style=flat&logo=angular&logoColor=white)](https://angular.io/) [![Java](https://img.shields.io/badge/Java-ED8B00?style=flat&logo=java&logoColor=white)](https://www.java.com/) [![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com/)

- **[Next.js/React](examples/nextjs-app/)** - JSON-based localization with i18next
- **[Flutter](examples/flutter-app/)** - ARB files for Flutter internationalization
- **[Angular](examples/angular-app/)** - XLIFF files for Angular i18n
- **[XLIFF](examples/xliff-app/)** - Minimal XLIFF example with `.xlf`
- **[Java](examples/java-app/)** - Properties files for Java ResourceBundle
- **[Django](examples/django-app/)** - Gettext PO files for Django

### Format Examples

[![CSV](https://img.shields.io/badge/CSV-239120?style=flat&logo=csv&logoColor=white)](https://en.wikipedia.org/wiki/Comma-separated_values) [![Excel](https://img.shields.io/badge/Excel-217346?style=flat&logo=microsoft-excel&logoColor=white)](https://www.microsoft.com/en-us/microsoft-365/excel) [![HTML](https://img.shields.io/badge/HTML-E34F26?style=flat&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML) [![Android](https://img.shields.io/badge/Android-3DDC84?style=flat&logo=android&logoColor=white)](https://developer.android.com/)

- **[CSV Translations](examples/csv-translations/)** - Multi-language CSV files
- **[XLSX Translations](examples/xlsx-translations/)** - Multi-language Excel files
- **[HTML](examples/html/)** - HTML files with translatable content
- **[Android](examples/android-app/)** - Android XML string resources

Each example includes:
- Sample source files
- Configuration examples
- Framework-specific setup instructions
- Best practices and tips

## Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTE.md) for detailed information on how to get started.

### Quick Start

1. **Fork and clone** the repository
2. **Install in development mode:**
   ```bash
   pip install -e .
   pip install -r requirements-dev.txt
   ```
3. **Run tests:**
   ```bash
   pytest
   ```
4. **Make your changes** and submit a pull request

For complete development setup, testing guidelines, and contribution process, see [CONTRIBUTE.md](CONTRIBUTE.md).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
