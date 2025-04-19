# Next.js Example for Algebras CLI

This is a minimal Next.js project structure to test Algebras CLI functionality. The project contains localization files in JSON format, which is common for Next.js applications using libraries like `next-i18next`.

## Project Structure

```
nextjs-app/
├── .algebras.config         # Algebras CLI configuration
├── public/
│   └── locales/             # Localization files directory
│       ├── en/              # English locales (source)
│       │   └── common.json  # English translations
│       ├── fr/              # French locales (to be managed by algebras-cli)
│       └── es/              # Spanish locales (to be managed by algebras-cli)
└── README.md                # This file
```

## Testing Algebras CLI

Follow these steps to test the Algebras CLI with this example:

1. **Set up your OpenAI API key** (if you plan to use AI translation):

```bash
export OPENAI_API_KEY=your-api-key-here
```

2. **Check the status of translations**:

```bash
cd examples/nextjs-app
algebras status
```

This should show that French and Spanish translations are missing or outdated.

3. **Generate translations**:

```bash
algebras translate
```

This should create or update the French and Spanish translation files in `public/locales/fr/common.json` and `public/locales/es/common.json`.

4. **Check the status again**:

```bash
algebras status
```

Now all translations should be up-to-date.

5. **Make changes to the source file**:

Edit `public/locales/en/common.json` to add or modify some translations.

6. **Update translations**:

```bash
algebras update
```

This should update the French and Spanish translation files with the new or modified content.

7. **Review translations**:

```bash
algebras review fr  # Review French translations
algebras review es  # Review Spanish translations
```

## Notes

- The `.algebras.config` file is configured to look for JSON files in the `public/locales` directory
- English (en) is set as the source language
- French (fr) and Spanish (es) are set as target languages 