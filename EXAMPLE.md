# Algebras CLI Example Usage

This document demonstrates how to use Algebras CLI for localizing your application.

## Basic Workflow

### 1. Initialize a New Project

```bash
algebras init
```

This will create a `.algebras.config` file in your current directory with default settings:

```yaml
languages:
- en
path_rules:
- '**/*.json'
- '**/*.yaml'
- '!**/node_modules/**'
- '!**/build/**'
api:
  provider: openai
  model: gpt-4
```

### 2. Add Target Languages

```bash
algebras add fr  # Add French
algebras add es  # Add Spanish
algebras add de  # Add German
```

### 3. Create Example Source Files

Create a file called `messages.en.json` with the following content:

```json
{
  "welcome": "Welcome to our application!",
  "login": {
    "title": "Login",
    "username": "Username",
    "password": "Password",
    "submit": "Sign In",
    "forgot_password": "Forgot your password?"
  },
  "errors": {
    "required": "This field is required",
    "invalid_credentials": "Invalid username or password"
  }
}
```

### 4. Check Translation Status

```bash
algebras status
```

This will show you that French, Spanish, and German translations are missing.

### 5. Translate Your Application

Make sure you have set your OpenAI API key:

```bash
export OPENAI_API_KEY=your-api-key-here
```

Then run:

```bash
algebras translate
```

This will generate `messages.fr.json`, `messages.es.json`, and `messages.de.json` with translated content.

### 6. Update Translations

If you update the source file `messages.en.json`, you can update the translations:

```bash
algebras update
```

### 7. Review Translations

```bash
algebras review fr  # Review French translations
```

## Example Project

A simple example project structure might look like:

```
my-app/
├── .algebras.config
├── locales/
│   ├── messages.en.json
│   ├── messages.fr.json
│   ├── messages.es.json
│   └── messages.de.json
└── app/
    ├── index.html
    └── ... other application files
```

## Tips

- Use descriptive keys in your JSON files to help the AI understand the context
- The first language in your config is considered the source language
- You can use `algebras translate --language fr` to translate only to a specific language
- The CLI automatically detects when translations are out of date based on file modification times 