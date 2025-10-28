"""HTTP clients for the LLM providers supported by the Darktable MCP server."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Iterable, List, Optional
from urllib import error, request

from .config import ProviderConfig

LOGGER = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    """Raised when a provider interaction fails."""


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
    """Send a JSON request and return the decoded response."""
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace") if exc.fp else exc.reason
        LOGGER.error("HTTP error for %s: %s", url, message)
        raise LLMClientError(f"HTTP {exc.code} error from provider: {message}") from exc
    except error.URLError as exc:
        LOGGER.error("Transport error for %s: %s", url, exc.reason)
        raise LLMClientError(f"Transport error contacting provider: {exc.reason}") from exc


class LMStudioClient:
    """Client for LM Studio's OpenAI-compatible API."""

    def __init__(self, config: ProviderConfig):
        self._config = config

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, temperature: float = 0.2) -> Dict[str, Any]:
        model_name = model or self._config.default_model
        if not model_name:
            raise LLMClientError("No model configured for LM Studio.")
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        url = f"{self._config.base_url.rstrip('/')}/v1/chat/completions"
        return _post_json(url, payload, self._headers(), self._config.timeout)

    def vision(self, prompt: str, image_data: Iterable[str], model: Optional[str] = None) -> Dict[str, Any]:
        """Perform a multimodal request combining text and images."""
        content: List[Dict[str, str]] = [{"type": "input_text", "text": prompt}]
        for image in image_data:
            content.append({"type": "input_image", "image": image})
        messages = [{"role": "user", "content": content}]
        return self.chat(messages, model=model)


class OllamaClient:
    """Client for the Ollama REST API."""

    def __init__(self, config: ProviderConfig):
        self._config = config

    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None) -> Dict[str, Any]:
        model_name = model or self._config.default_model
        if not model_name:
            raise LLMClientError("No model configured for Ollama.")
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }
        url = f"{self._config.base_url.rstrip('/')}/api/chat"
        return _post_json(url, payload, {"Content-Type": "application/json"}, self._config.timeout)

    def vision(self, prompt: str, image_data: Iterable[str], model: Optional[str] = None) -> Dict[str, Any]:
        message: Dict[str, Any] = {"role": "user", "content": prompt}
        images_list = list(image_data)
        if images_list:
            message["images"] = images_list
        return self.chat([message], model=model)


def encode_image_to_base64(path: str) -> str:
    """Encode a binary image file as a base64 data URI."""
    with open(path, "rb") as handle:
        raw = handle.read()
    encoded = base64.b64encode(raw).decode("ascii")
    return encoded


__all__ = [
    "LMStudioClient",
    "OllamaClient",
    "LLMClientError",
    "encode_image_to_base64",
]
