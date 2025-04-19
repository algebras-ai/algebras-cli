# Algebras CLI Test Examples

This directory contains example projects with different repository structures to test the functionality of the Algebras CLI tool. These examples allow you to manually validate whether algebras-cli works correctly with various localization setups.

## Available Examples

### 1. Next.js Application (`nextjs-app/`)

A minimal Next.js project structure with JSON-based localization files, similar to what you'd use with libraries like `next-i18next`.

[Go to Next.js Example](./nextjs-app/)

### 2. Django Application (`django-app/`)

A minimal Django project structure with GNU gettext `.po` localization files, which is the standard format used by Django's internationalization system.

[Go to Django Example](./django-app/)

## How to Use These Examples

Each example directory contains:

1. A predefined folder structure with source language files (English)
2. An `.algebras.config` file configured for that specific project structure
3. A detailed README with step-by-step instructions for testing algebras-cli

To test algebras-cli with any of these examples:

1. Set up your OpenAI API key (for AI-powered translations)
2. Navigate to the specific example directory
3. Follow the instructions in that example's README.md file

## Notes

- These examples contain only the minimal structure needed to test the localization functionality
- They do not include actual working applications, only the localization-related files
- The examples are configured with English as the source language and French/Spanish as target languages 