"""
Configuration module for Algebras CLI
"""

import os
import yaml
from typing import List, Dict, Any, Optional


class Config:
    """Configuration class for Algebras CLI."""
    
    CONFIG_FILE = ".algebras.config"
    
    def __init__(self):
        self.config_path = os.path.join(os.getcwd(), self.CONFIG_FILE)
        self.data = {}
    
    def exists(self) -> bool:
        """Check if the configuration file exists."""
        return os.path.exists(self.config_path)
    
    def load(self) -> Dict[str, Any]:
        """Load the configuration file."""
        if not self.exists():
            raise FileNotFoundError(f"Configuration file not found. Run 'algebras init' to create one.")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f) or {}
        
        return self.data
    
    def save(self) -> None:
        """Save the configuration file."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)
    
    def create_default(self) -> None:
        """Create a default configuration file."""
        if self.exists():
            return
        
        self.data = {
            "languages": ["en"],
            "path_rules": [
                "**/*.json",  # JSON files
                "**/*.yaml",  # YAML files
                "!**/node_modules/**",  # Exclude node_modules directory
                "!**/build/**",  # Exclude build directory
            ],
            "api": {
                "provider": "openai",
                "model": "gpt-4",
            }
        }
        
        self.save()
    
    def get_languages(self) -> List[str]:
        """Get the list of languages."""
        if not self.data:
            if not self.exists():
                return []
            self.load()
        
        return self.data.get("languages", [])
    
    def add_language(self, language: str) -> None:
        """Add a new language to the configuration."""
        if not self.data:
            self.load()
        
        languages = self.get_languages()
        if language in languages:
            return
        
        languages.append(language)
        self.data["languages"] = languages
        self.save()
    
    def get_path_rules(self) -> List[str]:
        """Get the list of path rules."""
        if not self.data:
            if not self.exists():
                return []
            self.load()
        
        return self.data.get("path_rules", [])
    
    def get_api_config(self) -> Dict[str, str]:
        """Get the API configuration."""
        if not self.data:
            if not self.exists():
                return {}
            self.load()
        
        return self.data.get("api", {}) 