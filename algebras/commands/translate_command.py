"""
Translate your application
"""

import os
import queue
import threading
import click
import json
import yaml
from colorama import Fore
from typing import Dict, Any, Optional, List, Tuple, Set

from algebras.utils.ts_handler import (
    write_ts_translation_file_in_place,
    convert_numeric_dicts_to_lists,
    read_ts_translation_file,
    write_ts_translation_file,
)
from algebras.utils.po_handler import (
    read_po_file,
    write_po_file,
)
from algebras.utils.android_xml_handler import (
    read_android_xml_file,
    write_android_xml_file,
    write_android_xml_file_in_place,
)
from algebras.utils.ios_strings_handler import (
    read_ios_strings_file,
    write_ios_strings_file,
)
from algebras.utils.ios_stringsdict_handler import (
    read_ios_stringsdict_file,
    write_ios_stringsdict_file,
    extract_translatable_strings,
    update_translatable_strings,
)
from algebras.utils.html_handler import (
    read_html_file,
    write_html_file,
)
from algebras.utils.xliff_handler import (
    read_xliff_file,
    write_xliff_file,
    extract_translatable_strings as extract_xliff_strings,
    update_xliff_targets,
)
from algebras.utils.csv_handler import (
    read_csv_file,
    write_csv_file,
    write_csv_file_in_place,
    extract_translatable_strings as extract_csv_strings,
)
from algebras.utils.nested_structure_handler import (
    get_nested_value,
    set_nested_value,
)
from algebras.utils.lang_validator import (
    validate_language_files,
    extract_all_keys,
)
from algebras.config import Config
from algebras.services.file_scanner import FileScanner
from algebras.utils.path_utils import determine_target_path, resolve_destination_path
from algebras.utils.git_utils import is_git_available
from algebras.utils.file_writer import IncrementalFileWriter
from algebras.services.translator import Translator
from algebras.utils.file_format_handlers import get_handler
from algebras.utils.file_format_detector import (
    is_flat_format,
    detect_format,
    FileFormat,
)
from algebras.utils.file_format_handlers import get_handler
from algebras.utils.file_format_detector import is_flat_format, detect_format


