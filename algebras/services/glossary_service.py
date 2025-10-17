"""
Glossary service for managing glossaries via Algebras AI API
"""

import os
import requests
import click
from colorama import Fore
from typing import List, Dict, Any, Optional


class GlossaryService:
    """Service for managing glossaries through the Algebras AI API."""
    
    def __init__(self, config):
        """Initialize the glossary service with configuration."""
        self.config = config
    
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
    
    def add_terms_bulk(self, glossary_id: str, terms: List[Dict[str, Any]]) -> Dict[str, Any]:
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
        """
        base_url = self.config.get_base_url()
        url = f"{base_url}/api/v1/translation/glossaries/{glossary_id}/terms/bulk"
        
        data = {
            "terms": terms
        }
        
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
