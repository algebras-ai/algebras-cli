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
    
    def add_terms_bulk(self, glossary_id: str, terms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add multiple terms to a glossary in bulk.
        
        Args:
            glossary_id: ID of the glossary to add terms to
            terms: List of term dictionaries with definitions
            
        Returns:
            List of created term data
            
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
