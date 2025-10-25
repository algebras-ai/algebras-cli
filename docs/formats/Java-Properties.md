# Java Properties Format Guide

[![Java](https://img.shields.io/badge/Java-ED8B00?style=flat&logo=java&logoColor=white)](https://www.java.com/) [![Spring](https://img.shields.io/badge/Spring-6DB33F?style=flat&logo=spring&logoColor=white)](https://spring.io/)

## Overview

Java Properties files (`.properties`) are used for storing configuration data and localized strings in Java applications. They are widely used in Java ResourceBundle, Spring Boot applications, and enterprise Java applications for internationalization.

## When to Use Java Properties

- **Java Applications**: Native Java applications using ResourceBundle
- **Spring Boot Applications**: Spring Boot apps with i18n support
- **Enterprise Java**: Large-scale Java enterprise applications
- **Configuration Files**: Application configuration and settings
- **Maven/Gradle Projects**: Java projects using build tools
- **Desktop Applications**: Java Swing/JavaFX applications
- **Web Applications**: Java web applications (JSP, Servlets)

## File Structure

Java projects use a specific directory structure for Properties files:

```
src/main/resources/
├── messages.properties      # English (base language)
├── messages_es.properties   # Spanish translations
├── messages_fr.properties   # French translations
├── messages_ru.properties   # Russian translations
└── application.properties   # Application configuration
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "es", "fr", "ru"]
source_files:
  "src/main/resources/messages.properties":
    destination_path: "src/main/resources/messages_%algebras_locale_code%.properties"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Standard Java Project:**
```yaml
source_files:
  "src/main/resources/messages.properties":
    destination_path: "src/main/resources/messages_%algebras_locale_code%.properties"
```

**Spring Boot Project:**
```yaml
source_files:
  "src/main/resources/messages.properties":
    destination_path: "src/main/resources/messages_%algebras_locale_code%.properties"
  "src/main/resources/application.properties":
    destination_path: "src/main/resources/application_%algebras_locale_code%.properties"
```

**Multiple Properties Files:**
```yaml
source_files:
  "src/main/resources/messages.properties":
    destination_path: "src/main/resources/messages_%algebras_locale_code%.properties"
  "src/main/resources/errors.properties":
    destination_path: "src/main/resources/errors_%algebras_locale_code%.properties"
  "src/main/resources/ui.properties":
    destination_path: "src/main/resources/ui_%algebras_locale_code%.properties"
```

**Custom Resources Directory:**
```yaml
source_files:
  "resources/i18n/messages.properties":
    destination_path: "resources/i18n/messages_%algebras_locale_code%.properties"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your Java project directory
cd your-java-project

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

### 1. Properties File Structure

- **Proper formatting**: Use consistent formatting and structure
- **Key naming**: Use descriptive names for property keys
- **Comments**: Add comments for complex properties
- **Encoding**: Use UTF-8 encoding for international characters

```properties
# Application messages
# This file contains all user-facing messages

# Basic application strings
app.title=My Java Application
app.description=A powerful Java application

# Navigation strings
nav.home=Home
nav.about=About
nav.contact=Contact
nav.settings=Settings

# Button strings
button.save=Save
button.cancel=Cancel
button.delete=Delete
button.edit=Edit
```

### 2. Key Naming Conventions

- **Dot notation**: Use dots to separate hierarchical levels
- **Descriptive names**: Use clear, descriptive names
- **Consistent prefixes**: Use consistent prefixes for related properties
- **Lowercase**: Use lowercase with dots for multi-word names

```properties
# Good naming conventions
user.profile.title=User Profile
user.profile.edit.button=Edit Profile
user.profile.save.button=Save Changes
user.profile.cancel.button=Cancel Changes

# Avoid generic names
title=User Profile
button1=Edit Profile
button2=Save Changes
button3=Cancel Changes
```

### 3. String Formatting

- **String formatting**: Use proper string formatting for dynamic content
- **Escape sequences**: Use proper escape sequences for special characters
- **Unicode support**: Use Unicode escape sequences for special characters

```properties
# String formatting with parameters
welcome.message=Welcome, {0}!
item.count=You have {0} items
price.format=Price: ${0}

# Unicode escape sequences
special.characters=Caf\u00e9, na\u00efve, r\u00e9sum\u00e9

# Escape sequences for special characters
quoted.string=This is a \"quoted\" string
newline.string=This is a line with a\nnewline
```

### 4. Comments and Documentation

- **Property comments**: Add comments for complex properties
- **Section comments**: Use comments to group related properties
- **Usage examples**: Include usage examples when helpful

```properties
# ===========================================
# Application Messages
# ===========================================
# This section contains all user-facing messages

# Basic application strings
app.title=My Java Application
app.description=A powerful Java application

# ===========================================
# Navigation Messages
# ===========================================
# Navigation menu items

nav.home=Home
nav.about=About
nav.contact=Contact
nav.settings=Settings

# ===========================================
# Button Messages
# ===========================================
# Common button labels

button.save=Save
button.cancel=Cancel
button.delete=Delete
button.edit=Edit
```

### 5. ResourceBundle Integration

- **Bundle naming**: Use consistent bundle naming conventions
- **Locale support**: Include proper locale support
- **Fallback handling**: Implement proper fallback handling

```properties
# messages.properties (default/fallback)
app.title=My Java Application
welcome.message=Welcome to our application!

# messages_es.properties (Spanish)
app.title=Mi Aplicación Java
welcome.message=¡Bienvenido a nuestra aplicación!

# messages_fr.properties (French)
app.title=Mon Application Java
welcome.message=Bienvenue dans notre application!
```

## Common Use Cases

### Basic Java Application

```properties
# messages.properties
app.title=My Java Application
app.description=A powerful Java application
welcome.message=Welcome to our application!
login.button=Log In
logout.button=Log Out
save.button=Save
cancel.button=Cancel
delete.button=Delete
edit.button=Edit
```

### Spring Boot Application

```properties
# messages.properties
app.title=My Spring Boot Application
app.description=A powerful Spring Boot application
welcome.message=Welcome to our Spring Boot application!
login.button=Log In
logout.button=Log Out
save.button=Save
cancel.button=Cancel
delete.button=Delete
edit.button=Edit

# Error messages
error.validation.required=This field is required
error.validation.email=Please enter a valid email address
error.validation.password=Password must be at least 8 characters

# Success messages
success.operation.completed=Operation completed successfully
success.user.created=User created successfully
success.user.updated=User updated successfully
```

### E-commerce Application

```properties
# messages.properties
app.title=Shopping Application
app.description=A powerful e-commerce application
welcome.message=Welcome to our shopping application!
product.title=Product Details
add.to.cart=Add to Cart
remove.from.cart=Remove from Cart
checkout=Checkout
total.price=Total: ${0}
cart.items.count=You have {0} items in your cart
```

### User Profile Application

```properties
# messages.properties
app.title=User Profile Application
app.description=A user profile management application
user.profile.title=User Profile
user.profile.edit.button=Edit Profile
user.profile.save.button=Save Changes
user.profile.cancel.button=Cancel Changes
user.profile.delete.button=Delete Profile
user.profile.edit.hint=Click to edit your profile
```

## Example Files

### Before Translation (messages.properties)
```properties
# Application Messages
# This file contains all user-facing messages

# Basic application strings
app.title=My Java Application
app.description=A powerful Java application
welcome.message=Welcome to our application!

# Navigation strings
nav.home=Home
nav.about=About
nav.contact=Contact
nav.settings=Settings

# Button strings
button.save=Save
button.cancel=Cancel
button.delete=Delete
button.edit=Edit
button.login=Log In
button.logout=Log Out

# User profile strings
user.profile.title=User Profile
user.profile.edit.hint=Click to edit your profile
user.profile.save.changes=Save Changes
user.profile.cancel.changes=Cancel Changes

# Message strings
message.success=Operation completed successfully
message.error=An error occurred
message.loading=Loading...
message.confirm=Are you sure?
```

### After Translation (messages_es.properties)
```properties
# Application Messages
# This file contains all user-facing messages

# Basic application strings
app.title=Mi Aplicación Java
app.description=Una aplicación Java poderosa
welcome.message=¡Bienvenido a nuestra aplicación!

# Navigation strings
nav.home=Inicio
nav.about=Acerca de
nav.contact=Contacto
nav.settings=Configuración

# Button strings
button.save=Guardar
button.cancel=Cancelar
button.delete=Eliminar
button.edit=Editar
button.login=Iniciar Sesión
button.logout=Cerrar Sesión

# User profile strings
user.profile.title=Perfil de Usuario
user.profile.edit.hint=Haz clic para editar tu perfil
user.profile.save.changes=Guardar Cambios
user.profile.cancel.changes=Cancelar Cambios

# Message strings
message.success=Operación completada exitosamente
message.error=Ocurrió un error
message.loading=Cargando...
message.confirm=¿Estás seguro?
```

## Advanced Features

### 1. String Formatting with Parameters

```properties
# String formatting with positional parameters
welcome.user=Welcome, {0}!
item.count=You have {0} items
price.format=Price: ${0}
date.format=Date: {0,date,short}
number.format=Number: {0,number,currency}
```

### 2. Unicode Support

```properties
# Unicode escape sequences
special.characters=Caf\u00e9, na\u00efve, r\u00e9sum\u00e9
accented.text=H\u00e9llo, w\u00f6rld!
currency.symbol=Price: \u20ac{0}
```

### 3. Multi-line Properties

```properties
# Multi-line properties using backslash
long.message=This is a very long message that spans multiple lines. \
It continues on the next line and can be as long as needed. \
This is useful for detailed descriptions or help text.
```

### 4. Property Inheritance

```properties
# Base properties
common.save=Save
common.cancel=Cancel
common.delete=Delete

# Specific properties that inherit from common
user.save={common.save} User
user.cancel={common.cancel} User
user.delete={common.delete} User
```

## Troubleshooting

### Common Issues

**Properties file parsing errors:**
- Ensure valid properties file format
- Check for proper key-value syntax
- Validate properties file structure before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Save files as UTF-8
- Use Unicode escape sequences for special characters
- Check for BOM (Byte Order Mark)

**ResourceBundle issues:**
- Ensure proper bundle naming conventions
- Check locale-specific file names
- Verify ResourceBundle loading logic

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Java Integration

### ResourceBundle Usage

```java
import java.util.ResourceBundle;
import java.util.Locale;

public class MessageService {
    private ResourceBundle messages;
    
    public MessageService(Locale locale) {
        this.messages = ResourceBundle.getBundle("messages", locale);
    }
    
    public String getMessage(String key) {
        return messages.getString(key);
    }
    
    public String getMessage(String key, Object... args) {
        return MessageFormat.format(messages.getString(key), args);
    }
}
```

### Spring Boot Integration

```java
@Configuration
public class MessageConfig {
    
    @Bean
    public MessageSource messageSource() {
        ResourceBundleMessageSource messageSource = new ResourceBundleMessageSource();
        messageSource.setBasename("messages");
        messageSource.setDefaultEncoding("UTF-8");
        return messageSource;
    }
}
```

## Related Examples

- [Java Example](../../examples/java-app/) - Complete Java setup
- [Spring Boot Example](../../examples/spring-boot-app/) - Spring Boot with i18n
- [Enterprise Java Example](../../examples/enterprise-java-app/) - Enterprise Java application