def execute(
    language: Optional[str] = None,
    force: bool = False,
    only_missing: bool = False,
    outdated_files: List[Tuple[str, str]] = None,
    missing_keys_files: List[Tuple[str, Set[str], str]] = None,
    outdated_keys_files: List[Tuple[str, Set[str], str]] = None,
    ui_safe: bool = False,
    verbose: bool = False,
    batch_size: Optional[int] = None,
    max_parallel_batches: Optional[int] = None,
    glossary_id: Optional[str] = None,
    prompt_file: Optional[str] = None,
    regenerate_from_scratch: bool = False,
    config_file: Optional[str] = None,
) -> None:
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
        click.echo(
            f"{Fore.RED}No Algebras configuration found. Run 'algebras init' first.\x1b[0m"
        )
        return

    # Load configuration
    config.load()
    if verbose:
        click.echo(f"{Fore.BLUE}Loaded configuration: {config.config_path}\x1b[0m")

    # Check for deprecated config format
    if config.check_deprecated_format():
        click.echo(
            f"{Fore.RED}🚨 ⚠️  WARNING: Your configuration uses the deprecated 'path_rules' format! ⚠️ 🚨{Fore.RESET}"
        )
        click.echo(
            f"{Fore.RED}🔴 Please update to the new 'source_files' format.{Fore.RESET}"
        )
        click.echo(
            f"{Fore.RED}📖 See documentation: https://github.com/algebras-ai/algebras-cli{Fore.RESET}"
        )

    # Get XLIFF target state from config (default: "translated")
    xlf_target_state = config.get_setting("xlf.default_target_state", "translated")
    if verbose:
        click.echo(f"{Fore.BLUE}XLIFF target state: {xlf_target_state}\x1b[0m")

    # Get XLIFF version from config (default: "1.2", supports "1.2" or "2.0")
    # Convert to string in case config returns a number
    xlf_version_raw = config.get_setting("xlf.version", "1.2")
    xlf_version = str(xlf_version_raw) if xlf_version_raw is not None else "1.2"

    # Validate version - must be "1.2" or "2.0"
    if xlf_version not in ["1.2", "2.0"]:
        if verbose:
            click.echo(
                f"{Fore.YELLOW}Invalid XLIFF version '{xlf_version}' in config, using default '1.2'\x1b[0m"
            )
        xlf_version = "1.2"
    if verbose:
        click.echo(
            f"{Fore.BLUE}XLIFF version from config: {xlf_version} (will be overridden by file version if detected)\x1b[0m"
        )

    # Get PO mark_fuzzy from config (default: false)
    po_mark_fuzzy = config.get_setting("po.mark_fuzzy", False)

    # Get languages
    languages = config.get_languages()
    if verbose:
        click.echo(f"{Fore.BLUE}Available languages: {', '.join(languages)}\x1b[0m")

    if len(languages) < 2:
        click.echo(
            f"{Fore.YELLOW}Only one language ({languages[0]}) is configured. Add more languages with 'algebras add <language>'.\x1b[0m"
        )
        return

    # Filter languages if specified
    if language:
        if language not in languages:
            click.echo(
                f"{Fore.RED}Language '{language}' is not configured in your project.\x1b[0m"
            )
            return
        target_languages = [language]
        if verbose:
            click.echo(f"{Fore.BLUE}Selected target language: {language}\x1b[0m")
    else:
        # Skip the source language
        source_lang = config.get_source_language()
        target_languages = [lang for lang in languages if lang != source_lang]
        if verbose:
            click.echo(
                f"{Fore.BLUE}Selected target languages: {', '.join(target_languages)}\x1b[0m"
            )

    # Get source language
    source_language = config.get_source_language()
    if verbose:
        click.echo(f"{Fore.BLUE}Source language: {source_language}\x1b[0m")

    # Initialize translator
    translator = Translator(config=config)
    translator.set_verbose(verbose)
    if verbose:
        click.echo(f"{Fore.BLUE}Initialized translator with verbose mode\x1b[0m")

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
                click.echo(
                    f"{Fore.BLUE}Loaded custom prompt from file: {prompt_file}\x1b[0m"
                )
                click.echo(
                    f"{Fore.BLUE}Prompt preview: {custom_prompt[:100]}{'...' if len(custom_prompt) > 100 else ''}\x1b[0m"
                )
        except Exception as e:
            click.echo(
                f"{Fore.RED}Error reading prompt file {prompt_file}: {str(e)}\x1b[0m"
            )
            return
    else:
        # Check if prompt is configured in the config file
        custom_prompt = config.get_setting("api.prompt", "")
        if custom_prompt and verbose:
            click.echo(f"{Fore.BLUE}Using prompt from config file\x1b[0m")
            click.echo(
                f"{Fore.BLUE}Prompt preview: {custom_prompt[:100]}{'...' if len(custom_prompt) > 100 else ''}\x1b[0m"
            )

    # Set the custom prompt in the translator if provided
    if custom_prompt:
        translator.set_custom_prompt(custom_prompt)
        if verbose:
            click.echo(f"{Fore.BLUE}Custom prompt set for translation\x1b[0m")

    # Override batch size if specified
    if batch_size is not None:
        if batch_size < 1:
            click.echo(
                f"{Fore.RED}Batch size must be at least 1. Using default batch size.\x1b[0m"
            )
        else:
            translator.batch_size = batch_size
            if verbose:
                click.echo(f"{Fore.BLUE}Using batch size: {batch_size}\x1b[0m")
    elif verbose:
        click.echo(
            f"{Fore.BLUE}Using default batch size: {translator.batch_size} (20 strings per batch for Algebras AI)\x1b[0m"
        )

    # Override max parallel batches if specified
    if max_parallel_batches is not None:
        if max_parallel_batches < 1:
            click.echo(
                f"{Fore.RED}Max parallel batches must be at least 1. Using default max parallel batches.\x1b[0m"
            )
        else:
            translator.max_parallel_batches = max_parallel_batches
            if verbose:
                click.echo(
                    f"{Fore.BLUE}Using max parallel batches: {max_parallel_batches}\x1b[0m"
                )
    elif verbose:
        click.echo(
            f"{Fore.BLUE}Using default max parallel batches: {translator.max_parallel_batches}\x1b[0m"
        )

    # Initialize lists if they're None
    outdated_files = outdated_files or []
    missing_keys_files = missing_keys_files or []
    outdated_keys_files = outdated_keys_files or []

    if verbose:
        click.echo(
            f"{Fore.BLUE}Files to process: {len(outdated_files)} outdated, {len(missing_keys_files)} with missing keys, {len(outdated_keys_files)} with outdated keys\x1b[0m"
        )

    # If no specific files were provided, scan and process all files
    if not outdated_files and not missing_keys_files and not outdated_keys_files:
        _process_all_files(
            config,
            source_language,
            target_languages,
            translator,
            force,
            only_missing,
            ui_safe,
            glossary_id,
            regenerate_from_scratch,
            xlf_target_state,
            xlf_version,
            po_mark_fuzzy,
            verbose,
        )
        return

    for target_lang in target_languages:
        # Process outdated files - find changed keys by comparing the content
        _process_outdated_files(
            outdated_files,
            target_lang,
            translator,
            config,
            source_language,
            ui_safe,
            glossary_id,
            only_missing,
            regenerate_from_scratch,
            xlf_target_state,
            xlf_version,
            po_mark_fuzzy,
            verbose,
        )

        # Process files with specific missing keys
        _process_missing_keys_files(
            missing_keys_files,
            target_lang,
            translator,
            config,
            source_language,
            ui_safe,
            glossary_id,
            regenerate_from_scratch,
            xlf_target_state,
            xlf_version,
            po_mark_fuzzy,
            verbose,
        )

        # Process files with outdated keys
        _process_outdated_keys_files(
            outdated_keys_files,
            target_lang,
            translator,
            config,
            source_language,
            ui_safe,
            glossary_id,
            only_missing,
            regenerate_from_scratch,
            xlf_target_state,
            xlf_version,
            po_mark_fuzzy,
            verbose,
        )

        click.echo(f"\n{Fore.GREEN}Translation completed.\x1b[0m")
        return


