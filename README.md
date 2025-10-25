# Algebras CLI

[![PyPI version](https://badge.fury.io/py/algebras-cli.svg)](https://badge.fury.io/py/algebras-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Tests](https://github.com/algebras-ai/algebras-cli/actions/workflows/python-tests.yml/badge.svg)](https://github.com/algebras-ai/algebras-cli/actions/workflows/python-tests.yml)


> Powerful AI-driven localization tool for your applications

![Algebras CLI Demo](imgs/demo-font-size-30.gif)

## Overview

Algebras CLI is a Python package that simplifies application localization by tracking translation status and automating updates. Powered by AI, it helps you manage translations across multiple languages with minimal effort.

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
algebras init
```


### Add a new language to your application

```bash
algebras add <language>
```


### Translate your application

```bash
algebras translate
```


### Update your translations

```bash
algebras update
```


### Review your translations

```bash
algebras review
```


### Check the status of your translations

```bash
algebras status
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
```

**Note:** Source file mappings are now configured directly in the `.algebras.config` file. Use `algebras init --force` to regenerate your configuration with the new format.

### Run the CI pipeline

To be done.

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



## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

### Development Setup

1. Clone the repository
2. Install the package in development mode:

```bash
pip install -e .
```

3. Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

### Running Tests

To run the tests:

```bash
python tests/run_tests.py
```

Or use pytest directly:

```bash
pytest
```

For test coverage reports:

```bash
pytest --cov=algebras --cov-report=term --cov-report=html
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
