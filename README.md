# Algebras CLI

[![PyPI version](https://badge.fury.io/py/algebras-cli.svg)](https://badge.fury.io/py/algebras-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Powerful AI-driven localization tool for your applications

## Overview

Algebras CLI is a Python package that simplifies application localization by tracking translation status and automating updates. Powered by AI, it helps you manage translations across multiple languages with minimal effort.

## Installation

```bash
pip install algebras-cli
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


### Run the CI pipeline

To be done.

## Configuration

### .algebras.config

The `.algebras.config` file is used to configure the Algebras CLI. It contains the following sections:

- `languages`: List of languages to translate the application into.
- `path_rules`: List of path rules to find localization files.
- `api`: API configuration for translation providers:
  - `provider`: The translation provider to use. Supported values:
    - `openai`: Use OpenAI's GPT models for translation (requires `OPENAI_API_KEY` environment variable)
    - `algebras-ai`: Use Algebras AI translation API (requires `ALGEBRAS_API_KEY` environment variable)
  - `model`: The model to use (for OpenAI provider)



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