# Algebras CLI

[![PyPI version](https://badge.fury.io/py/algebras-cli.svg)](https://badge.fury.io/py/algebras-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Tests](https://github.com/algebras-ai/algebras-cli/actions/workflows/python-tests.yml/badge.svg)](https://github.com/algebras-ai/algebras-cli/actions/workflows/python-tests.yml)


> Powerful AI-driven localization tool for your applications

![Algebras CLI Demo](imgs/demo-font-size-30.gif)

## Overview

Algebras CLI is a Python package that simplifies application localization by tracking translation status and automating updates. Powered by AI, it helps you manage translations across multiple languages with minimal effort.

## Supported File Formats

Algebras CLI supports a wide range of localization file formats:

- **JSON** (`.json`) - Common for web applications (Next.js, React, etc.)
- **YAML/YML** (`.yaml`, `.yml`) - Alternative format for configuration files
- **TypeScript** (`.ts`) - TypeScript translation files
- **Android XML** (`.xml`) - Android string resources in `values/` directories
- **iOS Strings** (`.strings`) - iOS localization files
- **iOS StringsDict** (`.stringsdict`) - iOS pluralization files
- **Gettext** (`.po`) - GNU gettext files (Django, etc.)
- **HTML** (`.html`) - HTML files with translatable content

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

# Performance tuning
algebras translate --batch-size 10 --max-parallel-batches 3
```

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

# Set the model for Algebras AI provider
algebras configure --model gpt-4

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

## Configuration

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

### Getting Help

- Check the [GitHub Issues](https://github.com/algebras-ai/algebras-cli/issues) for known problems
- Review the [examples](examples/) directory for usage patterns
- Ensure you're using the latest version: `pip install --upgrade algebras-cli`

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
