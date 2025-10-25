# XLSX Format Guide

[![Excel](https://img.shields.io/badge/Excel-217346?style=flat&logo=microsoft-excel&logoColor=white)](https://www.microsoft.com/en-us/microsoft-365/excel)

## Overview

XLSX (Excel Spreadsheet) files are a powerful format for storing multi-language translations with rich formatting, formulas, and metadata. They are widely used in enterprise translation workflows, professional translation agencies, and complex localization projects.

## When to Use XLSX

- **Enterprise Applications**: Large-scale applications with complex translation needs
- **Professional Translation**: When working with translation agencies
- **Rich Formatting**: When you need formatting, colors, and styling
- **Complex Data**: When dealing with complex translation data structures
- **Collaborative Work**: When multiple translators need to work on the same file
- **Data Analysis**: When you need to analyze translation data
- **Reporting**: When generating translation reports and metrics

## File Structure

XLSX translation files typically follow this structure:

```
locales/
├── translations.xlsx      # Multi-language XLSX file
└── README.md             # Documentation
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "locales/translations.xlsx":
    destination_path: "locales/translations_%algebras_locale_code%.xlsx"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Single XLSX File:**
```yaml
source_files:
  "locales/translations.xlsx":
    destination_path: "locales/translations_%algebras_locale_code%.xlsx"
```

**Multiple XLSX Files:**
```yaml
source_files:
  "locales/messages.xlsx":
    destination_path: "locales/messages_%algebras_locale_code%.xlsx"
  "locales/errors.xlsx":
    destination_path: "locales/errors_%algebras_locale_code%.xlsx"
  "locales/ui.xlsx":
    destination_path: "locales/ui_%algebras_locale_code%.xlsx"
```

**Custom XLSX Directory:**
```yaml
source_files:
  "data/i18n/translations.xlsx":
    destination_path: "data/i18n/translations_%algebras_locale_code%.xlsx"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your project directory
cd your-project

# Initialize algebras-cli
algebras init

# Add target languages
algebras add es fr ru
```

### 2. Basic Translation

```bash
# Translate all missing keys
algebras translate

# Translate specific language
algebras translate --language es

# Force translation (even if up-to-date)
algebras translate --force
```

### 3. Update Translations

```bash
# Update missing keys only
algebras update

# Update specific language
algebras update --language fr

# Full translation update
algebras update --full
```

### 4. Check Status

```bash
# Check all languages
algebras status

# Check specific language
algebras status --language ru
```

### 5. Review Translations

```bash
# Review all languages
algebras review

# Review specific language
algebras review --language es
```

## Best Practices

### 1. XLSX File Structure

- **Header row**: Include column headers for clarity
- **Key column**: Use the first column for translation keys
- **Language columns**: Use subsequent columns for different languages
- **Metadata columns**: Include additional columns for context, notes, etc.

| Key | EN | ES | FR | RU | Context | Notes |
|-----|----|----|----|----|---------|-------|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение | App | Main title |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! | Home | Welcome message |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти | Auth | Login button |

### 2. Key Naming Conventions

- **Descriptive keys**: Use clear, descriptive key names
- **Hierarchical structure**: Use dots or underscores for hierarchy
- **Consistent naming**: Use consistent naming conventions
- **Avoid spaces**: Use underscores or dots instead of spaces

| Key | EN | ES | FR | RU |
|-----|----|----|----|----|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение |
| user.profile.title | User Profile | Perfil de Usuario | Profil Utilisateur | Профиль Пользователя |
| user.profile.edit.button | Edit Profile | Editar Perfil | Modifier le Profil | Редактировать Профиль |
| user.profile.save.button | Save Changes | Guardar Cambios | Enregistrer les Modifications | Сохранить Изменения |

### 3. Data Formatting

- **Rich formatting**: Use Excel's formatting capabilities
- **Colors**: Use colors to highlight different types of content
- **Borders**: Use borders to separate sections
- **Fonts**: Use different fonts for different content types

| Key | EN | ES | FR | RU | Status |
|-----|----|----|----|----|--------|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение | ✅ |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! | ✅ |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти | ✅ |

### 4. Comments and Documentation

- **Cell comments**: Use Excel's comment feature for additional information
- **Sheet documentation**: Include documentation sheets
- **Usage examples**: Include usage examples when helpful

| Key | EN | ES | FR | RU | Context | Notes |
|-----|----|----|----|----|---------|-------|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение | App | Main application title |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! | Home | Welcome message displayed on home screen |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти | Auth | Button for user authentication |

### 5. Data Validation

- **Required fields**: Ensure all required fields are present
- **Data consistency**: Check for data consistency across languages
- **Format validation**: Validate data formats before processing
- **Length validation**: Check for appropriate string lengths

| Key | EN | ES | FR | RU | Max Length | Status |
|-----|----|----|----|----|------------|--------|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение | 50 | ✅ |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! | 100 | ✅ |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти | 20 | ✅ |

## Common Use Cases

### Basic Application

| Key | EN | ES | FR | RU |
|-----|----|----|----|----|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение |
| app.description | A powerful application | Una aplicación poderosa | Une application puissante | Мощное приложение |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти |
| logout.button | Log Out | Cerrar Sesión | Se déconnecter | Выйти |
| save.button | Save | Guardar | Enregistrer | Сохранить |
| cancel.button | Cancel | Cancelar | Annuler | Отмена |

### E-commerce Application

| Key | EN | ES | FR | RU |
|-----|----|----|----|----|
| app.title | Shopping App | Aplicación de Compras | Application d'Achat | Приложение для Покупок |
| product.title | Product Details | Detalles del Producto | Détails du Produit | Детали Товара |
| add.to.cart | Add to Cart | Añadir al Carrito | Ajouter au Panier | Добавить в Корзину |
| remove.from.cart | Remove from Cart | Eliminar del Carrito | Retirer du Panier | Удалить из Корзины |
| checkout | Checkout | Finalizar Compra | Commander | Оформить Заказ |
| total.price | Total: ${0} | Total: ${0} | Total: ${0} | Итого: ${0} |
| cart.items.count | You have {0} items in your cart | Tienes {0} artículos en tu carrito | Vous avez {0} articles dans votre panier | У вас {0} товаров в корзине |

### User Profile Application

| Key | EN | ES | FR | RU |
|-----|----|----|----|----|
| app.title | User Profile App | Aplicación de Perfil de Usuario | Application de Profil Utilisateur | Приложение Профиля Пользователя |
| user.profile.title | User Profile | Perfil de Usuario | Profil Utilisateur | Профиль Пользователя |
| user.profile.edit.button | Edit Profile | Editar Perfil | Modifier le Profil | Редактировать Профиль |
| user.profile.save.button | Save Changes | Guardar Cambios | Enregistrer les Modifications | Сохранить Изменения |
| user.profile.cancel.button | Cancel Changes | Cancelar Cambios | Annuler les Modifications | Отменить Изменения |
| user.profile.delete.button | Delete Profile | Eliminar Perfil | Supprimer le Profil | Удалить Профиль |
| user.profile.edit.hint | Click to edit your profile | Haz clic para editar tu perfil | Cliquez pour modifier votre profil | Нажмите, чтобы редактировать профиль |

## Example Files

### Before Translation (translations.xlsx)

| Key | EN | ES | FR | RU |
|-----|----|----|----|----|
| app.title | My Application | My Application | My Application | My Application |
| app.description | A powerful application | A powerful application | A powerful application | A powerful application |
| welcome.message | Welcome to our app! | Welcome to our app! | Welcome to our app! | Welcome to our app! |
| login.button | Log In | Log In | Log In | Log In |
| logout.button | Log Out | Log Out | Log Out | Log Out |
| save.button | Save | Save | Save | Save |
| cancel.button | Cancel | Cancel | Cancel | Cancel |
| delete.button | Delete | Delete | Delete | Delete |
| edit.button | Edit | Edit | Edit | Edit |
| user.profile.title | User Profile | User Profile | User Profile | User Profile |
| user.profile.edit.hint | Click to edit your profile | Click to edit your profile | Click to edit your profile | Click to edit your profile |
| success.message | Operation completed successfully | Operation completed successfully | Operation completed successfully | Operation completed successfully |
| error.message | An error occurred | An error occurred | An error occurred | An error occurred |
| loading.message | Loading... | Loading... | Loading... | Loading... |

### After Translation (translations.xlsx)

| Key | EN | ES | FR | RU |
|-----|----|----|----|----|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение |
| app.description | A powerful application | Una aplicación poderosa | Une application puissante | Мощное приложение |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти |
| logout.button | Log Out | Cerrar Sesión | Se déconnecter | Выйти |
| save.button | Save | Guardar | Enregistrer | Сохранить |
| cancel.button | Cancel | Cancelar | Annuler | Отмена |
| delete.button | Delete | Eliminar | Supprimer | Удалить |
| edit.button | Edit | Editar | Modifier | Редактировать |
| user.profile.title | User Profile | Perfil de Usuario | Profil Utilisateur | Профиль Пользователя |
| user.profile.edit.hint | Click to edit your profile | Haz clic para editar tu perfil | Cliquez pour modifier votre profil | Нажмите, чтобы редактировать профиль |
| success.message | Operation completed successfully | Operación completada exitosamente | Opération terminée avec succès | Операция завершена успешно |
| error.message | An error occurred | Ocurrió un error | Une erreur s'est produite | Произошла ошибка |
| loading.message | Loading... | Cargando... | Chargement... | Загрузка... |

## Advanced Features

### 1. Rich Formatting

| Key | EN | ES | FR | RU | Status |
|-----|----|----|----|----|--------|
| app.title | **My Application** | **Mi Aplicación** | **Mon Application** | **Мое Приложение** | ✅ |
| welcome.message | *Welcome to our app!* | *¡Bienvenido a nuestra app!* | *Bienvenue dans notre app!* | *Добро пожаловать в наше приложение!* | ✅ |
| login.button | `Log In` | `Iniciar Sesión` | `Se connecter` | `Войти` | ✅ |

### 2. Data Validation

| Key | EN | ES | FR | RU | Max Length | Status |
|-----|----|----|----|----|------------|--------|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение | 50 | ✅ |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! | 100 | ✅ |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти | 20 | ✅ |

### 3. Metadata and Context

| Key | EN | ES | FR | RU | Context | Notes | Priority |
|-----|----|----|----|----|---------|-------|----------|
| app.title | My Application | Mi Aplicación | Mon Application | Мое Приложение | App | Main title | High |
| welcome.message | Welcome to our app! | ¡Bienvenido a nuestra app! | Bienvenue dans notre app! | Добро пожаловать в наше приложение! | Home | Welcome message | High |
| login.button | Log In | Iniciar Sesión | Se connecter | Войти | Auth | Login button | Medium |

## Troubleshooting

### Common Issues

**XLSX parsing errors:**
- Ensure valid XLSX format
- Check for proper file structure
- Validate XLSX file before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Save files as UTF-8
- Check for BOM (Byte Order Mark)
- Verify special characters are properly encoded

**Formatting issues:**
- Check for complex formatting that might cause issues
- Ensure consistent formatting across languages
- Validate data types and formats

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## XLSX vs Other Formats

### Advantages of XLSX

- **Rich formatting**: Support for colors, fonts, borders, etc.
- **Complex data**: Support for complex data structures
- **Collaboration**: Multiple users can work on the same file
- **Analysis**: Built-in data analysis and reporting tools
- **Professional**: Widely used in professional translation workflows
- **Metadata**: Support for additional metadata and context

### Disadvantages of XLSX

- **File size**: Larger file sizes compared to other formats
- **Complexity**: More complex to parse and process
- **Dependencies**: Requires Excel or compatible software
- **Version compatibility**: Potential issues with different Excel versions
- **Performance**: Slower processing compared to simpler formats

## Related Examples

- [XLSX Example](../../examples/xlsx-translations/) - Complete XLSX setup
- [Enterprise Example](../../examples/enterprise-translations/) - Enterprise translation workflow
- [Professional Example](../../examples/professional-translations/) - Professional translation agency workflow