def _process_all_files(
    config,
    source_language: str,
    target_languages: List[str],
    translator,
    force: bool,
    only_missing: bool,
    ui_safe: bool,
    glossary_id: Optional[str],
    regenerate_from_scratch: bool,
    xlf_target_state: str,
    xlf_version: str,
    po_mark_fuzzy: bool,
    verbose: bool,
) -> None:
    """
    Scan and process all files for translation.

    Args:
        config: Config instance
        source_language: Source language code
        target_languages: List of target language codes
        translator: Translator instance
        force: Force translation even if files are up to date
        only_missing: Only translate keys that are missing in the target file
        ui_safe: If True, ensure translations will not be longer than original text
        glossary_id: ID of the glossary to use for translation
        regenerate_from_scratch: If True, regenerate files from scratch instead of updating in-place
        xlf_target_state: XLIFF target state
        xlf_version: XLIFF version
        po_mark_fuzzy: Whether to mark PO entries as fuzzy
        verbose: Verbose mode flag
    """
    try:
        scanner = FileScanner(config=config)
        files_by_language = scanner.group_files_by_language()

        # Get source files
        source_files = files_by_language.get(source_language, [])
        if not source_files:
            click.echo(
                f"{Fore.YELLOW}No source files found for language '{source_language}'.\x1b[0m"
            )
            return

        click.echo(
            f"{Fore.GREEN}Found {len(source_files)} source files for language '{source_language}'.\x1b[0m"
        )
        # Print verbose information about source files
        click.echo("\nSource files:")
        for idx, file_path in enumerate(source_files, 1):
            file_size = os.path.getsize(file_path)
            file_size_str = (
                f"{file_size / 1024:.1f} KB"
                if file_size >= 1024
                else f"{file_size} bytes"
            )
            file_ext = os.path.splitext(file_path)[1]

            # Get relative path for cleaner display
            try:
                rel_path = os.path.relpath(file_path)
            except ValueError:
                rel_path = file_path

            click.echo(
                f"  {idx}. {Fore.CYAN}{rel_path}{Fore.RESET} ({file_size_str}, {file_ext})"
            )

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
                source_ext = (
                    source_basename.split(".")[-1] if "." in source_basename else ""
                )

                # Use new path resolution system if source_files config is available
                # config_file is already in scope from function parameters
                # Re-use the existing config instance
                config.load()
                source_files_config = config.get_source_files()

                if source_files_config and source_file in source_files_config:
                    # Use the new destination pattern system
                    destination_pattern = source_files_config[source_file].get(
                        "destination_path", ""
                    )
                    if destination_pattern:
                        target_file = resolve_destination_path(
                            destination_pattern, target_lang, config
                        )
                        target_basename = os.path.basename(target_file)
                        target_dirname = os.path.dirname(target_file)
                    else:
                        # Fallback to old system if no destination pattern
                        target_dirname = os.path.dirname(
                            determine_target_path(
                                source_file, source_language, target_lang
                            )
                        )
                        target_basename = source_basename
                        target_file = os.path.join(target_dirname, target_basename)
                else:
                    # Fallback to old system for backward compatibility
                    # First, check if there's a direct corresponding file in the target language
                    # Example: src/locales/en.json -> src/locales/es.json
                    if (
                        source_basename == f"{source_language}.{source_ext}"
                        and f"{target_lang}.{source_ext}" in existing_file_basenames
                    ):
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
                            if source_basename == f"{source_language}.{ext}" and len(
                                base
                            ) == len(source_language):
                                target_basename = f"{target_lang}.{ext}"
                            # Check if the base already contains language marker
                            elif (
                                f".{source_language}" in base
                                or f"-{source_language}" in base
                                or f"_{source_language}" in base
                            ):
                                base = base.replace(
                                    f".{source_language}", f".{target_lang}"
                                )
                                base = base.replace(
                                    f"-{source_language}", f"-{target_lang}"
                                )
                                base = base.replace(
                                    f"_{source_language}", f"_{target_lang}"
                                )
                                target_basename = f"{base}.{ext}"
                            else:
                                # Check if source file is in a language-specific directory structure
                                # If so, preserve the original filename instead of adding language markers
                                source_dir_parts = os.path.normpath(
                                    source_dirname
                                ).split(os.sep)
                                has_lang_directory = any(
                                    part == source_language
                                    or part.lower() == source_language.lower()
                                    for part in source_dir_parts
                                )

                                # Special handling for Android values structure
                                # Files in .../values/*.xml should preserve filename (not add language suffix)
                                is_android_values = source_file.endswith(
                                    ".xml"
                                ) and any(part == "values" for part in source_dir_parts)

                                if has_lang_directory or is_android_values:
                                    # File is in language-specific directory or Android values, preserve original filename
                                    target_basename = source_basename
                                else:
                                    # File is not in language-specific directory, add language marker to filename
                                    base = f"{base}.{target_lang}"
                                    target_basename = f"{base}.{ext}"
                        else:
                            # Check if source file is in a language-specific directory structure
                            source_dir_parts = os.path.normpath(source_dirname).split(
                                os.sep
                            )
                            has_lang_directory = any(
                                part == source_language
                                or part.lower() == source_language.lower()
                                for part in source_dir_parts
                            )

                            # Special handling for Android values structure
                            # Files in .../values/*.xml should preserve filename (not add language suffix)
                            is_android_values = source_file.endswith(".xml") and any(
                                part == "values" for part in source_dir_parts
                            )

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
                            target_dirname = os.path.dirname(
                                determine_target_path(
                                    source_file, source_language, target_lang
                                )
                            )
                            target_file = os.path.join(target_dirname, target_basename)

                os.makedirs(target_dirname, exist_ok=True)

                # Check if target file already exists and is up to date
                if not force and os.path.exists(target_file):
                    source_mtime = os.path.getmtime(source_file)
                    target_mtime = os.path.getmtime(target_file)

                    if target_mtime > source_mtime and not only_missing:
                        # Check for missing keys even in default mode to avoid skipping files with incomplete translations
                        is_valid, missing_keys_check = validate_language_files(
                            source_file,
                            target_file,
                            source_language=source_language,
                            target_language=target_lang,
                            config=config,
                        )
                        
                        if not missing_keys_check:
                            click.echo(
                                f"  {Fore.YELLOW}Skipping {target_basename} (already up to date)\x1b[0m"
                            )
                            continue
                        # If there are missing keys, continue to translation below

                # Handle the translation based on mode (full or missing keys only)
                if only_missing and os.path.exists(target_file):
                    # Check which keys are missing in the target file
                    # For CSV files, pass language parameters to compare the correct language columns
                    is_valid, missing_keys = validate_language_files(
                        source_file,
                        target_file,
                        source_language=source_language,
                        target_language=target_lang,
                        config=config,
                    )

                    # When --only-missing is specified, we skip outdated key detection to avoid git overhead
                    # The user explicitly wants only missing keys, not outdated ones
                    if not missing_keys:
                        click.echo(
                            f"  {Fore.GREEN}No missing keys in {target_basename}. Nothing to translate.\x1b[0m"
                        )
                        continue

                    click.echo(
                        f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys in {target_basename}...\x1b[0m"
                    )

                    try:
                        # Get handler for file format
                        handler = get_handler(source_file, config)

                        # Load both source and target files using handler
                        (
                            source_content,
                            target_content,
                            source_raw_content,
                            target_raw_content,
                        ) = _load_file_contents(
                            source_file,
                            target_file,
                            handler,
                            source_language,
                            target_lang,
                            config,
                            verbose,
                            xlf_version,
                        )

                        # Save updated content
                        use_in_place = _should_use_in_place(
                            target_file, regenerate_from_scratch
                        )
                        keys_to_update = set(missing_keys)

                        # For TypeScript files, use incremental writer (special case)
                        if detect_format(source_file) == FileFormat.TS:
                            # Determine export name
                            basename = os.path.basename(target_file)
                            export_name = basename.split(".")[0]

                            # Create incremental writer
                            incremental_writer = IncrementalFileWriter(
                                target_file, "ts", export_name
                            )

                            # Define callback for batch completion
                            def on_batch_complete(
                                batch_results: Dict[str, str], batch_index: int
                            ):
                                incremental_writer.write_batch(
                                    batch_results, batch_index
                                )

                            # Translate only the missing keys with callback
                            translated_content = (
                                translator.translate_missing_keys_batch(
                                    source_content,
                                    target_content,
                                    list(missing_keys),
                                    target_lang,
                                    ui_safe,
                                    glossary_id,
                                    on_batch_complete=on_batch_complete,
                                    source_file_path=source_file,
                                )
                            )

                            # Wait for all writes to complete
                            incremental_writer.finish()
                        else:
                            # Translate only the missing keys
                            translated_content = (
                                translator.translate_missing_keys_batch(
                                    source_content,
                                    target_content,
                                    list(missing_keys),
                                    target_lang,
                                    ui_safe,
                                    glossary_id,
                                    source_file_path=source_file,
                                )
                            )

                            # Write using handler
                            _write_translated_content(
                                target_file,
                                translated_content,
                                handler,
                                keys_to_update,
                                use_in_place,
                                source_file=source_file,
                                source_language=source_language,
                                target_language=target_lang,
                                xlf_target_state=xlf_target_state,
                                xlf_version=xlf_version,
                                po_mark_fuzzy=po_mark_fuzzy,
                                source_raw_content=source_raw_content,
                                target_raw_content=target_raw_content,
                                verbose=verbose,
                            )

                        click.echo(
                            f"  {Fore.GREEN}✓ Updated {len(missing_keys)} keys in {target_file}\x1b[0m"
                        )
                    except Exception as e:
                        click.echo(
                            f"  {Fore.RED}Error translating keys in {source_basename}: {str(e)}\x1b[0m"
                        )
                else:
                    # Translate the full file
                    click.echo(
                        f"  {Fore.GREEN}Translating {source_basename} to {target_basename}...\x1b[0m"
                    )
                    # For .stringsdict files, we need to load the target file to get the structure
                    if source_file.endswith(".stringsdict"):
                        # Load the target file if it exists to preserve structure
                        if os.path.exists(target_file):
                            target_content_raw = read_ios_stringsdict_file(target_file)
                        else:
                            # If target file doesn't exist, use source file as template
                            target_content_raw = read_ios_stringsdict_file(source_file)

                        # Translate the file
                        translated_content = translator.translate_file(
                            source_file, target_lang, ui_safe, glossary_id
                        )

                        # Update the target structure with translations
                        updated_content = update_translatable_strings(
                            target_content_raw, translated_content
                        )
                        write_ios_stringsdict_file(target_file, updated_content)
                    elif source_file.endswith((".csv", ".tsv")):
                        # For CSV/TSV files, read existing CSV/TSV and add/update language column
                        existing_csv = read_csv_file(source_file)
                        translated_content = translator.translate_file(
                            source_file, target_lang, ui_safe, glossary_id
                        )
                        # Map language code to actual column name using config
                        mapped_target_lang = config.get_destination_locale_code(
                            target_lang
                        )
                        # Extract the translated strings (they come as flat dict from translator)
                        from algebras.utils.csv_handler import add_language_to_csv

                        updated_csv = add_language_to_csv(
                            existing_csv, mapped_target_lang, translated_content
                        )
                        write_csv_file(target_file, updated_csv)
                    elif source_file.endswith((".xlf", ".xliff")):
                        # For XLIFF files, extract strings, translate, then update structure
                        # Don't use translator.translate_file() as it returns structured dict, not flat translations
                        source_content_raw = read_xliff_file(source_file)
                        # Extract flat translatable strings
                        source_content = extract_xliff_strings(source_content_raw)

                        # Translate the flat dictionary using strategy
                        from algebras.services.strategies.strategy_factory import (
                            TranslationStrategyFactory,
                        )

                        flat_strategy = (
                            TranslationStrategyFactory.get_flat_dict_strategy(
                                translator
                            )
                        )
                        provider = translator.api_config.get("provider", "algebras-ai")
                        translate_text_func = (
                            None
                            if provider == "algebras-ai"
                            else translator.translate_text
                        )
                        translated_content = flat_strategy.translate(
                            source_content,
                            source_language,
                            target_lang,
                            ui_safe,
                            glossary_id,
                            None,
                            translate_text_func,
                        )

                        # Create empty target structure with version from source
                        target_version = (
                            source_content_raw.get("version", xlf_version)
                            if source_content_raw
                            else xlf_version
                        )
                        target_content_raw = {
                            "version": target_version,
                            "files": [],
                        }
                        if verbose:
                            click.echo(
                                f"  {Fore.CYAN}Creating new XLIFF file with version {target_version} and state '{xlf_target_state}'\x1b[0m"
                            )
                            # Show sample translations
                            sample_count = min(3, len(translated_content))
                            if sample_count > 0:
                                click.echo(
                                    f"  {Fore.CYAN}Sample translations:{Fore.RESET}"
                                )
                                for i, (key, value) in enumerate(
                                    list(translated_content.items())[:sample_count]
                                ):
                                    source_value = source_content.get(key, "")
                                    click.echo(
                                        f"    {key[:30]}... : '{source_value[:40]}...' → '{value[:40]}...'"
                                    )

                        # Use update_xliff_targets to properly structure the content and add state
                        updated_content = update_xliff_targets(
                            target_content_raw,
                            translated_content,
                            source_content_raw,
                            xlf_target_state,
                        )
                        write_xliff_file(
                            target_file,
                            updated_content,
                            source_language,
                            target_lang,
                            xlf_target_state,
                        )
                        click.echo(f"  {Fore.GREEN}✓ Saved to {target_file}\x1b[0m")
                    elif source_file.endswith(".ts"):
                        # For TypeScript files, use incremental writer
                        # Determine export name
                        basename = os.path.basename(target_file)
                        export_name = basename.split(".")[0]

                        # Read source content
                        source_content = read_ts_translation_file(source_file)

                        # Create incremental writer
                        incremental_writer = IncrementalFileWriter(
                            target_file, "ts", export_name
                        )

                        # Define callback for batch completion
                        def on_batch_complete(
                            batch_results: Dict[str, str], batch_index: int
                        ):
                            incremental_writer.write_batch(batch_results, batch_index)

                        # Translate with callback using strategy
                        from algebras.services.strategies.strategy_factory import (
                            TranslationStrategyFactory,
                        )

                        nested_strategy = (
                            TranslationStrategyFactory.get_nested_dict_strategy(
                                translator
                            )
                        )
                        provider = translator.api_config.get("provider", "algebras-ai")
                        translate_text_func = (
                            None
                            if provider == "algebras-ai"
                            else translator.translate_text
                        )
                        translated_content = nested_strategy.translate(
                            source_content,
                            source_language,
                            target_lang,
                            ui_safe,
                            glossary_id,
                            on_batch_complete,
                            translate_text_func,
                        )

                        # Wait for all writes to complete
                        incremental_writer.finish()
                        click.echo(f"  {Fore.GREEN}✓ Saved to {target_file}\x1b[0m")
                    else:
                        # For other file types, use the normal translation flow
                        translated_content = translator.translate_file(
                            source_file, target_lang, ui_safe, glossary_id
                        )

                        # Save translated content
                        # For full file translation, we always regenerate from scratch
                        # (since we're translating the entire file, not just updating keys)
                        handler = get_handler(source_file, config)
                        # Get all keys for full file translation
                        all_keys = handler.extract_keys(translated_content)
                        _write_translated_content(
                            target_file,
                            translated_content,
                            handler,
                            all_keys,
                            use_in_place=False,  # Always from scratch for full translation
                            source_file=source_file,
                            source_language=source_language,
                            target_language=target_lang,
                            xlf_target_state=xlf_target_state,
                            xlf_version=xlf_version,
                            po_mark_fuzzy=po_mark_fuzzy,
                            source_raw_content=None,
                            target_raw_content=None,
                            verbose=verbose,
                        )

                        click.echo(f"  {Fore.GREEN}✓ Saved to {target_file}\x1b[0m")

        click.echo(f"\n{Fore.GREEN}Translation completed.\x1b[0m")
        click.echo(
            f"To check the status of your translations, run: {Fore.BLUE}algebras status\x1b[0m"
        )

    except Exception as e:
        import traceback

        click.echo(f"{Fore.RED}Error: {str(e)}\x1b[0m")
        traceback.print_exc()


def _process_outdated_files(
    outdated_files: List[Tuple[str, str]],
    target_lang: str,
    translator,
    config,
    source_language: str,
    ui_safe: bool,
    glossary_id: Optional[str],
    only_missing: bool,
    regenerate_from_scratch: bool,
    xlf_target_state: str,
    xlf_version: str,
    po_mark_fuzzy: bool,
    verbose: bool,
) -> None:
    """
    Process outdated files by finding changed keys and translating them.

    Args:
        outdated_files: List of tuples (target_file, source_file) that are outdated
        target_lang: Target language code
        translator: Translator instance
        config: Config instance
        source_language: Source language code
        ui_safe: If True, ensure translations will not be longer than original text
        glossary_id: ID of the glossary to use for translation
        only_missing: Only translate keys that are missing in the target file
        regenerate_from_scratch: If True, regenerate files from scratch instead of updating in-place
        xlf_target_state: XLIFF target state
        xlf_version: XLIFF version
        po_mark_fuzzy: Whether to mark PO entries as fuzzy
        verbose: Verbose mode flag
    """
    for target_file, source_file in outdated_files:
        click.echo(
            f"\n{Fore.BLUE}Processing outdated file {os.path.basename(target_file)} for language '{target_lang}'...{Fore.RESET}"
        )

        try:
            # Get handler for file format
            handler = get_handler(source_file, config)

            # Load both source and target files using handler
            (
                source_content,
                target_content,
                source_raw_content,
                target_raw_content,
            ) = _load_file_contents(
                source_file,
                target_file,
                handler,
                source_language,
                target_lang,
                config,
                verbose,
                xlf_version,
            )

            # Extract all keys from both files
            if is_flat_format(detect_format(source_file)):
                source_keys = set(source_content.keys())
                target_keys = set(target_content.keys())
            else:
                source_keys = handler.extract_keys(source_content)
                target_keys = handler.extract_keys(target_content)

            # Find keys that exist in both files - these are potentially outdated
            common_keys = source_keys.intersection(target_keys)

            # Compare values to find potentially modified keys
            modified_keys = []
            for key in common_keys:
                if source_file.endswith((".html", ".xlf", ".xliff", ".csv", ".tsv")):
                    # For HTML, XLIFF, and CSV files, keys are flat, so compare values directly
                    source_value = source_content.get(key)
                    target_value = target_content.get(key)
                else:
                    key_parts = key.split(".")
                    source_value = get_nested_value(source_content, key_parts)
                    target_value = get_nested_value(target_content, key_parts)

                # If values are different, consider this key outdated
                if source_value != target_value and isinstance(source_value, str):
                    modified_keys.append(key)

            # Find keys only in source (missing keys)
            missing_keys = source_keys - target_keys

            # Also check for keys that exist in target but have empty values (for CSV/TSV and other flat formats)
            if is_flat_format(detect_format(source_file)):
                common_keys = source_keys & target_keys
                for key in common_keys:
                    target_value = target_content.get(key)
                    # Treat empty string values as missing keys
                    if target_value == "" or target_value is None:
                        missing_keys.add(key)

            # Report what we found
            if missing_keys:
                click.echo(
                    f"  {Fore.YELLOW}Found {len(missing_keys)} missing keys in {os.path.basename(target_file)}{Fore.RESET}"
                )

            if modified_keys:
                click.echo(
                    f"  {Fore.YELLOW}Found {len(modified_keys)} potentially outdated keys in {os.path.basename(target_file)}{Fore.RESET}"
                )
                # Print up to 5 modified keys as examples
                for key in modified_keys[:5]:
                    click.echo(f"    - {key}")
                if len(modified_keys) > 5:
                    click.echo(f"    - ... and {len(modified_keys) - 5} more")

            # Translate missing keys
            if missing_keys:
                click.echo(
                    f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys...{Fore.RESET}"
                )
                target_content = translator.translate_missing_keys_batch(
                    source_content,
                    target_content,
                    list(missing_keys),
                    target_lang,
                    ui_safe,
                    glossary_id,
                    source_file_path=source_file,
                )

            # Save updated content if there were changes
            if missing_keys or modified_keys:
                use_in_place = _should_use_in_place(
                    target_file, regenerate_from_scratch
                )
                keys_to_update = set(missing_keys) | set(modified_keys)

                # For TypeScript files, use incremental writer
                if target_file.endswith(".ts"):
                    # Determine export name
                    basename = os.path.basename(target_file)
                    export_name = basename.split(".")[0]

                    # Create incremental writer
                    incremental_writer = IncrementalFileWriter(
                        target_file, "ts", export_name
                    )

                    # Define callback for batch completion
                    def on_batch_complete(
                        batch_results: Dict[str, str], batch_index: int
                    ):
                        incremental_writer.write_batch(batch_results, batch_index)

                    # Translate missing keys with callback
                    if missing_keys:
                        target_content = translator.translate_missing_keys_batch(
                            source_content,
                            target_content,
                            list(missing_keys),
                            target_lang,
                            ui_safe,
                            glossary_id,
                            on_batch_complete=on_batch_complete,
                            source_file_path=source_file,
                        )

                    # Translate modified keys with callback
                    if modified_keys and not only_missing:
                        click.echo(
                            f"  {Fore.GREEN}Translating {len(modified_keys)} outdated keys...{Fore.RESET}"
                        )
                        target_content = translator.translate_outdated_keys_batch(
                            source_content,
                            target_content,
                            modified_keys,
                            target_lang,
                            ui_safe,
                            glossary_id,
                            on_batch_complete=on_batch_complete,
                        )

                    # Wait for all writes to complete
                    incremental_writer.finish()
                else:
                    # Translate missing keys if needed
                    if missing_keys:
                        target_content = translator.translate_missing_keys_batch(
                            source_content,
                            target_content,
                            list(missing_keys),
                            target_lang,
                            ui_safe,
                            glossary_id,
                            source_file_path=source_file,
                        )

                    # Translate modified keys if needed
                    if modified_keys and not only_missing:
                        click.echo(
                            f"  {Fore.GREEN}Translating {len(modified_keys)} outdated keys...{Fore.RESET}"
                        )
                        target_content = translator.translate_outdated_keys_batch(
                            source_content,
                            target_content,
                            modified_keys,
                            target_lang,
                            ui_safe,
                            glossary_id,
                        )

                    # Write using handler
                    _write_translated_content(
                        target_file,
                        target_content,
                        handler,
                        keys_to_update,
                        use_in_place,
                        source_file=source_file,
                        source_language=source_language,
                        target_language=target_lang,
                        xlf_target_state=xlf_target_state,
                        xlf_version=xlf_version,
                        po_mark_fuzzy=po_mark_fuzzy,
                        source_raw_content=source_raw_content,
                        target_raw_content=target_raw_content,
                        verbose=verbose,
                    )

                updated_count = len(missing_keys) + len(modified_keys)
                click.echo(
                    f"  {Fore.GREEN}✓ Updated {updated_count} keys in {target_file}\x1b[0m"
                )
            else:
                click.echo(
                    f"  {Fore.GREEN}No keys need to be updated in {os.path.basename(target_file)}\x1b[0m"
                )

        except Exception as e:
            click.echo(
                f"  {Fore.RED}Error processing outdated file {os.path.basename(target_file)}: {str(e)}\x1b[0m"
            )


def _process_missing_keys_files(
    missing_keys_files: List[Tuple[str, Set[str], str]],
    target_lang: str,
    translator,
    config,
    source_language: str,
    ui_safe: bool,
    glossary_id: Optional[str],
    regenerate_from_scratch: bool,
    xlf_target_state: str,
    xlf_version: str,
    po_mark_fuzzy: bool,
    verbose: bool,
) -> None:
    """
    Process files with specific missing keys.

    Args:
        missing_keys_files: List of tuples (target_file, missing_keys, source_file)
        target_lang: Target language code
        translator: Translator instance
        config: Config instance
        source_language: Source language code
        ui_safe: If True, ensure translations will not be longer than original text
        glossary_id: ID of the glossary to use for translation
        regenerate_from_scratch: If True, regenerate files from scratch instead of updating in-place
        xlf_target_state: XLIFF target state
        xlf_version: XLIFF version
        po_mark_fuzzy: Whether to mark PO entries as fuzzy
        verbose: Verbose mode flag
    """
    for target_file, missing_keys, source_file in missing_keys_files:
        click.echo(
            f"\n{Fore.BLUE}Processing file with missing keys {os.path.basename(target_file)}...{Fore.RESET}"
        )

        try:
            # Get handler for file format
            handler = get_handler(source_file, config)

            # Load both source and target files using handler
            (
                source_content,
                target_content,
                source_raw_content,
                target_raw_content,
            ) = _load_file_contents(
                source_file,
                target_file,
                handler,
                source_language,
                target_lang,
                config,
                verbose,
                xlf_version,
            )

            # Translate missing keys
            if missing_keys:
                click.echo(
                    f"  {Fore.GREEN}Translating {len(missing_keys)} missing keys...{Fore.RESET}"
                )
                target_content = translator.translate_missing_keys_batch(
                    source_content,
                    target_content,
                    list(missing_keys),
                    target_lang,
                    ui_safe,
                    glossary_id,
                    source_file_path=source_file,
                )

                # Save updated content
                use_in_place = _should_use_in_place(
                    target_file, regenerate_from_scratch
                )
                keys_to_update = set(missing_keys)

                # For TypeScript files, use incremental writer (special case)
                if detect_format(target_file) == FileFormat.TS:
                    # Determine export name
                    basename = os.path.basename(target_file)
                    export_name = basename.split(".")[0]

                    # Create incremental writer
                    incremental_writer = IncrementalFileWriter(
                        target_file, "ts", export_name
                    )

                    # Define callback for batch completion
                    def on_batch_complete(
                        batch_results: Dict[str, str], batch_index: int
                    ):
                        incremental_writer.write_batch(batch_results, batch_index)

                    # Translate only the missing keys with callback
                    target_content = translator.translate_missing_keys_batch(
                        source_content,
                        target_content,
                        list(missing_keys),
                        target_lang,
                        ui_safe,
                        glossary_id,
                        on_batch_complete=on_batch_complete,
                        source_file_path=source_file,
                    )

                    # Wait for all writes to complete
                    incremental_writer.finish()
                else:
                    # Translate missing keys
                    target_content = translator.translate_missing_keys_batch(
                        source_content,
                        target_content,
                        list(missing_keys),
                        target_lang,
                        ui_safe,
                        glossary_id,
                        source_file_path=source_file,
                    )

                    # Write using handler
                    _write_translated_content(
                        target_file,
                        target_content,
                        handler,
                        keys_to_update,
                        use_in_place,
                        source_file=source_file,
                        source_language=source_language,
                        target_language=target_lang,
                        xlf_target_state=xlf_target_state,
                        xlf_version=xlf_version,
                        po_mark_fuzzy=po_mark_fuzzy,
                        source_raw_content=source_raw_content,
                        target_raw_content=target_raw_content,
                        verbose=verbose,
                    )

                click.echo(
                    f"  {Fore.GREEN}✓ Updated {len(missing_keys)} keys in {target_file}\x1b[0m"
                )
        except Exception as e:
            click.echo(
                f"  {Fore.RED}Error processing file with missing keys {os.path.basename(target_file)}: {str(e)}\x1b[0m"
            )


def _process_outdated_keys_files(
    outdated_keys_files: List[Tuple[str, Set[str], str]],
    target_lang: str,
    translator,
    config,
    source_language: str,
    ui_safe: bool,
    glossary_id: Optional[str],
    only_missing: bool,
    regenerate_from_scratch: bool,
    xlf_target_state: str,
    xlf_version: str,
    po_mark_fuzzy: bool,
    verbose: bool,
) -> None:
    """
    Process files with specific outdated keys.

    Args:
        outdated_keys_files: List of tuples (target_file, outdated_keys, source_file)
        target_lang: Target language code
        translator: Translator instance
        config: Config instance
        source_language: Source language code
        ui_safe: If True, ensure translations will not be longer than original text
        glossary_id: ID of the glossary to use for translation
        only_missing: Only translate keys that are missing in the target file
        regenerate_from_scratch: If True, regenerate files from scratch instead of updating in-place
        xlf_target_state: XLIFF target state
        xlf_version: XLIFF version
        po_mark_fuzzy: Whether to mark PO entries as fuzzy
        verbose: Verbose mode flag
    """
    for target_file, outdated_keys, source_file in outdated_keys_files:
        if os.path.basename(target_file).startswith(target_lang):
            click.echo(
                f"\n{Fore.BLUE}Processing file with outdated keys {os.path.basename(target_file)}...{Fore.RESET}"
            )

            try:
                # Get handler for file format
                handler = get_handler(source_file, config)

                # Load both source and target files using handler
                (
                    source_content,
                    target_content,
                    source_raw_content,
                    target_raw_content,
                ) = _load_file_contents(
                    source_file,
                    target_file,
                    handler,
                    source_language,
                    target_lang,
                    config,
                    verbose,
                    xlf_version,
                )

                # Translate outdated keys
                if outdated_keys and not only_missing:
                    click.echo(
                        f"  {Fore.GREEN}Translating {len(outdated_keys)} outdated keys...{Fore.RESET}"
                    )

                    # Save updated content
                    use_in_place = _should_use_in_place(
                        target_file, regenerate_from_scratch
                    )
                    keys_to_update = set(outdated_keys)

                    # For TypeScript files, use incremental writer (special case)
                    if detect_format(target_file) == FileFormat.TS:
                        # Determine export name
                        basename = os.path.basename(target_file)
                        export_name = basename.split(".")[0]

                        # Create incremental writer
                        incremental_writer = IncrementalFileWriter(
                            target_file, "ts", export_name
                        )

                        # Define callback for batch completion
                        def on_batch_complete(
                            batch_results: Dict[str, str], batch_index: int
                        ):
                            incremental_writer.write_batch(batch_results, batch_index)

                        # Translate with callback
                        target_content = translator.translate_outdated_keys_batch(
                            source_content,
                            target_content,
                            list(outdated_keys),
                            target_lang,
                            ui_safe,
                            glossary_id,
                            on_batch_complete=on_batch_complete,
                        )

                        # Wait for all writes to complete
                        incremental_writer.finish()
                    else:
                        # Translate outdated keys
                        target_content = translator.translate_outdated_keys_batch(
                            source_content,
                            target_content,
                            list(outdated_keys),
                            target_lang,
                            ui_safe,
                            glossary_id,
                        )

                        # Write using handler
                        _write_translated_content(
                            target_file,
                            target_content,
                            handler,
                            keys_to_update,
                            use_in_place,
                            source_file=source_file,
                            source_language=source_language,
                            target_language=target_lang,
                            xlf_target_state=xlf_target_state,
                            xlf_version=xlf_version,
                            po_mark_fuzzy=po_mark_fuzzy,
                            source_raw_content=source_raw_content,
                            target_raw_content=target_raw_content,
                            verbose=verbose,
                        )

                    click.echo(
                        f"  {Fore.GREEN}✓ Updated {len(outdated_keys)} keys in {target_file}\x1b[0m"
                    )
            except Exception as e:
                click.echo(
                    f"  {Fore.RED}Error processing file with outdated keys {os.path.basename(target_file)}: {str(e)}\x1b[0m"
                )


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


def _load_file_contents(
    source_file: str,
    target_file: str,
    handler,
    source_language: str,
    target_language: str,
    config,
    verbose: bool = False,
    xlf_version: str = "1.2",
):
    """
    Load source and target file contents using handler.

    Args:
        source_file: Path to source file
        target_file: Path to target file
        handler: FileFormatHandler instance
        source_language: Source language code
        target_language: Target language code
        config: Config instance
        verbose: Verbose mode flag
        xlf_version: XLIFF version (for XLIFF files)

    Returns:
        Tuple of (source_content, target_content, source_raw_content, target_raw_content)
        raw_content may be None for formats that don't need it
    """
    source_raw_content = None
    target_raw_content = None

    # For formats that need raw content (XLIFF, StringsDict)
    format_type = detect_format(source_file)

    if format_type == FileFormat.XLIFF:
        # XLIFF needs raw content for version detection and structure preservation
        source_raw_content = handler.read(source_file)
        if verbose and source_raw_content and "version" in source_raw_content:
            detected_source_version = source_raw_content["version"]
            if detected_source_version != xlf_version:
                click.echo(
                    f"  {Fore.CYAN}Source file has XLIFF version {detected_source_version}, overriding config version {xlf_version}\x1b[0m"
                )

        if os.path.exists(target_file):
            target_raw_content = handler.read(target_file)
        else:
            # Create empty target with version from source file (if available) or config
            target_version = (
                source_raw_content.get("version", xlf_version)
                if source_raw_content
                else xlf_version
            )
            target_raw_content = {
                "version": target_version,
                "files": [],
            }
            if verbose:
                click.echo(
                    f"  {Fore.CYAN}Created new target file with XLIFF version {target_version}\x1b[0m"
                )

        source_content = handler.read_for_translation(
            source_file, source_language, config
        )
        target_content = (
            handler.read_for_translation(target_file, target_language, config)
            if os.path.exists(target_file)
            else {}
        )
    elif format_type == FileFormat.STRINGSDICT:
        # StringsDict needs raw content for structure preservation
        source_raw_content = handler.read(source_file)
        target_raw_content = (
            handler.read(target_file) if os.path.exists(target_file) else None
        )
        source_content = handler.read_for_translation(
            source_file, source_language, config
        )
        target_content = (
            handler.read_for_translation(target_file, target_language, config)
            if os.path.exists(target_file)
            else {}
        )
    elif format_type in (FileFormat.CSV, FileFormat.TSV):
        # CSV needs language-specific reading
        source_content = handler.read_for_translation(
            source_file, source_language, config
        )
        target_content = (
            handler.read_for_translation(target_file, target_language, config)
            if os.path.exists(target_file)
            else {}
        )
    else:
        # Standard reading for other formats
        source_content = handler.read_for_translation(
            source_file, source_language, config
        )
        target_content = (
            handler.read_for_translation(target_file, target_language, config)
            if os.path.exists(target_file)
            else {}
        )

    return source_content, target_content, source_raw_content, target_raw_content


def _write_translated_content(
    target_file: str,
    content: Dict[str, Any],
    handler,
    keys_to_update: Set[str],
    use_in_place: bool,
    source_file: Optional[str] = None,
    source_language: Optional[str] = None,
    target_language: Optional[str] = None,
    xlf_target_state: str = "translated",
    xlf_version: str = "1.2",
    po_mark_fuzzy: bool = False,
    source_raw_content: Optional[Dict[str, Any]] = None,
    target_raw_content: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
):
    """
    Write translated content to file using handler.

    Args:
        target_file: Path to target file
        content: Translated content dictionary
        handler: FileFormatHandler instance
        keys_to_update: Set of keys that were updated
        use_in_place: Whether to use in-place update
        source_file: Path to source file (required for HTML)
        source_language: Source language code (required for XLIFF)
        target_language: Target language code (required for XLIFF, CSV)
        xlf_target_state: XLIFF target state (for XLIFF files)
        xlf_version: XLIFF version (for XLIFF files)
        po_mark_fuzzy: Whether to mark PO entries as fuzzy
        source_raw_content: Raw source content (for XLIFF, StringsDict)
        target_raw_content: Raw target content (for XLIFF, StringsDict)
        verbose: Verbose mode flag
    """
    format_type = detect_format(target_file)

    # Prepare kwargs for handler.write()
    kwargs = {}

    if format_type == FileFormat.XLIFF:
        if source_language is None or target_language is None:
            raise ValueError("XLIFF write requires source_language and target_language")
        kwargs.update(
            {
                "source_language": source_language,
                "target_language": target_language,
                "xlf_target_state": xlf_target_state,
                "xlf_version": xlf_version,
                "raw_content": target_raw_content,
                "source_raw_content": source_raw_content,
            }
        )
    elif format_type == FileFormat.STRINGSDICT:
        kwargs["raw_content"] = target_raw_content
    elif format_type == FileFormat.HTML:
        if source_file is None:
            raise ValueError("HTML write requires source_file")
        kwargs["source_file"] = source_file
    elif format_type in (FileFormat.CSV, FileFormat.TSV):
        if target_language is None:
            raise ValueError("CSV/TSV write requires target_language")
        kwargs.update(
            {
                "target_language": target_language,
                "source_file": source_file,
            }
        )
    elif format_type == FileFormat.PO:
        kwargs["po_mark_fuzzy"] = po_mark_fuzzy

    # Write using handler
    if use_in_place and handler.supports_in_place():
        handler.write_in_place(target_file, content, keys_to_update, **kwargs)
    else:
        if use_in_place and not handler.supports_in_place():
            # Format doesn't support in-place, show warning
            click.echo(
                f"  {Fore.YELLOW}{format_type.value.upper()} format does not support in-place updates yet, regenerating from scratch{Fore.RESET}"
            )
        handler.write(target_file, content, **kwargs)
