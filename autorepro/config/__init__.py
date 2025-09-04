"""Configuration system for AutoRepro."""

from .models import AutoReproConfig, get_config, reset_config

# Global configuration instance
config = get_config()

__all__ = ["AutoReproConfig", "config", "get_config", "reset_config"]
