# Contributing to Algebras CLI

Thank you for your interest in contributing to Algebras CLI! This document provides guidelines and information for contributors.

## Table of Contents

- [Project Overview](#project-overview)
- [Development Setup](#development-setup)
- [Code Structure](#code-structure)
- [Testing Guidelines](#testing-guidelines)
- [Code Style Guidelines](#code-style-guidelines)
- [Adding New File Format Support](#adding-new-file-format-support)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Project Overview

Algebras CLI is a Python package that simplifies application localization by tracking translation status and automating updates. It's powered by AI and helps manage translations across multiple languages with minimal effort.

### Key Features

- **Multi-format support**: JSON, YAML, TypeScript, Android XML, iOS strings, Gettext, HTML
- **AI-powered translations**: Using Algebras AI API
- **Git integration**: Tracks changes and validates translations
- **Glossary management**: Consistent terminology across translations
- **CI/CD support**: Built-in CI checks for translation consistency
- **Batch processing**: Optimized for large translation workloads

## Development Setup

### Prerequisites

- Python 3.7 or higher
- Git
- Virtual environment (recommended)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/algebras-ai/algebras-cli.git
   cd algebras-cli
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode:**
   ```bash
   pip install -e .
   ```

4. **Install development dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

5. **Set up environment variables:**
   ```bash
   export ALGEBRAS_API_KEY=your_api_key
   ```

### Verifying Setup

Run the tests to ensure everything is working:

```bash
python tests/run_tests.py
```

Or use pytest directly:

```bash
pytest
```

## Code Structure

```
algebras-cli/
├── algebras/                    # Main package
│   ├── cli.py                  # CLI entry point and command definitions
│   ├── config.py               # Configuration management
│   ├── commands/               # Command implementations
│   │   ├── init_command.py
│   │   ├── add_command.py
│   │   ├── translate_command.py
│   │   ├── update_command.py
│   │   ├── review_command.py
│   │   ├── status_command.py
│   │   ├── configure_command.py
│   │   └── glossary_push_command.py
│   ├── services/               # Core services
│   │   ├── translator.py       # AI translation service
│   │   ├── file_scanner.py     # File discovery and scanning
│   │   └── glossary_service.py # Glossary management
│   └── utils/                  # Utility modules
│       ├── android_xml_handler.py
│       ├── ios_strings_handler.py
│       ├── po_handler.py
│       ├── html_handler.py
│       ├── git_utils.py
│       └── ...
├── tests/                      # Test suite
├── examples/                   # Usage examples
└── docs/                      # Documentation
```

### Key Components

- **CLI Layer** (`cli.py`): Command definitions and argument parsing
- **Command Layer** (`commands/`): Business logic for each command
- **Service Layer** (`services/`): Core functionality (translation, file scanning)
- **Utils Layer** (`utils/`): File format handlers and utilities

## Testing Guidelines

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_translator.py

# Run with coverage
pytest --cov=algebras --cov-report=term --cov-report=html

# Run with verbose output
pytest -v
```

### Test Structure

- **Unit tests**: Test individual functions and methods
- **Integration tests**: Test command execution and file operations
- **Mock external dependencies**: API calls, file system operations

### Writing Tests

1. **Test file naming**: `test_<module_name>.py`
2. **Test function naming**: `test_<function_description>`
3. **Use fixtures** for common setup/teardown
4. **Mock external dependencies** (API calls, file operations)
5. **Test both success and failure cases**

Example test structure:

```python
def test_translate_command_success():
    """Test successful translation command execution."""
    # Arrange
    mock_config = Mock()
    mock_translator = Mock()
    
    # Act
    result = translate_command.execute("fr")
    
    # Assert
    assert result is None  # Command should complete without error
```

## Code Style Guidelines

### Python Style

- Follow **PEP 8** style guidelines
- Use **type hints** for function parameters and return values
- Use **docstrings** for all public functions and classes
- Keep functions **small and focused** (single responsibility)
- Use **meaningful variable names**

### Code Organization

- **One class per file** (except for small utility classes)
- **Group related functions** in modules
- **Import order**: standard library, third-party, local imports
- **Use absolute imports** when possible

### Documentation

- **Docstrings**: Use Google-style docstrings
- **Comments**: Explain "why", not "what"
- **README updates**: Update documentation for new features

Example docstring:

```python
def translate_file(source_file: str, target_file: str, target_lang: str) -> None:
    """Translate a single file from source to target language.
    
    Args:
        source_file: Path to the source language file
        target_file: Path to the target language file
        target_lang: Target language code (e.g., 'fr', 'es')
        
    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If file format is not supported
    """
```

## Adding New File Format Support

To add support for a new file format:

1. **Create handler module** in `algebras/utils/`:
   ```python
   # algebras/utils/new_format_handler.py
   
   def read_new_format_file(file_path: str) -> Dict[str, Any]:
       """Read new format file and return dictionary."""
       pass
   
   def write_new_format_file(file_path: str, data: Dict[str, Any]) -> None:
       """Write dictionary to new format file."""
       pass
   ```

2. **Update file detection** in `file_scanner.py`:
   ```python
   # Add file extension to supported patterns
   specific_locale_patterns = [
       # ... existing patterns
       "**/*.newformat",
   ]
   ```

3. **Update translation command** in `translate_command.py`:
   ```python
   # Add format handling in execute function
   elif source_file.endswith(".newformat"):
       source_content = read_new_format_file(source_file)
       target_content = read_new_format_file(target_file)
   ```

4. **Add tests** for the new format handler
5. **Update documentation** (README.md, examples)

## Pull Request Process

### Before Submitting

1. **Fork the repository** and create a feature branch
2. **Write tests** for your changes
3. **Run the test suite** to ensure nothing is broken
4. **Update documentation** if needed
5. **Check code style** with linters

### Pull Request Guidelines

1. **Clear title**: Describe what the PR does
2. **Detailed description**: Explain changes and motivation
3. **Link issues**: Reference related issues
4. **Small, focused changes**: One feature/fix per PR
5. **Update tests**: Include tests for new functionality

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

## Issue Reporting

### Before Creating an Issue

1. **Search existing issues** to avoid duplicates
2. **Check documentation** and examples
3. **Try latest version** to ensure issue still exists

### Issue Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command '...'
2. See error

**Expected behavior**
What you expected to happen.

**Environment**
- OS: [e.g., macOS, Windows, Linux]
- Python version: [e.g., 3.8.5]
- Algebras CLI version: [e.g., 0.1.0]

**Additional context**
Any other context about the problem.
```

### Issue Types

- **Bug reports**: Something isn't working as expected
- **Feature requests**: Suggest new functionality
- **Documentation**: Improve or add documentation
- **Questions**: Ask for help or clarification

## Communication

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Requests**: For code contributions

## License

By contributing to Algebras CLI, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Algebras CLI! 🚀
