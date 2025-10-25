# Django Example for Algebras CLI

This is a minimal Django project structure to test Algebras CLI functionality. The project contains localization files in GNU gettext `.po` format, which is the standard format for Django's internationalization system.

## Project Structure

```
django-app/
├── .algebras.config                 # Algebras CLI configuration
├── locale/                          # Localization files directory
│   ├── en/                          # English locales (source)
│   │   └── LC_MESSAGES/             
│   │       └── django.po            # English translations
│   ├── fr/                          # French locales (to be managed by algebras-cli)
│   │   └── LC_MESSAGES/
│   │       └── django.po            # Will be created/updated by algebras-cli
│   └── es/                          # Spanish locales (to be managed by algebras-cli)
│       └── LC_MESSAGES/
│           └── django.po            # Will be created/updated by algebras-cli
└── README.md                        # This file
```

## Testing Algebras CLI

Follow these steps to test the Algebras CLI with this example:

1. **Set up your Algebras AI API key** (if you plan to use AI translation):

```bash
export ALGEBRAS_API_KEY=your-api-key-here
```

2. **Check the status of translations**:

```bash
cd examples/django-app
algebras status
```

This should show that French and Spanish translations are missing or outdated.

3. **Generate translations**:

```bash
algebras translate
```

This should create or update the French and Spanish translation files in their respective `locale/*/LC_MESSAGES/django.po` files.

4. **Check the status again**:

```bash
algebras status
```

Now all translations should be up-to-date.

5. **Make changes to the source file**:

Edit `locale/en/LC_MESSAGES/django.po` to add or modify some translations.

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

- The `.algebras.config` file is configured to look for .po files in the `locale` directory
- English (en) is set as the source language
- French (fr) and Spanish (es) are set as target languages
- In a real Django project, you would typically run `django-admin makemessages` to extract strings from your code into .po files, and then `django-admin compilemessages` to compile .po files to .mo files after translation 