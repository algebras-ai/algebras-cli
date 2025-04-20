"""
Example demonstrating how to use the Algebras AI provider for translation
"""

import os
import click
from colorama import Fore
from algebras.config import Config
from algebras.services.translator import Translator

def main():
    # Make sure ALGEBRAS_API_KEY environment variable is set
    if not os.environ.get("ALGEBRAS_API_KEY"):
        click.echo(f"{Fore.RED}Error: ALGEBRAS_API_KEY environment variable not set")
        click.echo(f"Please set it with: export ALGEBRAS_API_KEY=your_api_key{Fore.RESET}")
        return
    
    # Create a sample configuration
    config = Config()
    
    # Create a new configuration if it doesn't exist
    if not config.exists():
        config.create_default()
    
    # Update the configuration to use Algebras AI provider
    config.load()
    if "api" not in config.data:
        config.data["api"] = {}
    
    config.data["api"]["provider"] = "algebras-ai"
    config.save()
    
    click.echo(f"{Fore.GREEN}Set Algebras AI as the translation provider in configuration{Fore.RESET}")
    
    # Create translator with the Algebras AI provider
    translator = Translator()
    
    # Example text to translate
    text = "Hello world, this is a test of the Algebras AI translation API."
    source_lang = "en"
    target_lang = "de"  # German
    
    click.echo(f"\n{Fore.BLUE}Text to translate: {text}{Fore.RESET}")
    click.echo(f"{Fore.BLUE}Source language: {source_lang}")
    click.echo(f"{Fore.BLUE}Target language: {target_lang}{Fore.RESET}")
    
    # Translate the text
    try:
        translated_text = translator.translate_text(text, source_lang, target_lang)
        click.echo(f"\n{Fore.GREEN}Translation successful!{Fore.RESET}")
        click.echo(f"\n{Fore.YELLOW}Translated text: {translated_text}{Fore.RESET}")
    except Exception as e:
        click.echo(f"\n{Fore.RED}Translation failed: {str(e)}{Fore.RESET}")

if __name__ == "__main__":
    main() 