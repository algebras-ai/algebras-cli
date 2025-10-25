# HTML Format Guide

[![HTML](https://img.shields.io/badge/HTML-E34F26?style=flat&logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/HTML)

## Overview

HTML files with translatable content are used for static websites, landing pages, and documentation sites that need to be localized. Algebras CLI can extract translatable text from HTML files and create translated versions.

## When to Use HTML

- **Static Websites**: Landing pages, marketing sites, documentation
- **Email Templates**: HTML email templates for different languages
- **Documentation Sites**: Technical documentation that needs translation
- **Landing Pages**: Marketing pages with multiple language versions
- **Email Campaigns**: Multi-language email marketing campaigns
- **Simple Websites**: Basic websites without complex frameworks

## File Structure

HTML files with translatable content typically follow this structure:

```html
<!-- en.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Our Application</title>
</head>
<body>
    <header>
        <h1>Welcome to Our Application</h1>
        <nav>
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    
    <main>
        <section id="home">
            <h2>Welcome to Our Amazing Application</h2>
            <p>This is a powerful tool that will help you achieve your goals.</p>
            <button>Get Started</button>
        </section>
        
        <section id="about">
            <h2>About Us</h2>
            <p>We are a team of passionate developers creating amazing software.</p>
        </section>
    </main>
    
    <footer>
        <p>&copy; 2024 Our Company. All rights reserved.</p>
    </footer>
</body>
</html>
```

## Configuration

### .algebras.config Setup

```yaml
languages: ["en", "fr", "es", "de"]
source_files:
  "public/index.html":
    destination_path: "public/index.%algebras_locale_code%.html"
  "templates/landing.html":
    destination_path: "templates/landing.%algebras_locale_code%.html"
api:
  provider: "algebras-ai"
  normalize_strings: true
```

### Common Directory Structures

**Static Website:**
```yaml
source_files:
  "index.html":
    destination_path: "index.%algebras_locale_code%.html"
  "about.html":
    destination_path: "about.%algebras_locale_code%.html"
```

**Email Templates:**
```yaml
source_files:
  "templates/welcome.html":
    destination_path: "templates/welcome.%algebras_locale_code%.html"
  "templates/newsletter.html":
    destination_path: "templates/newsletter.%algebras_locale_code%.html"
```

**Documentation Site:**
```yaml
source_files:
  "docs/index.html":
    destination_path: "docs/%algebras_locale_code%/index.html"
  "docs/getting-started.html":
    destination_path: "docs/%algebras_locale_code%/getting-started.html"
```

## Usage Examples

### 1. Initialize Project

```bash
# Navigate to your project directory
cd your-project

# Initialize algebras-cli
algebras init

# Add target languages
algebras add fr es de
```

### 2. Basic Translation

```bash
# Translate all missing keys
algebras translate

# Translate specific language
algebras translate --language fr

# Force translation (even if up-to-date)
algebras translate --force
```

### 3. Update Translations

```bash
# Update missing keys only
algebras update

# Update specific language
algebras update --language es

# Full translation update
algebras update --full
```

### 4. Check Status

```bash
# Check all languages
algebras status

# Check specific language
algebras status --language de
```

### 5. Review Translations

```bash
# Review all languages
algebras review

# Review specific language
algebras review --language fr
```

## Best Practices

### 1. HTML Structure

- **Semantic HTML**: Use proper HTML5 semantic elements
- **Accessibility**: Include proper ARIA labels and alt text
- **Meta tags**: Include language-specific meta tags
- **Clean markup**: Keep HTML structure clean and consistent

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Our Application</title>
    <meta name="description" content="A powerful application for developers">
</head>
<body>
    <header role="banner">
        <h1>Welcome to Our Application</h1>
        <nav role="navigation">
            <ul>
                <li><a href="#home">Home</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>
</body>
</html>
```

### 2. Text Content Organization

- **Separate content from structure**: Keep translatable text in content areas
- **Avoid inline styles**: Use CSS classes instead of inline styles
- **Consistent formatting**: Use consistent text formatting across languages

```html
<!-- Good: Clean content structure -->
<section class="hero">
    <h2>Welcome to Our Amazing Application</h2>
    <p class="lead">This is a powerful tool that will help you achieve your goals.</p>
    <button class="cta-button">Get Started</button>
</section>

<!-- Avoid: Inline styles and mixed content -->
<section style="background: blue;">
    <h2>Welcome to Our <strong>Amazing</strong> Application</h2>
    <p>This is a <em>powerful</em> tool that will help you achieve your goals.</p>
</section>
```

### 3. Language-Specific Considerations

- **RTL languages**: Consider right-to-left languages in CSS
- **Text length**: Account for different text lengths in different languages
- **Cultural context**: Be aware of cultural differences in content

```html
<!-- Consider RTL languages -->
<html lang="ar" dir="rtl">
<head>
    <title>مرحباً بكم في تطبيقنا</title>
</head>
<body>
    <h1>مرحباً بكم في تطبيقنا</h1>
    <p>هذا تطبيق قوي سيساعدكم في تحقيق أهدافكم.</p>
</body>
</html>
```

### 4. SEO and Meta Tags

- **Language tags**: Use proper language attributes
- **Meta descriptions**: Translate meta descriptions
- **Title tags**: Translate page titles
- **Alt text**: Translate image alt text

```html
<!-- English version -->
<html lang="en">
<head>
    <title>Welcome to Our Application</title>
    <meta name="description" content="A powerful application for developers">
</head>
<body>
    <img src="hero.jpg" alt="Welcome to our application">
</body>
</html>

<!-- French version -->
<html lang="fr">
<head>
    <title>Bienvenue dans Notre Application</title>
    <meta name="description" content="Une application puissante pour les développeurs">
</head>
<body>
    <img src="hero.jpg" alt="Bienvenue dans notre application">
</body>
</html>
```

## Common Use Cases

### Static Landing Page

```html
<!-- en.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <title>My Awesome Product</title>
    <meta name="description" content="The best product for your needs">
</head>
<body>
    <header>
        <h1>My Awesome Product</h1>
        <nav>
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    
    <main>
        <section id="hero">
            <h2>Transform Your Business</h2>
            <p>Our product will revolutionize how you work.</p>
            <button>Start Free Trial</button>
        </section>
        
        <section id="features">
            <h2>Amazing Features</h2>
            <ul>
                <li>Feature 1: Boost productivity</li>
                <li>Feature 2: Save time</li>
                <li>Feature 3: Increase efficiency</li>
            </ul>
        </section>
    </main>
</body>
</html>
```

### Email Template

```html
<!-- welcome.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Welcome to Our Service</title>
</head>
<body>
    <div class="email-container">
        <h1>Welcome to Our Service!</h1>
        <p>Thank you for joining us. We're excited to have you on board.</p>
        <p>Here's what you can do next:</p>
        <ul>
            <li>Complete your profile</li>
            <li>Explore our features</li>
            <li>Get started with your first project</li>
        </ul>
        <a href="#" class="button">Get Started</a>
    </div>
</body>
</html>
```

### Documentation Page

```html
<!-- getting-started.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Getting Started - Documentation</title>
</head>
<body>
    <nav class="sidebar">
        <ul>
            <li><a href="#introduction">Introduction</a></li>
            <li><a href="#installation">Installation</a></li>
            <li><a href="#configuration">Configuration</a></li>
        </ul>
    </nav>
    
    <main class="content">
        <h1>Getting Started</h1>
        <p>This guide will help you get up and running quickly.</p>
        
        <section id="introduction">
            <h2>Introduction</h2>
            <p>Our application is designed to make your life easier.</p>
        </section>
        
        <section id="installation">
            <h2>Installation</h2>
            <p>Follow these steps to install our application.</p>
        </section>
    </main>
</body>
</html>
```

## Example Files

### Before Translation (en.html)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Our Application</title>
    <meta name="description" content="A powerful application for developers">
</head>
<body>
    <header>
        <h1>Welcome to Our Application</h1>
        <nav>
            <a href="#home">Home</a>
            <a href="#about">About</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    
    <main>
        <section id="home">
            <h2>Welcome to Our Amazing Application</h2>
            <p>This is a powerful tool that will help you achieve your goals.</p>
            <button>Get Started</button>
        </section>
        
        <section id="about">
            <h2>About Us</h2>
            <p>We are a team of passionate developers creating amazing software.</p>
        </section>
    </main>
    
    <footer>
        <p>&copy; 2024 Our Company. All rights reserved.</p>
    </footer>
</body>
</html>
```

### After Translation (fr.html)
```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bienvenue dans Notre Application</title>
    <meta name="description" content="Une application puissante pour les développeurs">
</head>
<body>
    <header>
        <h1>Bienvenue dans Notre Application</h1>
        <nav>
            <a href="#home">Accueil</a>
            <a href="#about">À propos</a>
            <a href="#contact">Contact</a>
        </nav>
    </header>
    
    <main>
        <section id="home">
            <h2>Bienvenue dans Notre Application Incroyable</h2>
            <p>C'est un outil puissant qui vous aidera à atteindre vos objectifs.</p>
            <button>Commencer</button>
        </section>
        
        <section id="about">
            <h2>À Propos de Nous</h2>
            <p>Nous sommes une équipe de développeurs passionnés créant des logiciels incroyables.</p>
        </section>
    </main>
    
    <footer>
        <p>&copy; 2024 Notre Entreprise. Tous droits réservés.</p>
    </footer>
</body>
</html>
```

## Troubleshooting

### Common Issues

**HTML parsing errors:**
- Ensure valid HTML structure
- Check for unclosed tags
- Validate HTML before translation

**Missing translations:**
- Verify source file paths in `.algebras.config`
- Check that target language files exist
- Run `algebras status` to see missing keys

**Encoding issues:**
- Save files as UTF-8
- Include proper charset meta tag
- Check for BOM (Byte Order Mark)

**Layout issues:**
- Account for different text lengths
- Test with different languages
- Use responsive design principles

### Performance Tips

- **Batch processing**: Use `--batch-size` for large files
- **UI-safe translations**: Use `--ui-safe` for UI-constrained text
- **Glossary support**: Upload glossaries for consistent terminology

```bash
# Performance-optimized translation
algebras translate --batch-size 20 --ui-safe --glossary-id my-glossary
```

## Related Examples

- [HTML Example](../../examples/html/) - Complete HTML setup
- [Email Templates Example](../../examples/email-templates/) - Email template localization
- [Documentation Site Example](../../examples/docs-site/) - Documentation localization
