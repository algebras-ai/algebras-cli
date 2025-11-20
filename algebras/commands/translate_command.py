"""
Translate your application
"""

import os
import json
import yaml
import click
from colorama import Fore
from typing import Dict, Any, Optional, List, Tuple, Set

from algebras.config import Config
from algebras.services.translator import Translator
from algebras.services.file_scanner import FileScanner
from algebras.utils.path_utils import determine_target_path, resolve_destination_path
from algebras.utils.lang_validator import validate_language_files, find_outdated_keys, extract_all_keys
from algebras.utils.git_utils import is_git_available, is_git_repository
from algebras.utils.ts_handler import read_ts_translation_file, write_ts_translation_file
from algebras.utils.android_xml_handler import read_android_xml_file, write_android_xml_file, write_android_xml_file_in_place
from algebras.utils.ios_strings_handler import read_ios_strings_file, write_ios_strings_file
from algebras.utils.ios_stringsdict_handler import (
    read_ios_stringsdict_file, 
    write_ios_stringsdict_file,
    extract_translatable_strings,
    update_translatable_strings
)
from algebras.utils.po_handler import read_po_file, write_po_file
from algebras.utils.html_handler import read_html_file, write_html_file
from algebras.utils.xliff_handler import read_xliff_file, write_xliff_file, extract_translatable_strings as extract_xliff_strings, update_xliff_targets
from algebras.utils.csv_handler import read_csv_file, write_csv_file, write_csv_file_in_place, extract_translatable_strings as extract_csv_strings, get_csv_language_codes


