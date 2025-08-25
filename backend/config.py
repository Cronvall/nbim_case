"""
Configuration module for loading prompts and settings.
"""
import json
import os
from typing import Dict, Any


class PromptConfig:
    """Handles loading and managing AI prompts from JSON configuration."""
    
    def __init__(self, config_file: str = "prompts.json"):
        self.config_file = config_file
        self._prompts = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompts from JSON configuration file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompts configuration file '{self.config_file}' not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in prompts configuration file: {e}")
    
    def get_prompt(self, prompt_key: str) -> str:
        """Get a prompt template by key."""
        if prompt_key not in self._prompts:
            raise KeyError(f"Prompt '{prompt_key}' not found in configuration")
        
        return self._prompts[prompt_key]["template"]
    
    def get_prompt_description(self, prompt_key: str) -> str:
        """Get the description of a prompt."""
        if prompt_key not in self._prompts:
            raise KeyError(f"Prompt '{prompt_key}' not found in configuration")
        
        return self._prompts[prompt_key].get("description", "No description available")
    
    def list_available_prompts(self) -> Dict[str, str]:
        """List all available prompts with their descriptions."""
        return {
            key: config.get("description", "No description available")
            for key, config in self._prompts.items()
        }
    
    def reload_prompts(self):
        """Reload prompts from the configuration file."""
        self._prompts = self._load_prompts()


# Global instance for easy access
prompt_config = PromptConfig()
