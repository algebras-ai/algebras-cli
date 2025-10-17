"""
CSV parser utility for glossary files
"""

import csv
import click
from colorama import Fore
from typing import List, Dict, Any, Tuple
from pathlib import Path


class GlossaryCSVParser:
    """Parser for glossary CSV files with structure: Record ID, lang1, lang2, ..."""
    
    def __init__(self, csv_file_path: str):
        """
        Initialize the parser with a CSV file path.
        
        Args:
            csv_file_path: Path to the CSV file to parse
        """
        self.csv_file_path = Path(csv_file_path)
        if not self.csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
    
    def parse(self) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse the CSV file and extract language codes and terms.
        
        Returns:
            Tuple of (language_codes, terms_list)
            - language_codes: List of language codes from headers
            - terms_list: List of term dictionaries with definitions
            
        Raises:
            ValueError: If CSV format is invalid
        """
        language_codes = []
        terms = []
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                # Read the first line to get headers
                reader = csv.reader(file)
                headers = next(reader)
                
                if not headers or len(headers) < 2:
                    raise ValueError("CSV file must have at least 2 columns (Record ID and at least one language)")
                
                # Extract language codes (skip first column "Record ID")
                language_codes = headers[1:]
                
                if not language_codes:
                    raise ValueError("No language columns found in CSV file")
                
                # Validate that we have valid language codes
                for lang in language_codes:
                    if not lang or not lang.strip():
                        raise ValueError(f"Empty language code found in header: {headers}")
                
                # Parse each row
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because we read headers
                    if not row:  # Skip empty rows
                        continue
                    
                    if len(row) != len(headers):
                        click.echo(f"{Fore.YELLOW}Warning: Row {row_num} has {len(row)} columns, expected {len(headers)}. Skipping.{Fore.RESET}")
                        continue
                    
                    # First column is the Record ID (term identifier)
                    record_id = row[0].strip()
                    if not record_id:
                        click.echo(f"{Fore.YELLOW}Warning: Row {row_num} has empty Record ID. Skipping.{Fore.RESET}")
                        continue
                    
                    # Create definitions for each language
                    definitions = []
                    for i, lang_code in enumerate(language_codes):
                        term_text = row[i + 1].strip()  # +1 because first column is Record ID
                        
                        # Skip empty terms
                        if not term_text:
                            continue
                        
                        # Validate term text for potential issues
                        if len(term_text) > 1000:  # Reasonable limit for term length
                            click.echo(f"{Fore.YELLOW}Warning: Row {row_num}, language {lang_code}: Term too long ({len(term_text)} chars), truncating{Fore.RESET}")
                            term_text = term_text[:1000]
                        
                        # Check for problematic characters that might cause API issues
                        if '\x00' in term_text:  # Null bytes
                            click.echo(f"{Fore.YELLOW}Warning: Row {row_num}, language {lang_code}: Contains null bytes, removing{Fore.RESET}")
                            term_text = term_text.replace('\x00', '')
                        
                        # Validate language code format
                        if not lang_code or not isinstance(lang_code, str) or len(lang_code) < 2:
                            click.echo(f"{Fore.YELLOW}Warning: Row {row_num}: Invalid language code '{lang_code}', skipping{Fore.RESET}")
                            continue
                        
                        definitions.append({
                            "language": lang_code,
                            "term": term_text,
                            "definition": term_text  # Using term as definition for now
                        })
                    
                    # Only add term if it has at least one definition
                    if definitions:
                        terms.append({
                            "definitions": definitions
                        })
                    else:
                        click.echo(f"{Fore.YELLOW}Warning: Row {row_num} has no valid terms. Skipping.{Fore.RESET}")
        
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(self.csv_file_path, 'r', encoding='latin-1') as file:
                    reader = csv.reader(file)
                    headers = next(reader)
                    language_codes = headers[1:]
                    
                    for row_num, row in enumerate(reader, start=2):
                        if not row or len(row) != len(headers):
                            continue
                        
                        record_id = row[0].strip()
                        if not record_id:
                            continue
                        
                        definitions = []
                        for i, lang_code in enumerate(language_codes):
                            term_text = row[i + 1].strip()
                            if not term_text:
                                continue
                            
                            definitions.append({
                                "language": lang_code,
                                "term": term_text,
                                "definition": term_text
                            })
                        
                        if definitions:
                            terms.append({
                                "definitions": definitions
                            })
            except Exception as e:
                raise ValueError(f"Failed to parse CSV file: {str(e)}")
        
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file: {str(e)}")
        
        if not terms:
            raise ValueError("No valid terms found in CSV file")
        
        return language_codes, terms
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the CSV file without parsing all terms.
        
        Returns:
            Dictionary with file summary information
        """
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                headers = next(reader)
                language_codes = headers[1:] if len(headers) > 1 else []
                
                # Count total rows
                total_rows = 1  # Headers
                for row in reader:
                    if row:  # Count non-empty rows
                        total_rows += 1
                
                return {
                    "file_path": str(self.csv_file_path),
                    "total_rows": total_rows,
                    "language_codes": language_codes,
                    "total_languages": len(language_codes)
                }
        except Exception as e:
            return {
                "file_path": str(self.csv_file_path),
                "error": str(e)
            }