def execute(language: Optional[str] = None, force: bool = False, only_missing: bool = False,
           outdated_files: List[Tuple[str, str]] = None, 
           missing_keys_files: List[Tuple[str, Set[str], str]] = None,
           outdated_keys_files: List[Tuple[str, Set[str], str]] = None,
           ui_safe: bool = False, verbose: bool = False, batch_size: Optional[int] = None, 
           max_parallel_batches: Optional[int] = None, glossary_id: Optional[str] = None, prompt_file: Optional[str] = None, 
           regenerate_from_scratch: bool = False, config_file: Optional[str] = None) -> None:
    """
    Translate your application.
    
    Args:
        language: Language to translate (if None, translate all languages)
        force: Force translation even if files are up to date
        only_missing: Only translate keys that are missing in the target file
        outdated_files: List of tuples (target_file, source_file) that are outdated by modification time
        missing_keys_files: List of tuples (target_file, missing_keys, source_file)
        outdated_keys_files: List of tuples (target_file, outdated_keys, source_file)
        ui_safe: If True, ensure translations will not be longer than original text
        verbose: If True, show detailed logs of the translation process
        batch_size: Override the batch size for translation processing
        max_parallel_batches: Override the maximum number of parallel batches for translation processing
        glossary_id: ID of the glossary to use for translation
        prompt_file: Path to a file containing a custom prompt for translation
        regenerate_from_scratch: If True, regenerate files from scratch instead of updating in-place
        config_file: Path to custom config file (optional)
    """
    config = Config(config_file)

    if not config.exists():
        click.echo(f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m")
        return
    
    # Load configuration
    config.load()
    if verbose:
        click.echo(f"{Fore.BLUE}Loaded configuration: {config.config_path}\x1b[0m")
    
    # Check for deprecated config format
    if config.check_deprecated_format():
        click.echo(f"{Fore.RED}🚨 ⚠️  WARNING: Your configuration uses the deprecated 'path_rules' format! ⚠️ 🚨{Fore.RESET}")
        click.echo(f"{Fore.RED}🔴 Please update to the new 'source_files' format.{Fore.RESET}")
        click.echo(f"{Fore.RED}📖 See documentation: https://github.com/algebras-ai/algebras-cli{Fore.RESET}")
    
    # Get XLIFF target state from config (default: "translated")
    xlf_target_state = config.get_setting("xlf.default_target_state", "translated")
    
    # Get PO mark_fuzzy from config (default: false)
    po_mark_fuzzy = config.get_setting("po.mark_fuzzy", False)
    
    # Get languages
    languages = config.get_languages()
    if verbose:
        click.echo(f"{Fore.BLUE}Available languages: {', '.join(languages)}\x1b[0m")
        
    if len(languages) < 2:
        click.echo(f"{Fore.YELLOW}Only one language ({languages[0]}) is configured. Add more languages with 'algebras add <language>'.\x1b[0m")
        return
    
    # Filter languages if specified
    if language:
        if language not in languages:
            click.echo(f"{Fore.RED}Language '{language}' is not configured in your project.\x1b[0m")
            return
        target_languages = [language]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected target language: {language}\x1b[0m")
    else:
        # Skip the source language
        source_lang = config.get_source_language()
        target_languages = [lang for lang in languages if lang != source_lang]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected target languages: {', '.join(target_languages)}\x1b[0m")
    
    # Get source language
    source_language = config.get_source_language()
    if verbose:
        click.echo(f"{Fore.BLUE}Source language: {source_language}\x1b[0m")
    
    # Initialize translator
    translator = Translator(config=config)
    if verbose:
        click.echo(f"{Fore.BLUE}Initialized translator\x1b[0m")
    
    # Handle custom prompt from file or config
    custom_prompt = None
    if prompt_file:
        try:
            if not os.path.exists(prompt_file):
                click.echo(f"{Fore.RED}Prompt file not found: {prompt_file}\x1b[0m")
                return
            
            with open(prompt_file, "r", encoding="utf-8") as f:
                custom_prompt = f.read().strip()
            
            if verbose:
                click.echo(f"{Fore.BLUE}Loaded custom prompt from file: {prompt_file}\x1b[0m")
                click.echo(f"{Fore.BLUE}Prompt preview: {custom_prompt[:100]}{'...' if len(custom_prompt) > 100 else ''}\x1b[0m")
        except Exception as e:
            click.echo(f"{Fore.RED}Error reading prompt file {prompt_file}: {str(e)}\x1b[0m")
            return
    else:
        # Check if prompt is configured in the config file
        custom_prompt = config.get_setting("api.prompt", "")
        if custom_prompt and verbose:
            click.echo(f"{Fore.BLUE}Using prompt from config file\x1b[0m")
            click.echo(f"{Fore.BLUE}Prompt preview: {custom_prompt[:100]}{'...' if len(custom_prompt) > 100 else ''}\x1b[0m")
    
    # Set the custom prompt in the translator if provided
    if custom_prompt:
        translator.set_custom_prompt(custom_prompt)
        if verbose:
            click.echo(f"{Fore.BLUE}Custom prompt set for translation\x1b[0m")
    
    # Override batch size if specified
    if batch_size is not None:
        if batch_size < 1:
            click.echo(f"{Fore.RED}Batch size must be at least 1. Using default batch size.\x1b[0m")
        else:
            translator.batch_size = batch_size
            if verbose:
                click.echo(f"{Fore.BLUE}Using batch size: {batch_size}\x1b[0m")
    elif verbose:
        click.echo(f"{Fore.BLUE}Using default batch size: {translator.batch_size} (20 strings per batch for Algebras AI)\x1b[0m")
    
    # Override max parallel batches if specified
    if max_parallel_batches is not None:
        if max_parallel_batches < 1:
            click.echo(f"{Fore.RED}Max parallel batches must be at least 1. Using default max parallel batches.\x1b[0m")
        else:
            translator.max_parallel_batches = max_parallel_batches
            if verbose:
                click.echo(f"{Fore.BLUE}Using max parallel batches: {max_parallel_batches}\x1b[0m")
    elif verbose:
        click.echo(f"{Fore.BLUE}Using default max parallel batches: {translator.max_parallel_batches}\x1b[0m")
    
    # Initialize lists if they're None
    outdated_files = outdated_files or []
    missing_keys_files = missing_keys_files or []
    outdated_keys_files = outdated_keys_files or []
    
    if verbose:
        click.echo(f"{Fore.BLUE}Files to process: {len(outdated_files)} outdated, {len(missing_keys_files)} with missing keys, {len(outdated_keys_files)} with outdated keys\x1b[0m")
    
    # Check if we have specific files to update
    if outdated_files or missing_keys_files or outdated_keys_files:
        # Process the specific files that were passed in
        
        for target_lang in target_languages:
            # Process outdated files - find changed keys by comparing the content
            for target_file, source_file in outdated_files:
                click.echo(f"\n{Fore.BLUE}Processing outdated file {os.path.basename(target_file)} for language '{target_lang}'...{Fore.RESET}")
                
                try:
                    # Load both source and target files
                    if source_file.endswith(".json"):
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = json.load(f)
                        with open(target_file, "r", encoding="utf-8") as f:
                            target_content = json.load(f)
                    elif source_file.endswith((".yaml", ".yml")):
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = yaml.safe_load(f)
                        with open(target_file, "r", encoding="utf-8") as f:
                            target_content = yaml.safe_load(f)
                    elif source_file.endswith(".ts"):
                        source_content = read_ts_translation_file(source_file)
                        target_content = read_ts_translation_file(target_file)
                    elif source_file.endswith(".xml"):
                        source_content = read_android_xml_file(source_file)
                        target_content = read_android_xml_file(target_file)
                    elif source_file.endswith(".strings"):
                        source_content = read_ios_strings_file(source_file)
                        target_content = read_ios_strings_file(target_file)
                    elif source_file.endswith(".stringsdict"):
                        # For .stringsdict files, we need to extract translatable strings first
                        source_content_raw = read_ios_stringsdict_file(source_file)
                        target_content_raw = read_ios_stringsdict_file(target_file)
                        source_content = extract_translatable_strings(source_content_raw)
                        target_content = extract_translatable_strings(target_content_raw)
                    elif source_file.endswith(".po"):
                        source_content = read_po_file(source_file)
                        target_content = read_po_file(target_file)
                    elif source_file.endswith(".html"):
                        source_content = read_html_file(source_file)
                        target_content = read_html_file(target_file)
                    elif source_file.endswith((".xlf", ".xliff")):
                        # For XLIFF files, extract translatable strings to get a flat dictionary
                        source_content_raw = read_xliff_file(source_file)
                        target_content_raw = read_xliff_file(target_file)
                        source_content = extract_xliff_strings(source_content_raw)
                        target_content = extract_xliff_strings(target_content_raw)
                    else:
                        raise ValueError(f"Unsupported file format: {source_file}")
                    
                    # Extract all keys from both files
                    if source_file.endswith((".html", ".xlf", ".xliff", ".csv")):
                        source_keys = set(source_content.keys())
                        target_keys = set(target_content.keys())
                    else:
                        source_keys = extract_all_keys(source_content)
                        target_keys = extract_all_keys(target_content)
                    
                    # Find keys that exist in both files - these are potentially outdated
                    common_keys = source_keys.intersection(target_keys)
                    
                    # Compare values to find potentially modified keys
                    modified_keys = []
                    for key in common_keys:
                        if source_file.endswith((".html", ".xlf", ".xliff", ".csv")):
                            # For HTML, XLIFF, and CSV files, keys are flat, so compare values directly
                            source_value = source_content.get(key)
                            target_value = target_content.get(key)
                        else:
                            key_parts = key.split('.')
                            source_value = get_nested_value(source_content, key_parts)
                            target_value = get_nested_value(target_content, key_parts)
                        
                        # If values are different, consider this key outdated
                        if source_value != target_value and isinstance(source_value, str):
                            modified_keys.append(key)
                    
                    # Find keys only in source (missing keys)
                    missing_keys = source_keys - target_keys
                    
                    # Report what we found
                    if missing_keys:
                        click.echo(f"  {Fore.YELLOW}Found {len(missing_keys)} missing keys in {os.path.basename(target_file)}{Fore.RESET}")
                    
                    if modified_keys:
                        click.echo(f"  {Fore.YELLOW}Found {len(modified_keys)} potentially outdated keys in {os.path.basename(target_file)}{Fore.RESET}")
                        # Print up to 5 modified keys as examples
                        for key in modified_keys[:5]:
                            click.echo(f"    - {key}")
                        if len(modified_keys) > 5:
                            click.echo(f"    - ... and {len(modified_keys) - 5} more")
                    
                    # Translate missing keys
                    if missing_keys:
                        click.echo(f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys...{Fore.RESET}")
                        target_content = translator.translate_missing_keys_batch(
                            source_content, 
                            target_content, 
                            list(missing_keys), 
                            target_lang,
                            ui_safe,
                            glossary_id
                        )
                    
                    # Translate modified keys
                    if modified_keys and not only_missing:
                        click.echo(f"  {Fore.GREEN}Translating {len(modified_keys)} outdated keys...{Fore.RESET}")
                        target_content = translator.translate_outdated_keys_batch(
                            source_content,
                            target_content,
                            modified_keys,
                            target_lang,
                            ui_safe,
                            glossary_id
                        )
                    
                    # Save updated content if there were changes
                    if missing_keys or modified_keys:
                        use_in_place = _should_use_in_place(target_file, regenerate_from_scratch)
                        keys_to_update = set(missing_keys) | set(modified_keys)
                        
                        if target_file.endswith(".json"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}JSON format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(target_content, f, ensure_ascii=False, indent=2)
                        elif target_file.endswith((".yaml", ".yml")):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}YAML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(target_content, f, default_flow_style=False, allow_unicode=True)
                        elif target_file.endswith(".ts"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}TypeScript format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ts_translation_file(target_file, target_content)
                        elif target_file.endswith(".xml"):
                            if use_in_place:
                                write_android_xml_file_in_place(target_file, target_content, keys_to_update)
                            else:
                                write_android_xml_file(target_file, target_content)
                        elif target_file.endswith(".strings"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}iOS Strings format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ios_strings_file(target_file, target_content)
                        elif target_file.endswith(".stringsdict"):
                            # For .stringsdict files, update the original structure with translations
                            updated_content = update_translatable_strings(target_content_raw, target_content)
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}iOS StringsDict format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ios_stringsdict_file(target_file, updated_content)
                        elif target_file.endswith(".html"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}HTML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_html_file(target_file, source_file, target_content)
                        elif target_file.endswith((".xlf", ".xliff")):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}XLIFF format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            # Update the original XLIFF structure with translations, preserving source text
                            # Also add new units from source that don't exist in target
                            updated_content = update_xliff_targets(target_content_raw, target_content, source_content_raw, xlf_target_state)
                            write_xliff_file(target_file, updated_content, source_language, target_lang, xlf_target_state)
                        elif target_file.endswith(".csv"):
                            # Map language code to actual column name using config
                            mapped_target_lang = config.get_destination_locale_code(target_lang)
                            if use_in_place:
                                write_csv_file_in_place(target_file, target_content, mapped_target_lang, keys_to_update)
                            else:
                                # Regenerate from scratch - read existing CSV and update language column
                                existing_csv = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}, 'key_column': 'Key'}
                                from algebras.utils.csv_handler import add_language_to_csv
                                updated_csv = add_language_to_csv(existing_csv, mapped_target_lang, target_content)
                                write_csv_file(target_file, updated_csv)
                        
                        updated_count = len(missing_keys) + len(modified_keys)
                        click.echo(f"  {Fore.GREEN}✓ Updated {updated_count} keys in {target_file}\x1b[0m")
                    else:
                        click.echo(f"  {Fore.GREEN}No keys need to be updated in {os.path.basename(target_file)}\x1b[0m")
                        
                except Exception as e:
                    click.echo(f"  {Fore.RED}Error processing outdated file {os.path.basename(target_file)}: {str(e)}\x1b[0m")
            
            # Process files with specific missing keys
            for target_file, missing_keys, source_file in missing_keys_files:
                click.echo(f"\n{Fore.BLUE}Processing file with missing keys {os.path.basename(target_file)}...{Fore.RESET}")
                
                try:
                    # Load both source and target files
                    if source_file.endswith(".json"):
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = json.load(f)
                        with open(target_file, "r", encoding="utf-8") as f:
                            target_content = json.load(f)
                    elif source_file.endswith((".yaml", ".yml")):
                        with open(source_file, "r", encoding="utf-8") as f:
                            source_content = yaml.safe_load(f)
                        with open(target_file, "r", encoding="utf-8") as f:
                            target_content = yaml.safe_load(f)
                    elif source_file.endswith(".ts"):
                        source_content = read_ts_translation_file(source_file)
                        target_content = read_ts_translation_file(target_file)
                    elif source_file.endswith(".xml"):
                        source_content = read_android_xml_file(source_file)
                        target_content = read_android_xml_file(target_file)
                    elif source_file.endswith(".strings"):
                        source_content = read_ios_strings_file(source_file)
                        target_content = read_ios_strings_file(target_file)
                    elif source_file.endswith(".stringsdict"):
                        # For .stringsdict files, we need to extract translatable strings first
                        source_content_raw = read_ios_stringsdict_file(source_file)
                        target_content_raw = read_ios_stringsdict_file(target_file)
                        source_content = extract_translatable_strings(source_content_raw)
                        target_content = extract_translatable_strings(target_content_raw)
                    elif source_file.endswith(".po"):
                        source_content = read_po_file(source_file)
                        target_content = read_po_file(target_file)
                    elif source_file.endswith(".html"):
                        source_content = read_html_file(source_file)
                        target_content = read_html_file(target_file)
                    elif source_file.endswith((".xlf", ".xliff")):
                        # For XLIFF files, extract translatable strings to get a flat dictionary
                        source_content_raw = read_xliff_file(source_file)
                        target_content_raw = read_xliff_file(target_file)
                        source_content = extract_xliff_strings(source_content_raw)
                        target_content = extract_xliff_strings(target_content_raw)
                    elif source_file.endswith(".csv"):
                        # For CSV files, read the full CSV content and extract specific language columns
                        source_csv_content = read_csv_file(source_file)
                        target_csv_content = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}}
                        # Map language codes to actual column names using config
                        mapped_source_lang = config.get_destination_locale_code(source_language)
                        mapped_target_lang = config.get_destination_locale_code(target_lang) if target_lang else None
                        source_content = extract_csv_strings(source_csv_content, mapped_source_lang)
                        target_content = extract_csv_strings(target_csv_content, mapped_target_lang) if mapped_target_lang and mapped_target_lang in get_csv_language_codes(target_csv_content) else {}
                    else:
                        raise ValueError(f"Unsupported file format: {source_file}")
                    
                    # Translate missing keys
                    if missing_keys:
                        click.echo(f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys...{Fore.RESET}")
                        target_content = translator.translate_missing_keys_batch(
                            source_content, 
                            target_content, 
                            list(missing_keys), 
                            target_lang,
                            ui_safe,
                            glossary_id
                        )
                        
                        # Save updated content
                        use_in_place = _should_use_in_place(target_file, regenerate_from_scratch)
                        keys_to_update = set(missing_keys)
                        
                        if target_file.endswith(".json"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}JSON format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(target_content, f, ensure_ascii=False, indent=2)
                        elif target_file.endswith((".yaml", ".yml")):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}YAML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(target_content, f, default_flow_style=False, allow_unicode=True)
                        elif target_file.endswith(".ts"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}TypeScript format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ts_translation_file(target_file, target_content)
                        elif target_file.endswith(".xml"):
                            if use_in_place:
                                write_android_xml_file_in_place(target_file, target_content, keys_to_update)
                            else:
                                write_android_xml_file(target_file, target_content)
                        elif target_file.endswith(".strings"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}iOS Strings format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ios_strings_file(target_file, target_content)
                        elif target_file.endswith(".stringsdict"):
                            # For .stringsdict files, update the original structure with translations
                            updated_content = update_translatable_strings(target_content_raw, target_content)
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}iOS StringsDict format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ios_stringsdict_file(target_file, updated_content)
                        elif target_file.endswith(".po"):
                            if use_in_place:
                                # PO files already support in-place updates via write_po_file
                                write_po_file(target_file, target_content, po_mark_fuzzy)
                            else:
                                write_po_file(target_file, target_content, po_mark_fuzzy)
                        elif target_file.endswith(".html"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}HTML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_html_file(target_file, source_file, target_content)
                        elif target_file.endswith((".xlf", ".xliff")):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}XLIFF format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            # Update the original XLIFF structure with translations, preserving source text
                            # Also add new units from source that don't exist in target
                            updated_content = update_xliff_targets(target_content_raw, target_content, source_content_raw, xlf_target_state)
                            write_xliff_file(target_file, updated_content, source_language, target_lang, xlf_target_state)
                        elif target_file.endswith(".csv"):
                            # Map language code to actual column name using config
                            mapped_target_lang = config.get_destination_locale_code(target_lang)
                            if use_in_place:
                                write_csv_file_in_place(target_file, target_content, mapped_target_lang, keys_to_update)
                            else:
                                # Regenerate from scratch - read existing CSV and update language column
                                existing_csv = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}, 'key_column': 'Key'}
                                from algebras.utils.csv_handler import add_language_to_csv
                                updated_csv = add_language_to_csv(existing_csv, mapped_target_lang, target_content)
                                write_csv_file(target_file, updated_csv)
                        
                        click.echo(f"  {Fore.GREEN}✓ Updated {len(missing_keys)} keys in {target_file}\x1b[0m")
                except Exception as e:
                    click.echo(f"  {Fore.RED}Error processing file with missing keys {os.path.basename(target_file)}: {str(e)}\x1b[0m")
            
            # Process files with outdated keys
            for target_file, outdated_keys, source_file in outdated_keys_files:
                if os.path.basename(target_file).startswith(target_lang):
                    click.echo(f"\n{Fore.BLUE}Processing file with outdated keys {os.path.basename(target_file)}...{Fore.RESET}")
                    
                    try:
                        # Load both source and target files
                        if source_file.endswith(".json"):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = json.load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = json.load(f)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = yaml.safe_load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = yaml.safe_load(f)
                        elif source_file.endswith(".ts"):
                            source_content = read_ts_translation_file(source_file)
                            target_content = read_ts_translation_file(target_file)
                        elif source_file.endswith(".xml"):
                            source_content = read_android_xml_file(source_file)
                            target_content = read_android_xml_file(target_file)
                        elif source_file.endswith(".strings"):
                            source_content = read_ios_strings_file(source_file)
                            target_content = read_ios_strings_file(target_file)
                        elif source_file.endswith(".stringsdict"):
                            source_content_raw = read_ios_stringsdict_file(source_file)
                            target_content_raw = read_ios_stringsdict_file(target_file)
                            source_content = extract_translatable_strings(source_content_raw)
                            target_content = extract_translatable_strings(target_content_raw)
                        elif source_file.endswith(".po"):
                            source_content = read_po_file(source_file)
                            target_content = read_po_file(target_file)
                        elif source_file.endswith(".html"):
                            source_content = read_html_file(source_file)
                            target_content = read_html_file(target_file)
                        elif source_file.endswith((".xlf", ".xliff")):
                            # For XLIFF files, extract translatable strings to get a flat dictionary
                            source_content_raw = read_xliff_file(source_file)
                            target_content_raw = read_xliff_file(target_file)
                            source_content = extract_xliff_strings(source_content_raw)
                            target_content = extract_xliff_strings(target_content_raw)
                        elif source_file.endswith(".csv"):
                            # For CSV files, read the full CSV content and extract specific language columns
                            source_csv_content = read_csv_file(source_file)
                            target_csv_content = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}}
                            # Map language codes to actual column names using config
                            mapped_source_lang = config.get_destination_locale_code(source_language)
                            mapped_target_lang = config.get_destination_locale_code(target_lang) if target_lang else None
                            source_content = extract_csv_strings(source_csv_content, mapped_source_lang)
                            target_content = extract_csv_strings(target_csv_content, mapped_target_lang) if mapped_target_lang and mapped_target_lang in get_csv_language_codes(target_csv_content) else {}
                        else:
                            raise ValueError(f"Unsupported file format: {source_file}")
                        
                        # Translate outdated keys
                        if outdated_keys and not only_missing:
                            click.echo(f"  {Fore.GREEN}Translating {len(outdated_keys)} outdated keys...{Fore.RESET}")
                            target_content = translator.translate_outdated_keys_batch(
                                source_content,
                                target_content,
                                list(outdated_keys),
                                target_lang,
                                ui_safe,
                                glossary_id
                            )
                            
                            # Save updated content
                            use_in_place = _should_use_in_place(target_file, regenerate_from_scratch)
                            keys_to_update = set(outdated_keys)
                            
                            if target_file.endswith(".json"):
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}JSON format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                with open(target_file, "w", encoding="utf-8") as f:
                                    json.dump(target_content, f, ensure_ascii=False, indent=2)
                            elif target_file.endswith((".yaml", ".yml")):
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}YAML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                with open(target_file, "w", encoding="utf-8") as f:
                                    yaml.dump(target_content, f, default_flow_style=False, allow_unicode=True)
                            elif target_file.endswith(".ts"):
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}TypeScript format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                write_ts_translation_file(target_file, target_content)
                            elif target_file.endswith(".xml"):
                                if use_in_place:
                                    write_android_xml_file_in_place(target_file, target_content, keys_to_update)
                                else:
                                    write_android_xml_file(target_file, target_content)
                            elif target_file.endswith(".strings"):
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}iOS Strings format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                write_ios_strings_file(target_file, target_content)
                            elif target_file.endswith(".stringsdict"):
                                updated_content = update_translatable_strings(target_content_raw, target_content)
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}iOS StringsDict format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                write_ios_stringsdict_file(target_file, updated_content)
                            elif target_file.endswith(".po"):
                                # PO files already support in-place updates via write_po_file
                                write_po_file(target_file, target_content, po_mark_fuzzy)
                            elif target_file.endswith(".html"):
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}HTML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                write_html_file(target_file, source_file, target_content)
                            elif target_file.endswith((".xlf", ".xliff")):
                                if use_in_place:
                                    click.echo(f"  {Fore.YELLOW}XLIFF format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                                # Update the original XLIFF structure with translations, preserving source text
                                # Also add new units from source that don't exist in target
                                updated_content = update_xliff_targets(target_content_raw, target_content, source_content_raw, xlf_target_state)
                                write_xliff_file(target_file, updated_content, source_language, target_lang, xlf_target_state)
                            elif target_file.endswith(".csv"):
                                if use_in_place:
                                    write_csv_file_in_place(target_file, target_content, target_lang, keys_to_update)
                                else:
                                    # Regenerate from scratch - read existing CSV and update language column
                                    existing_csv = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}, 'key_column': 'Key'}
                                    from algebras.utils.csv_handler import add_language_to_csv
                                    updated_csv = add_language_to_csv(existing_csv, target_lang, target_content)
                                    write_csv_file(target_file, updated_csv)
                            
                            click.echo(f"  {Fore.GREEN}✓ Updated {len(outdated_keys)} keys in {target_file}\x1b[0m")
                    except Exception as e:
                        click.echo(f"  {Fore.RED}Error processing file with outdated keys {os.path.basename(target_file)}: {str(e)}\x1b[0m")
        
        click.echo(f"\n{Fore.GREEN}Translation completed.\x1b[0m")
        return
    
    # If no specific files were provided, scan and process all files
    # Scan for files
    try:
        scanner = FileScanner(config=config)
        files_by_language = scanner.group_files_by_language()
        
        # Get source files
        source_files = files_by_language.get(source_language, [])
        if not source_files:
            click.echo(f"{Fore.YELLOW}No source files found for language '{source_language}'.\x1b[0m")
            return
        
        click.echo(f"{Fore.GREEN}Found {len(source_files)} source files for language '{source_language}'.\x1b[0m")
        # Print verbose information about source files
        click.echo("\nSource files:")
        for idx, file_path in enumerate(source_files, 1):
            file_size = os.path.getsize(file_path)
            file_size_str = f"{file_size / 1024:.1f} KB" if file_size >= 1024 else f"{file_size} bytes"
            file_ext = os.path.splitext(file_path)[1]
            
            # Get relative path for cleaner display
            try:
                rel_path = os.path.relpath(file_path)
            except ValueError:
                rel_path = file_path
                
            click.echo(f"  {idx}. {Fore.CYAN}{rel_path}{Fore.RESET} ({file_size_str}, {file_ext})")
            
        click.echo("")  # Empty line for better readability
        
        # Check if git is available for outdated key detection
        git_available = is_git_available()
        
        # Translate each target language
        for target_lang in target_languages:
            click.echo(f"\n{Fore.BLUE}Translating to {target_lang}...\x1b[0m")
            
            # Get existing files for this language
            existing_files = files_by_language.get(target_lang, [])
            existing_file_basenames = [os.path.basename(f) for f in existing_files]
            existing_file_paths = {os.path.basename(f): f for f in existing_files}
            
            # Process each source file
            for source_file in source_files:
                source_basename = os.path.basename(source_file)
                source_dirname = os.path.dirname(source_file)
                source_ext = source_basename.split('.')[-1] if '.' in source_basename else ''
                
                # Use new path resolution system if source_files config is available
                # config_file is already in scope from function parameters
                # Re-use the existing config instance
                config.load()
                source_files_config = config.get_source_files()
                
                if source_files_config and source_file in source_files_config:
                    # Use the new destination pattern system
                    destination_pattern = source_files_config[source_file].get("destination_path", "")
                    if destination_pattern:
                        target_file = resolve_destination_path(destination_pattern, target_lang, config)
                        target_basename = os.path.basename(target_file)
                        target_dirname = os.path.dirname(target_file)
                    else:
                        # Fallback to old system if no destination pattern
                        target_dirname = os.path.dirname(determine_target_path(source_file, source_language, target_lang))
                        target_basename = source_basename
                        target_file = os.path.join(target_dirname, target_basename)
                else:
                    # Fallback to old system for backward compatibility
                    # First, check if there's a direct corresponding file in the target language
                    # Example: src/locales/en.json -> src/locales/es.json
                    if source_basename == f"{source_language}.{source_ext}" and f"{target_lang}.{source_ext}" in existing_file_basenames:
                        target_file = existing_file_paths[f"{target_lang}.{source_ext}"]
                        target_basename = os.path.basename(target_file)
                        target_dirname = os.path.dirname(target_file)
                    else:
                        # Determine target filename using the more complex logic
                        if "." in source_basename:
                            name_parts = source_basename.split(".")
                            ext = name_parts.pop()
                            base = ".".join(name_parts)
                            
                            # Special case for common localization pattern like "en.json", "es.json" in same directory
                            if source_basename == f"{source_language}.{ext}" and len(base) == len(source_language):
                                target_basename = f"{target_lang}.{ext}"
                            # Check if the base already contains language marker
                            elif f".{source_language}" in base or f"-{source_language}" in base or f"_{source_language}" in base:
                                base = base.replace(f".{source_language}", f".{target_lang}")
                                base = base.replace(f"-{source_language}", f"-{target_lang}")
                                base = base.replace(f"_{source_language}", f"_{target_lang}")
                                target_basename = f"{base}.{ext}"
                            else:
                                # Check if source file is in a language-specific directory structure
                                # If so, preserve the original filename instead of adding language markers
                                source_dir_parts = os.path.normpath(source_dirname).split(os.sep)
                                has_lang_directory = any(part == source_language or part.lower() == source_language.lower() 
                                                       for part in source_dir_parts)
                                
                                # Special handling for Android values structure
                                # Files in .../values/*.xml should preserve filename (not add language suffix)
                                is_android_values = (source_file.endswith('.xml') and 
                                                   any(part == 'values' for part in source_dir_parts))
                                
                                if has_lang_directory or is_android_values:
                                    # File is in language-specific directory or Android values, preserve original filename
                                    target_basename = source_basename
                                else:
                                    # File is not in language-specific directory, add language marker to filename
                                    base = f"{base}.{target_lang}"
                                    target_basename = f"{base}.{ext}"
                        else:
                            # Check if source file is in a language-specific directory structure
                            source_dir_parts = os.path.normpath(source_dirname).split(os.sep)
                            has_lang_directory = any(part == source_language or part.lower() == source_language.lower() 
                                                   for part in source_dir_parts)
                            
                            # Special handling for Android values structure
                            # Files in .../values/*.xml should preserve filename (not add language suffix)
                            is_android_values = (source_file.endswith('.xml') and 
                                               any(part == 'values' for part in source_dir_parts))
                            
                            if has_lang_directory or is_android_values:
                                # File is in language-specific directory or Android values, preserve original filename
                                target_basename = source_basename
                            else:
                                # File is not in language-specific directory, add language marker to filename
                                target_basename = f"{source_basename}.{target_lang}"
                        
                        # Check if target file exists in the list of already existing files for this language
                        if target_basename in existing_file_basenames:
                            target_file = existing_file_paths[target_basename]
                            target_dirname = os.path.dirname(target_file)
                        else:
                            # Determine the target directory path
                            target_dirname = os.path.dirname(determine_target_path(source_file, source_language, target_lang))
                            target_file = os.path.join(target_dirname, target_basename)
                
                os.makedirs(target_dirname, exist_ok=True)
                
                # Check if target file already exists and is up to date
                if not force and os.path.exists(target_file):
                    source_mtime = os.path.getmtime(source_file)
                    target_mtime = os.path.getmtime(target_file)
                    
                    if target_mtime > source_mtime and not only_missing:
                        click.echo(f"  {Fore.YELLOW}Skipping {target_basename} (already up to date)\x1b[0m")
                        continue
                
                # Handle the translation based on mode (full or missing keys only)
                if only_missing and os.path.exists(target_file):
                    # Check which keys are missing in the target file
                    is_valid, missing_keys = validate_language_files(source_file, target_file)
                    
                    # When --only-missing is specified, we skip outdated key detection to avoid git overhead
                    # The user explicitly wants only missing keys, not outdated ones
                    if not missing_keys:
                        click.echo(f"  {Fore.GREEN}No missing keys in {target_basename}. Nothing to translate.\x1b[0m")
                        continue
                    
                    click.echo(f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys in {target_basename}...\x1b[0m")
                    
                    try:
                        # Load both source and target files
                        if source_file.endswith(".json"):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = json.load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = json.load(f)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(source_file, "r", encoding="utf-8") as f:
                                source_content = yaml.safe_load(f)
                            with open(target_file, "r", encoding="utf-8") as f:
                                target_content = yaml.safe_load(f)
                        elif source_file.endswith(".ts"):
                            source_content = read_ts_translation_file(source_file)
                            target_content = read_ts_translation_file(target_file)
                        elif source_file.endswith(".xml"):
                            source_content = read_android_xml_file(source_file)
                            target_content = read_android_xml_file(target_file)
                        elif source_file.endswith(".strings"):
                            source_content = read_ios_strings_file(source_file)
                            target_content = read_ios_strings_file(target_file)
                        elif source_file.endswith(".stringsdict"):
                            source_content_raw = read_ios_stringsdict_file(source_file)
                            target_content_raw = read_ios_stringsdict_file(target_file)
                            source_content = extract_translatable_strings(source_content_raw)
                            target_content = extract_translatable_strings(target_content_raw)
                        elif source_file.endswith(".po"):
                            source_content = read_po_file(source_file)
                            target_content = read_po_file(target_file)
                        elif source_file.endswith(".html"):
                            source_content = read_html_file(source_file)
                            target_content = read_html_file(target_file)
                        elif source_file.endswith((".xlf", ".xliff")):
                            # For XLIFF files, extract translatable strings to get a flat dictionary
                            source_content_raw = read_xliff_file(source_file)
                            target_content_raw = read_xliff_file(target_file)
                            source_content = extract_xliff_strings(source_content_raw)
                            target_content = extract_xliff_strings(target_content_raw)
                        elif source_file.endswith(".csv"):
                            # For CSV files, read the full CSV content and extract specific language columns
                            source_csv_content = read_csv_file(source_file)
                            target_csv_content = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}}
                            # Map language codes to actual column names using config
                            mapped_source_lang = config.get_destination_locale_code(source_language)
                            mapped_target_lang = config.get_destination_locale_code(target_lang) if target_lang else None
                            source_content = extract_csv_strings(source_csv_content, mapped_source_lang)
                            target_content = extract_csv_strings(target_csv_content, mapped_target_lang) if mapped_target_lang and mapped_target_lang in get_csv_language_codes(target_csv_content) else {}
                        else:
                            raise ValueError(f"Unsupported file format: {source_file}")
                        
                        # Translate only the missing keys
                        translated_content = translator.translate_missing_keys_batch(
                            source_content, 
                            target_content, 
                            list(missing_keys), 
                            target_lang,
                            ui_safe,
                            glossary_id
                        )
                        
                        # Save updated content
                        use_in_place = _should_use_in_place(target_file, regenerate_from_scratch)
                        keys_to_update = set(missing_keys)
                        
                        if source_file.endswith(".json"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}JSON format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(translated_content, f, ensure_ascii=False, indent=2)
                        elif source_file.endswith((".yaml", ".yml")):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}YAML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(translated_content, f, default_flow_style=False, allow_unicode=True)
                        elif source_file.endswith(".ts"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}TypeScript format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ts_translation_file(target_file, translated_content)
                        elif source_file.endswith(".xml"):
                            if use_in_place:
                                write_android_xml_file_in_place(target_file, translated_content, keys_to_update)
                            else:
                                write_android_xml_file(target_file, translated_content)
                        elif source_file.endswith(".strings"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}iOS Strings format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ios_strings_file(target_file, translated_content)
                        elif source_file.endswith(".stringsdict"):
                            updated_content = update_translatable_strings(target_content_raw, translated_content)
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}iOS StringsDict format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_ios_stringsdict_file(target_file, updated_content)
                        elif source_file.endswith(".po"):
                            # PO files already support in-place updates via write_po_file
                            write_po_file(target_file, translated_content, po_mark_fuzzy)
                        elif source_file.endswith(".html"):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}HTML format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            write_html_file(target_file, source_file, translated_content)
                        elif source_file.endswith((".xlf", ".xliff")):
                            if use_in_place:
                                click.echo(f"  {Fore.YELLOW}XLIFF format does not support in-place updates yet, regenerating from scratch{Fore.RESET}")
                            # Update the original XLIFF structure with translations, preserving source text
                            # Also add new units from source that don't exist in target
                            updated_content = update_xliff_targets(target_content_raw, translated_content, source_content_raw, xlf_target_state)
                            write_xliff_file(target_file, updated_content, source_language, target_lang, xlf_target_state)
                        elif source_file.endswith(".csv"):
                            if use_in_place:
                                write_csv_file_in_place(target_file, translated_content, target_lang, keys_to_update)
                            else:
                                # Regenerate from scratch - read existing CSV and update language column
                                existing_csv = read_csv_file(target_file) if os.path.exists(target_file) else {'languages': [], 'translations': {}, 'key_column': 'Key'}
                                from algebras.utils.csv_handler import add_language_to_csv
                                updated_csv = add_language_to_csv(existing_csv, target_lang, translated_content)
                                write_csv_file(target_file, updated_csv)
                        
                        click.echo(f"  {Fore.GREEN}✓ Updated {len(missing_keys)} keys in {target_file}\x1b[0m")
                    except Exception as e:
                        click.echo(f"  {Fore.RED}Error translating keys in {source_basename}: {str(e)}\x1b[0m")
                else:
                    # Translate the full file
                    click.echo(f"  {Fore.GREEN}Translating {source_basename} to {target_basename}...\x1b[0m")
                    # For .stringsdict files, we need to load the target file to get the structure
                    if source_file.endswith(".stringsdict"):
                        # Load the target file if it exists to preserve structure
                        if os.path.exists(target_file):
                            target_content_raw = read_ios_stringsdict_file(target_file)
                        else:
                            # If target file doesn't exist, use source file as template
                            target_content_raw = read_ios_stringsdict_file(source_file)
                        
                        # Translate the file
                        translated_content = translator.translate_file(source_file, target_lang, ui_safe, glossary_id)
                        
                        # Update the target structure with translations
                        updated_content = update_translatable_strings(target_content_raw, translated_content)
                        write_ios_stringsdict_file(target_file, updated_content)
                    elif source_file.endswith(".csv"):
                        # For CSV files, read existing CSV and add/update language column
                        existing_csv = read_csv_file(source_file)
                        translated_content = translator.translate_file(source_file, target_lang, ui_safe, glossary_id)
                        # Extract the translated strings (they come as flat dict from translator)
                        from algebras.utils.csv_handler import add_language_to_csv
                        updated_csv = add_language_to_csv(existing_csv, target_lang, translated_content)
                        write_csv_file(target_file, updated_csv)
                    else:
                        # For other file types, use the normal translation flow
                        translated_content = translator.translate_file(source_file, target_lang, ui_safe, glossary_id)
                        
                        # Save translated content
                        # For full file translation, we always regenerate from scratch
                        # (since we're translating the entire file, not just updating keys)
                        if source_file.endswith(".json"):
                            with open(target_file, "w", encoding="utf-8") as f:
                                json.dump(translated_content, f, ensure_ascii=False, indent=2)
                        elif source_file.endswith((".yaml", ".yml")):
                            with open(target_file, "w", encoding="utf-8") as f:
                                yaml.dump(translated_content, f, default_flow_style=False, allow_unicode=True)
                        elif source_file.endswith(".ts"):
                            write_ts_translation_file(target_file, translated_content)
                        elif source_file.endswith(".xml"):
                            write_android_xml_file(target_file, translated_content)
                        elif source_file.endswith(".strings"):
                            write_ios_strings_file(target_file, translated_content)
                        elif source_file.endswith(".po"):
                            write_po_file(target_file, translated_content, po_mark_fuzzy)
                        elif source_file.endswith(".html"):
                            write_html_file(target_file, source_file, translated_content)
                        elif source_file.endswith((".xlf", ".xliff")):
                            write_xliff_file(target_file, translated_content, source_language, target_lang, xlf_target_state)
                        
                        click.echo(f"  {Fore.GREEN}✓ Saved to {target_file}\x1b[0m")
        
        click.echo(f"\n{Fore.GREEN}Translation completed.\x1b[0m")
        click.echo(f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m")
    
    except Exception as e:
        import traceback
        click.echo(f"{Fore.RED}Error: {str(e)}\x1b[0m")
        traceback.print_exc()


def _should_use_in_place(target_file: str, regenerate_from_scratch: bool) -> bool:
    """
    Determine if we should use in-place updates or regenerate from scratch.
    
    Args:
        target_file: Path to the target file
        regenerate_from_scratch: Flag indicating to regenerate from scratch
        
    Returns:
        True if in-place updates should be used, False otherwise
    """
    if regenerate_from_scratch:
        return False
    return os.path.exists(target_file)


def get_nested_value(data: Dict[str, Any], key_parts: List[str]) -> Any:
    """
    Get a value from a nested dictionary using a list of key parts.
    
    Args:
        data: Dictionary to get value from
        key_parts: List of key parts representing a dot-notation path
        
    Returns:
        Value at the specified path
    """
    current = data
    for part in key_parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current 