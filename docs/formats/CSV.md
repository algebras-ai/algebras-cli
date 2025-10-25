# CSV Format Guide

[![CSV](https://img.shields.io/badge/CSV-239120?style=flat&logo=csv&logoColor=white)](https://en.wikipedia.org/wiki/Comma-separated_values)

## Overview

CSV (Comma-Separated Values) files are a simple format for storing tabular data, including multi-language translations. They are widely used for spreadsheet-based translation workflows, data import/export, and simple localization projects.

## When to Use CSV

- **Simple Applications**: Basic applications with straightforward translation needs
- **Spreadsheet Editing**: When translators prefer working with Excel or Google Sheets
- **Data Import/Export**: For importing/exporting translation data
- **Multi-language Management**: When you need all languages in one file
- **Translation Agencies**: When working with translation agencies that prefer CSV
- **Quick Prototyping**: For rapid prototyping and testing
- **Data Migration**: For migrating between different translation systems

## File Structure

CSV translation files typically follow this structure:

```
locales/
├── translations.csv      # Multi-language CSV file
└── README.md            # Documentation
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "locales/translations.csv":
    destination_path: "locales/translations_%algebras_locale_code%.csv"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Single CSV File:**
```yaml
source_files:
  "locales/translations.csv":
    destination_path: "locales/translations_%algebras_locale_code%.csv"
```

**Multiple CSV Files:**
```yaml
source_files:
  "locales/messages.csv":
    destination_path: "locales/messages_%algebras_locale_code%.csv"
  "locales/errors.csv":
    destination_path: "locales/errors_%algebras_locale_code%.csv"
  "locales/ui.csv":
    destination_path: "locales/ui_%algebras_locale_code%.csv"
```

**Custom CSV Directory:**
```yaml
source_files:
  "data/i18n/translations.csv":
    destination_path: "data/i18n/translations_%algebras_locale_code%.csv"
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

### 1. CSV File Structure

- **Header row**: Include column headers for clarity
- **Key column**: Use the first column for translation keys
- **Language columns**: Use subsequent columns for different languages
- **Consistent formatting**: Use consistent formatting throughout

```csv
key,en,es,fr,ru
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
welcome.message,Welcome to our app!,¡Bienvenido a nuestra app!,Bienvenue dans notre app!,Добро пожаловать в наше приложение!
login.button,Log In,Iniciar Sesión,Se connecter,Войти
logout.button,Log Out,Cerrar Sesión,Se déconnecter,Выйти
```

### 2. Key Naming Conventions

- **Descriptive keys**: Use clear, descriptive key names
- **Hierarchical structure**: Use dots or underscores for hierarchy
- **Consistent naming**: Use consistent naming conventions
- **Avoid spaces**: Use underscores or dots instead of spaces

```csv
key,en,es,fr,ru
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
user.profile.title,User Profile,Perfil de Usuario,Profil Utilisateur,Профиль Пользователя
user.profile.edit.button,Edit Profile,Editar Perfil,Modifier le Profil,Редактировать Профиль
user.profile.save.button,Save Changes,Guardar Cambios,Enregistrer les Modifications,Сохранить Изменения
```

### 3. Data Formatting

- **Quoted strings**: Use quotes for strings with commas or special characters
- **Escape sequences**: Use proper escape sequences for special characters
- **Unicode support**: Use UTF-8 encoding for international characters
- **Consistent delimiters**: Use consistent delimiters (commas, semicolons, tabs)

```csv
key,en,es,fr,ru
quoted.string,"This is a ""quoted"" string","Esta es una cadena ""entre comillas""","Ceci est une chaîne ""entre guillemets""","Это ""строка в кавычках"""
special.characters,Café, naïve, résumé,Café, naïve, résumé,Café, naïve, résumé,Кафе, наивный, резюме
multiline.string,"This is a multi-line
string that spans
multiple lines","Esta es una cadena
de múltiples líneas
que abarca
varias líneas","Ceci est une chaîne
multi-lignes qui s'étend
sur plusieurs lignes","Это многострочная
строка, которая
охватывает
несколько строк"
```

### 4. Comments and Documentation

- **Comment rows**: Use rows starting with # for comments
- **Section headers**: Use comment rows to separate sections
- **Usage examples**: Include usage examples when helpful

```csv
# Application Messages
# This file contains all user-facing messages

key,en,es,fr,ru
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
app.description,A powerful application,Una aplicación poderosa,Une application puissante,Мощное приложение

# Navigation Messages
# Navigation menu items

key,en,es,fr,ru
nav.home,Home,Inicio,Accueil,Главная
nav.about,About,Acerca de,À propos,О нас
nav.contact,Contact,Contacto,Contact,Контакты
nav.settings,Settings,Configuración,Paramètres,Настройки

# Button Messages
# Common button labels

key,en,es,fr,ru
button.save,Save,Guardar,Enregistrer,Сохранить
button.cancel,Cancel,Cancelar,Annuler,Отмена
button.delete,Delete,Eliminar,Supprimer,Удалить
button.edit,Edit,Editar,Modifier,Редактировать
```

### 5. Data Validation

- **Required fields**: Ensure all required fields are present
- **Data consistency**: Check for data consistency across languages
- **Encoding validation**: Validate UTF-8 encoding
- **Format validation**: Validate CSV format before processing

```csv
key,en,es,fr,ru
# Required fields: key, en (source language)
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
welcome.message,Welcome to our app!,¡Bienvenido a nuestra app!,Bienvenue dans notre app!,Добро пожаловать в наше приложение!
login.button,Log In,Iniciar Sesión,Se connecter,Войти
logout.button,Log Out,Cerrar Sesión,Se déconnecter,Выйти
```

## Common Use Cases

### Basic Application

```csv
key,en,es,fr,ru
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
app.description,A powerful application,Una aplicación poderosa,Une application puissante,Мощное приложение
welcome.message,Welcome to our app!,¡Bienvenido a nuestra app!,Bienvenue dans notre app!,Добро пожаловать в наше приложение!
login.button,Log In,Iniciar Sesión,Se connecter,Войти
logout.button,Log Out,Cerrar Sesión,Se déconnecter,Выйти
save.button,Save,Guardar,Enregistrer,Сохранить
cancel.button,Cancel,Cancelar,Annuler,Отмена
```

### E-commerce Application

```csv
key,en,es,fr,ru
app.title,Shopping App,Aplicación de Compras,Application d'Achat,Приложение для Покупок
product.title,Product Details,Detalles del Producto,Détails du Produit,Детали Товара
add.to.cart,Add to Cart,Añadir al Carrito,Ajouter au Panier,Добавить в Корзину
remove.from.cart,Remove from Cart,Eliminar del Carrito,Retirer du Panier,Удалить из Корзины
checkout,Checkout,Finalizar Compra,Commander,Оформить Заказ
total.price,Total: ${0},Total: ${0},Total: ${0},Итого: ${0}
cart.items.count,You have {0} items in your cart,Tienes {0} artículos en tu carrito,Vous avez {0} articles dans votre panier,У вас {0} товаров в корзине
```

### User Profile Application

```csv
key,en,es,fr,ru
app.title,User Profile App,Aplicación de Perfil de Usuario,Application de Profil Utilisateur,Приложение Профиля Пользователя
user.profile.title,User Profile,Perfil de Usuario,Profil Utilisateur,Профиль Пользователя
user.profile.edit.button,Edit Profile,Editar Perfil,Modifier le Profil,Редактировать Профиль
user.profile.save.button,Save Changes,Guardar Cambios,Enregistrer les Modifications,Сохранить Изменения
user.profile.cancel.button,Cancel Changes,Cancelar Cambios,Annuler les Modifications,Отменить Изменения
user.profile.delete.button,Delete Profile,Eliminar Perfil,Supprimer le Profil,Удалить Профиль
user.profile.edit.hint,Click to edit your profile,Haz clic para editar tu perfil,Cliquez pour modifier votre profil,Нажмите, чтобы редактировать профиль
```

## Example Files

### Before Translation (translations.csv)
```csv
key,en,es,fr,ru
app.title,My Application,My Application,My Application,My Application
app.description,A powerful application,A powerful application,A powerful application,A powerful application
welcome.message,Welcome to our app!,Welcome to our app!,Welcome to our app!,Welcome to our app!
login.button,Log In,Log In,Log In,Log In
logout.button,Log Out,Log Out,Log Out,Log Out
save.button,Save,Save,Save,Save
cancel.button,Cancel,Cancel,Cancel,Cancel
delete.button,Delete,Delete,Delete,Delete
edit.button,Edit,Edit,Edit,Edit
user.profile.title,User Profile,User Profile,User Profile,User Profile
user.profile.edit.hint,Click to edit your profile,Click to edit your profile,Click to edit your profile,Click to edit your profile
success.message,Operation completed successfully,Operation completed successfully,Operation completed successfully,Operation completed successfully
error.message,An error occurred,An error occurred,An error occurred,An error occurred
loading.message,Loading...,Loading...,Loading...,Loading...
```

### After Translation (translations.csv)
```csv
key,en,es,fr,ru
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
app.description,A powerful application,Una aplicación poderosa,Une application puissante,Мощное приложение
welcome.message,Welcome to our app!,¡Bienvenido a nuestra app!,Bienvenue dans notre app!,Добро пожаловать в наше приложение!
login.button,Log In,Iniciar Sesión,Se connecter,Войти
logout.button,Log Out,Cerrar Sesión,Se déconnecter,Выйти
save.button,Save,Guardar,Enregistrer,Сохранить
cancel.button,Cancel,Cancelar,Annuler,Отмена
delete.button,Delete,Eliminar,Supprimer,Удалить
edit.button,Edit,Editar,Modifier,Редактировать
user.profile.title,User Profile,Perfil de Usuario,Profil Utilisateur,Профиль Пользователя
user.profile.edit.hint,Click to edit your profile,Haz clic para editar tu perfil,Cliquez pour modifier votre profil,Нажмите, чтобы редактировать профиль
success.message,Operation completed successfully,Operación completada exitosamente,Opération terminée avec succès,Операция завершена успешно
error.message,An error occurred,Ocurrió un error,Une erreur s'est produite,Произошла ошибка
loading.message,Loading...,Cargando...,Chargement...,Загрузка...
```

## Advanced Features

### 1. Multi-line Strings

```csv
key,en,es,fr,ru
multiline.description,"This is a multi-line
description that spans
multiple lines","Esta es una descripción
de múltiples líneas
que abarca
varias líneas","Ceci est une description
multi-lignes qui s'étend
sur plusieurs lignes","Это многострочное
описание, которое
охватывает
несколько строк"
```

### 2. Special Characters and Escaping

```csv
key,en,es,fr,ru
quoted.string,"This is a ""quoted"" string","Esta es una cadena ""entre comillas""","Ceci est une chaîne ""entre guillemets""","Это ""строка в кавычках"""
special.characters,Café, naïve, résumé,Café, naïve, résumé,Café, naïve, résumé,Кафе, наивный, резюме
currency.symbol,Price: $100,Price: $100,Prix: 100 €,Цена: 100 ₽
```

### 3. Data Validation

```csv
key,en,es,fr,ru
# Required fields: key, en (source language)
app.title,My Application,Mi Aplicación,Mon Application,Мое Приложение
welcome.message,Welcome to our app!,¡Bienvenido a nuestra app!,Bienvenue dans notre app!,Добро пожаловать в наше приложение!
login.button,Log In,Iniciar Sesión,Se connecter,Войти
logout.button,Log Out,Cerrar Sesión,Se déconnecter,Выйти
```

## Troubleshooting

### Common Issues

**CSV parsing errors:**
- Ensure valid CSV format
- Check for proper quoting of strings with commas
- Validate CSV structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Save files as UTF-8
- Check for BOM (Byte Order Mark)
- Verify special characters are properly encoded

**Data consistency issues:**
- Ensure all rows have the same number of columns
- Check for missing values in required fields
- Validate data types and formats

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## CSV vs Other Formats

### Advantages of CSV

- **Simple format**: Easy to understand and edit
- **Spreadsheet compatibility**: Works well with Excel and Google Sheets
- **Universal support**: Supported by most applications
- **Human-readable**: Easy to read and edit manually
- **Lightweight**: Small file sizes

### Disadvantages of CSV

- **Limited structure**: No support for complex data structures
- **No metadata**: Limited support for additional information
- **Escaping issues**: Can be problematic with special characters
- **No type information**: No built-in data type support
- **Limited validation**: No built-in validation capabilities

## Related Examples

- [CSV Example](../../examples/csv-translations/) - Complete CSV setup
- [Spreadsheet Example](../../examples/spreadsheet-translations/) - Spreadsheet-based workflow
- [Data Migration Example](../../examples/data-migration/) - Migrating between formats
