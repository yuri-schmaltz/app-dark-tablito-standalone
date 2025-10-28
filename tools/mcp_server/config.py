"""Configuration helpers for the Darktable MCP server.

This module centralises environment variable parsing so that
behaviour can be adjusted without editing the source code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import os


@dataclass
class ProviderConfig:
    """Holds settings for a single LLM provider."""

    base_url: str
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    timeout: float = 60.0

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Return a serialisable representation."""
        return {
            "base_url": self.base_url,
            "api_key": "<hidden>" if self.api_key else None,
            "default_model": self.default_model,
            "timeout": self.timeout,
        }


@dataclass
class MCPServerConfig:
    """Top-level server configuration."""

    host: str = "127.0.0.1"
    port: int = 8082
    default_provider: str = "lmstudio"
    lm_studio: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(
            base_url=os.environ.get("LM_STUDIO_URL", "http://localhost:1234"),
            api_key=os.environ.get("LM_STUDIO_API_KEY"),
            default_model=os.environ.get("LM_STUDIO_MODEL", "vision"),
            timeout=float(os.environ.get("LM_STUDIO_TIMEOUT", "60")),
        )
    )
    ollama: ProviderConfig = field(
        default_factory=lambda: ProviderConfig(
            base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            default_model=os.environ.get("OLLAMA_MODEL", "llava"),
            timeout=float(os.environ.get("OLLAMA_TIMEOUT", "60")),
        )
    )

    @classmethod
    def from_env(cls) -> "MCPServerConfig":
        """Create a configuration instance reading from environment variables."""
        host = os.environ.get("DARKTABLE_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("DARKTABLE_MCP_PORT", "8082"))
        default_provider = os.environ.get("DARKTABLE_MCP_PROVIDER", "lmstudio")
        config = cls(host=host, port=port, default_provider=default_provider)
        return config

    def as_dict(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Expose configuration details for diagnostics without secrets."""
        return {
            "host": self.host,
            "port": self.port,
            "default_provider": self.default_provider,
            "providers": {
                "lmstudio": self.lm_studio.to_dict(),
                "ollama": self.ollama.to_dict(),
            },
        }


__all__ = ["ProviderConfig", "MCPServerConfig"]
