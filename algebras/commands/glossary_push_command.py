"""
Glossary push command implementation
"""

import click
from colorama import Fore
from typing import List, Dict, Any
from pathlib import Path

from algebras.config import Config
from algebras.services.glossary_service import GlossaryService, PayloadTooLargeError
from algebras.utils.csv_parser import GlossaryCSVParser, GlossaryXLSXParser


def _upload_terms_adaptive(glossary_service: GlossaryService, glossary_id: str, terms: List[Dict[str, Any]], 
                          batch_num: int, total_batches: int) -> Dict[str, Any]:
    """
    Upload terms with adaptive batch sizing to handle payload size limits.
    
    Args:
        glossary_service: The glossary service instance
        glossary_id: ID of the glossary to add terms to
        terms: List of terms to upload
        batch_num: Current batch number for logging
        total_batches: Total number of batches for logging
        
    Returns:
        Dictionary containing upload results
    """
    try:
        result = glossary_service.add_terms_bulk(glossary_id, terms)
        return result
    except PayloadTooLargeError as e:
        # If batch is too large, split it in half
        if len(terms) <= 1:
            # Edge case: single term is too large, skip it
            click.echo(f"{Fore.RED}⚠ Skipping term that exceeds size limit: {str(e)}{Fore.RESET}")
            return {
                "status": "partial_success",
                "successful": [],
                "failed": [{"error": "Term too large", "details": str(e)}],
                "successCount": 0,
                "failedCount": 1
            }
        
        # Split batch in half
        mid_point = len(terms) // 2
        first_half = terms[:mid_point]
        second_half = terms[mid_point:]
        
        click.echo(f"{Fore.YELLOW}⚠ Batch {batch_num} too large ({len(terms)} terms), splitting into smaller batches...{Fore.RESET}")
        
        # Recursively process each half
        first_result = _upload_terms_adaptive(glossary_service, glossary_id, first_half, batch_num, total_batches)
        second_result = _upload_terms_adaptive(glossary_service, glossary_id, second_half, batch_num, total_batches)
        
        # Combine results
        combined_successful = first_result.get("successful", []) + second_result.get("successful", [])
        combined_failed = first_result.get("failed", []) + second_result.get("failed", [])
        combined_success_count = first_result.get("successCount", 0) + second_result.get("successCount", 0)
        combined_failed_count = first_result.get("failedCount", 0) + second_result.get("failedCount", 0)
        
        return {
            "status": "partial_success" if combined_failed_count > 0 else "ok",
            "successful": combined_successful,
            "failed": combined_failed,
            "successCount": combined_success_count,
            "failedCount": combined_failed_count
        }


def execute(csv_file: str, name: str) -> None:
    """
    Execute the glossary push command.
    
    Args:
        csv_file: Path to the CSV or XLSX file containing glossary terms
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
        
        # Detect file type and create appropriate parser
        file_path = Path(csv_file)
        file_extension = file_path.suffix.lower()
        
        if file_extension == '.xlsx':
            click.echo(f"{Fore.BLUE}Parsing XLSX file: {csv_file}{Fore.RESET}")
            parser = GlossaryXLSXParser(csv_file)
        elif file_extension == '.csv':
            click.echo(f"{Fore.BLUE}Parsing CSV file: {csv_file}{Fore.RESET}")
            parser = GlossaryCSVParser(csv_file)
        else:
            click.echo(f"{Fore.RED}Error: Unsupported file type '{file_extension}'. Only .csv and .xlsx files are supported.{Fore.RESET}")
            return
        
        # Get file summary first
        summary = parser.get_summary()
        if "error" in summary:
            click.echo(f"{Fore.RED}Error parsing file: {summary['error']}{Fore.RESET}")
            return
        
        click.echo(f"Found {summary['total_rows'] - 1} terms in {summary['total_languages']} languages")
        click.echo(f"Languages: {', '.join(summary['language_codes'])}")
        
        # Parse the actual data
        language_codes, terms = parser.parse()
        
        if not terms:
            click.echo(f"{Fore.RED}Error: No valid terms found in file{Fore.RESET}")
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
        
        # Upload terms in batches of 500
        batch_size = 100
        total_batches = (len(terms) + batch_size - 1) // batch_size
        
        click.echo(f"{Fore.BLUE}Uploading {len(terms)} terms in {total_batches} batches of {batch_size}...{Fore.RESET}")
        
        total_successful = 0
        total_failed = 0
        batch_results = []
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(terms))
            batch_terms = terms[start_idx:end_idx]
            
            click.echo(f"Uploading batch {batch_num + 1}/{total_batches} ({len(batch_terms)} terms)...")
            
            try:
                result = _upload_terms_adaptive(glossary_service, glossary_id, batch_terms, batch_num + 1, total_batches)
                batch_results.append(result)
                
                # Update counters based on result status
                if result["status"] == "ok":
                    total_successful += result["successCount"]
                    click.echo(f"{Fore.GREEN}✓ Batch {batch_num + 1} uploaded successfully ({result['successCount']} terms){Fore.RESET}")
                elif result["status"] == "partial_success":
                    total_successful += result["successCount"]
                    total_failed += result["failedCount"]
                    click.echo(f"{Fore.YELLOW}⚠ Batch {batch_num + 1} partially successful ({result['successCount']} successful, {result['failedCount']} failed){Fore.RESET}")
                    
                    # Show details of failed terms in this batch
                    if result["failed"]:
                        click.echo(f"{Fore.RED}  Failed terms:{Fore.RESET}")
                        for failed_term in result["failed"]:
                            error_msg = failed_term.get("error", "Unknown error")
                            details = failed_term.get("details", "")
                            click.echo(f"    - Index {failed_term.get('index', '?')}: {error_msg}")
                            if details:
                                click.echo(f"      Details: {details}")
                
            except Exception as e:
                total_failed += len(batch_terms)
                click.echo(f"{Fore.RED}✗ Batch {batch_num + 1} failed completely: {str(e)}{Fore.RESET}")
                # Continue with next batch instead of stopping completely
                continue
        
        # Summary
        click.echo(f"\n{Fore.BLUE}=== Upload Summary ==={Fore.RESET}")
        click.echo(f"Glossary ID: {glossary_id}")
        click.echo(f"Glossary Name: {name}")
        click.echo(f"Languages: {', '.join(language_codes)}")
        click.echo(f"Total terms: {len(terms)}")
        click.echo(f"{Fore.GREEN}Successful uploads: {total_successful}{Fore.RESET}")
        if total_failed > 0:
            click.echo(f"{Fore.RED}Failed uploads: {total_failed}{Fore.RESET}")
        
        # Overall status
        if total_failed == 0:
            click.echo(f"{Fore.GREEN}✓ Glossary push completed successfully! All terms uploaded.{Fore.RESET}")
        elif total_successful > 0:
            click.echo(f"{Fore.YELLOW}⚠ Glossary push completed with partial success. {total_successful} terms uploaded, {total_failed} failed.{Fore.RESET}")
        else:
            click.echo(f"{Fore.RED}✗ No terms were uploaded successfully{Fore.RESET}")
    
    except FileNotFoundError as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
    except ValueError as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}")
    except Exception as e:
        click.echo(f"{Fore.RED}Unexpected error: {str(e)}{Fore.RESET}")
