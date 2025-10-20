"""
Glossary service for managing glossaries via Algebras AI API
"""

import os
import requests
import click
import json
from colorama import Fore
from typing import List, Dict, Any, Optional


class PayloadTooLargeError(Exception):
    """Raised when request payload exceeds size limit."""
    pass


class GlossaryService:
    """Service for managing glossaries through the Algebras AI API."""
    
    def __init__(self, config, debug: bool = False):
        """Initialize the glossary service with configuration."""
        self.config = config
        self.debug = debug
    
    def _get_api_key(self) -> str:
        """Get the API key from environment variables."""
        api_key = os.environ.get("ALGEBRAS_API_KEY")
        if not api_key:
            raise ValueError("Algebras API key not found. Set the ALGEBRAS_API_KEY environment variable.")
        return api_key
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self._get_api_key()
        }
    
    def create_glossary(self, name: str, languages: List[str]) -> Dict[str, Any]:
        """
        Create a new glossary with the specified name and languages.
        
        Args:
            name: Name of the glossary
            languages: List of language codes
            
        Returns:
            Dictionary containing the created glossary data
            
        Raises:
            ValueError: If API key is not set
            requests.RequestException: If API request fails
        """
        base_url = self.config.get_base_url()
        url = f"{base_url}/api/v1/translation/glossaries"
        
        data = {
            "name": name,
            "languages": languages
        }
        
        if self.debug:
            click.echo(f"{Fore.CYAN}[DEBUG] POST {url}{Fore.RESET}")
            click.echo(f"{Fore.CYAN}[DEBUG] Request body: {json.dumps(data, indent=2)}{Fore.RESET}")
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "ok" and "data" in result:
                return result["data"]
            else:
                raise requests.RequestException(f"API returned error: {result.get('error', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                except:
                    error_msg = str(e)
            else:
                error_msg = str(e)
            raise requests.RequestException(f"Failed to create glossary: {error_msg}")
    
    def add_terms_bulk(self, glossary_id: str, terms: List[Dict[str, Any]], debug: bool = False) -> Dict[str, Any]:
        """
        Add multiple terms to a glossary in bulk.
        
        Args:
            glossary_id: ID of the glossary to add terms to
            terms: List of term dictionaries with definitions
            
        Returns:
            Dictionary containing the result with status, successful terms, and failed terms:
            {
                "status": "ok" | "partial_success",
                "successful": List of created term data,
                "failed": List of failed term data with error details,
                "successCount": int,
                "failedCount": int
            }
            
        Raises:
            ValueError: If API key is not set
            requests.RequestException: If API request fails
            PayloadTooLargeError: If request payload exceeds 500KB limit
        """
        base_url = self.config.get_base_url()
        url = f"{base_url}/api/v1/translation/glossaries/{glossary_id}/terms/bulk"
        
        data = {
            "terms": terms
        }
        
        # Calculate request size
        payload_size = len(json.dumps(data).encode('utf-8'))
        
        # Check if payload exceeds 500KB
        if payload_size > 512000:  # 500KB in bytes
            raise PayloadTooLargeError(f"Request size ({payload_size} bytes) exceeds 500KB limit")
        
        # Use debug flag from parameter or instance variable
        should_debug = debug or self.debug
        
        if should_debug:
            click.echo(f"{Fore.CYAN}[DEBUG] POST {url}{Fore.RESET}")
            click.echo(f"{Fore.CYAN}[DEBUG] Payload size: {payload_size} bytes ({payload_size / 1024:.2f} KB){Fore.RESET}")
            click.echo(f"{Fore.CYAN}[DEBUG] Number of terms: {len(terms)}{Fore.RESET}")
            # Log first few terms as a sample (don't log all terms as it can be too verbose)
            if len(terms) > 0:
                sample_terms = terms[:3] if len(terms) > 3 else terms
                click.echo(f"{Fore.CYAN}[DEBUG] Sample terms (first {len(sample_terms)}): {json.dumps(sample_terms, indent=2)}{Fore.RESET}")
        
        try:
            response = requests.post(url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            
            result = response.json()
            status = result.get("status")
            
            if status == "ok":
                # All terms created successfully
                return {
                    "status": "ok",
                    "successful": result.get("data", []),
                    "failed": [],
                    "successCount": len(result.get("data", [])),
                    "failedCount": 0
                }
            elif status == "partial_success":
                # Some terms created, some failed
                data = result.get("data", {})
                return {
                    "status": "partial_success",
                    "successful": data.get("successful", []),
                    "failed": data.get("failed", []),
                    "successCount": data.get("successCount", 0),
                    "failedCount": data.get("failedCount", 0)
                }
            else:
                raise requests.RequestException(f"API returned error: {result.get('error', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    # Try to get more detailed error information
                    if 'details' in error_data.get('error', {}):
                        error_msg += f" Details: {error_data['error']['details']}"
                    if 'validation_errors' in error_data:
                        error_msg += f" Validation errors: {error_data['validation_errors']}"
                except:
                    error_msg = str(e)
                    # Try to get response text for more details
                    try:
                        if hasattr(e, 'response') and e.response is not None:
                            error_msg += f" Response: {e.response.text[:500]}"
                    except:
                        pass
            else:
                error_msg = str(e)
            raise requests.RequestException(f"Failed to add terms to glossary: {error_msg}")
    
    def get_glossary(self, glossary_id: str) -> Dict[str, Any]:
        """
        Get a glossary by ID.
        
        Args:
            glossary_id: ID of the glossary to retrieve
            
        Returns:
            Dictionary containing the glossary data
            
        Raises:
            ValueError: If API key is not set
            requests.RequestException: If API request fails
        """
        base_url = self.config.get_base_url()
        url = f"{base_url}/api/v1/translation/glossaries/{glossary_id}"
        
        if self.debug:
            click.echo(f"{Fore.CYAN}[DEBUG] GET {url}{Fore.RESET}")
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") == "ok" and "data" in result:
                return result["data"]
            else:
                raise requests.RequestException(f"API returned error: {result.get('error', 'Unknown error')}")
                
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                except:
                    error_msg = str(e)
            else:
                error_msg = str(e)
            raise requests.RequestException(f"Failed to get glossary: {error_msg}")
