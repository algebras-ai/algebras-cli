"""
Glossary push command implementation
"""

import click
from colorama import Fore
from typing import List, Dict, Any

from algebras.config import Config
from algebras.services.glossary_service import GlossaryService
from algebras.utils.csv_parser import GlossaryCSVParser


def execute(csv_file: str, name: str) -> None:
    """
    Execute the glossary push command.
    
    Args:
        csv_file: Path to the CSV file containing glossary terms
        name: Name of the glossary to create
    """
    try:
        # Load configuration
        config = Config()
        if not config.exists():
            click.echo(f"{Fore.RED}Error: No configuration found. Run 'algebras init' first.{Fore.RESET}")
            return
        
        config.load()
        
        # Initialize services
        glossary_service = GlossaryService(config)
        
        # Parse CSV file
        click.echo(f"{Fore.BLUE}Parsing CSV file: {csv_file}{Fore.RESET}")
        parser = GlossaryCSVParser(csv_file)
        
        # Get file summary first
        summary = parser.get_summary()
        if "error" in summary:
            click.echo(f"{Fore.RED}Error parsing CSV file: {summary['error']}{Fore.RESET}")
            return
        
        click.echo(f"Found {summary['total_rows'] - 1} terms in {summary['total_languages']} languages")
        click.echo(f"Languages: {', '.join(summary['language_codes'])}")
        
        # Parse the actual data
        language_codes, terms = parser.parse()
        
        if not terms:
            click.echo(f"{Fore.RED}Error: No valid terms found in CSV file{Fore.RESET}")
            return
        
        click.echo(f"{Fore.GREEN}Successfully parsed {len(terms)} terms{Fore.RESET}")
        
        # Create glossary
        click.echo(f"{Fore.BLUE}Creating glossary '{name}' with languages: {', '.join(language_codes)}{Fore.RESET}")
        
        try:
            glossary_data = glossary_service.create_glossary(name, language_codes)
            glossary_id = glossary_data.get("id")
            click.echo(f"{Fore.GREEN}✓ Glossary created successfully with ID: {glossary_id}{Fore.RESET}")
        except Exception as e:
            click.echo(f"{Fore.RED}Error creating glossary: {str(e)}{Fore.RESET}")
            return
        
        # Upload terms in batches of 100
        batch_size = 500
        total_batches = (len(terms) + batch_size - 1) // batch_size
        
        click.echo(f"{Fore.BLUE}Uploading {len(terms)} terms in {total_batches} batches of {batch_size}...{Fore.RESET}")
        
        successful_terms = 0
        failed_terms = 0
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(terms))
            batch_terms = terms[start_idx:end_idx]
            
            click.echo(f"Uploading batch {batch_num + 1}/{total_batches} ({len(batch_terms)} terms)...")
            
            try:
                result = glossary_service.add_terms_bulk(glossary_id, batch_terms)
                successful_terms += len(batch_terms)
                click.echo(f"{Fore.GREEN}✓ Batch {batch_num + 1} uploaded successfully{Fore.RESET}")
            except Exception as e:
                failed_terms += len(batch_terms)
                click.echo(f"{Fore.RED}✗ Batch {batch_num + 1} failed: {str(e)}{Fore.RESET}")
                # Continue with next batch instead of stopping completely
                continue
        
        # Summary
        click.echo(f"\n{Fore.BLUE}=== Upload Summary ==={Fore.RESET}")
        click.echo(f"Glossary ID: {glossary_id}")
        click.echo(f"Glossary Name: {name}")
        click.echo(f"Languages: {', '.join(language_codes)}")
        click.echo(f"Total terms: {len(terms)}")
        click.echo(f"Successful uploads: {successful_terms}")
        if failed_terms > 0:
            click.echo(f"{Fore.RED}Failed uploads: {failed_terms}{Fore.RESET}")
        
        if successful_terms > 0:
            click.echo(f"{Fore.GREEN}✓ Glossary push completed successfully!{Fore.RESET}")
        else:
            click.echo(f"{Fore.RED}✗ No terms were uploaded successfully{Fore.RESET}")
    
    except FileNotFoundError as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
    except ValueError as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
    except Exception as e:
        click.echo(f"{Fore.RED}Unexpected error: {str(e)}{Fore.RESET}")
