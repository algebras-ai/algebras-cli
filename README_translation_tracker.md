# Translation Key Tracker

A tool to track and identify outdated translations in multilingual projects using Git blame.

## Overview

This tool helps you identify outdated translations between language files (such as JSON or YAML files) by using Git blame to determine when keys were last modified. It's particularly useful for projects with multiple language files where you need to ensure translations stay in sync.

## Features

- **Accurate tracking**: Uses Git blame to precisely identify when a translation key was last modified
- **Nested key support**: Works with deeply nested structures in both JSON and YAML files
- **Fast performance**: Efficiently works with repositories of any size, even those with many commits
- **CLI interface**: Simple command-line interface for easy integration into your workflow

## Installation

No additional installation is required beyond having Git available on your system.

## Usage

### Command Line Interface

The tool offers a command-line interface with several subcommands:

#### Find outdated translations

```bash
python -m algebras.utils.git_utils find path/to/en.json path/to/ru.json
```

This command will scan both files and report any keys where the source file (e.g., English) has been updated more recently than the target file (e.g., Russian).

#### Test specific keys

```bash
python -m algebras.utils.git_utils test path/to/en.json path/to/ru.json user.name app.title 
```

This command checks specific keys (in this example, "user.name" and "app.title") and reports detailed information about their modification status.

#### Get last modification date for a key

```bash
python -m algebras.utils.git_utils date path/to/en.json user.profile.name
```

This command shows when a specific key was last modified, including the line number and timestamp.

### Programmatic Usage

You can also use the functions directly in your code:

```python
from algebras.utils.git_utils import find_outdated_translations

# Find all outdated translations
results = find_outdated_translations('path/to/en.json', 'path/to/ru.json')

# Process results
for key, info in results.items():
    print(f"Key {key} needs updating: source changed on {info['source_date']}")
```

## How It Works

1. The tool identifies the exact line number where a translation key is defined
2. It uses Git blame to determine when that line was last modified
3. It compares modification dates between source and target files
4. It reports keys where the source is newer than the target

## Requirements

- Git must be installed and available in your PATH
- Files must be tracked in a Git repository
- Supported file formats: JSON, YAML

## Example Output

```json
{
  "common.buttons.submit": {
    "source_date": "2023-05-15T14:23:45Z",
    "target_date": "2023-01-10T09:12:30Z"
  },
  "user.profile.title": {
    "source_date": "2023-06-02T11:45:12Z",
    "target_date": "2023-05-20T16:30:45Z"
  }
}
```

## Troubleshooting

- **No results returned**: Ensure your files are properly tracked in Git and have a commit history
- **Inaccurate results**: If you've made significant structural changes to your files, Git blame might not correctly identify the last change for a key
- **Error finding keys**: For complex nested structures, you may need to verify the key path using the `date` command first

## License

This tool is released under the same license as the main project. 