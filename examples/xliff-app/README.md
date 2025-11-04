# XLIFF (.xlf) Example

This example demonstrates translating Angular-style XLIFF 1.2 files with Algebras CLI.

## Files

- `translations/messages.en.xlf` — source XLIFF
- `.algebras.config` — config mapping source to destination files

## Usage

```bash
# From repo root
algebras -f examples/xliff-app/.algebras.config translate

# Translate only French
algebras -f examples/xliff-app/.algebras.config translate --language fr
```

After running, translated files will appear as:

- `examples/xliff-app/translations/messages.fr.xlf`
- `examples/xliff-app/translations/messages.es.xlf`



