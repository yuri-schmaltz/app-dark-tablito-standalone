"""HTTP entry point for the Darktable MCP server."""
from __future__ import annotations

import json
import logging
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from .clients import (
    LMStudioClient,
    LLMClientError,
    OllamaClient,
    encode_image_to_base64,
)
from .config import MCPServerConfig

LOGGER = logging.getLogger(__name__)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Simple multi-threaded HTTP server."""

    daemon_threads = True


class MCPServerState:
    """Holds state shared across HTTP requests."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._clients: Dict[str, Any] = {
            "lmstudio": LMStudioClient(config.lm_studio),
            "ollama": OllamaClient(config.ollama),
        }
        LOGGER.debug("Loaded MCP server configuration: %s", self.config.as_dict())

    def get_client(self, provider: str | None) -> Tuple[str, Any]:
        provider_name = (provider or self.config.default_provider).lower()
        if provider_name not in self._clients:
            raise ValueError(f"Unsupported provider '{provider_name}'.")
        return provider_name, self._clients[provider_name]

    def chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider_name, client = self.get_client(payload.get("provider"))
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("'messages' must be a non-empty list.")
        model = payload.get("model")
        temperature = payload.get("temperature", 0.2)
        if hasattr(client, "chat"):
            return {
                "provider": provider_name,
                "response": client.chat(messages, model=model, temperature=temperature)  # type: ignore[arg-type]
                if provider_name == "lmstudio"
                else client.chat(messages, model=model),
            }
        raise ValueError(f"Provider '{provider_name}' does not support chat operations.")

    def vision(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider_name, client = self.get_client(payload.get("provider"))
        prompt = payload.get("prompt") or "Describe the image"
        images = payload.get("images")
        if not isinstance(images, list) or not images:
            raise ValueError("'images' must be a non-empty list.")
        prepared_images = self._prepare_images(provider_name, images)
        model = payload.get("model")
        if not hasattr(client, "vision"):
            raise ValueError(f"Provider '{provider_name}' does not support vision analysis.")
        response = client.vision(prompt, prepared_images, model=model)
        return {
            "provider": provider_name,
            "response": response,
        }

    def batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider_name, client = self.get_client(payload.get("provider"))
        prompt = payload.get("prompt") or "Describe the image"
        items = payload.get("images")
        if not isinstance(items, list) or not items:
            raise ValueError("'images' must be a non-empty list.")
        model = payload.get("model")
        if not hasattr(client, "vision"):
            raise ValueError(f"Provider '{provider_name}' does not support batch vision analysis.")
        results: List[Dict[str, Any]] = []
        for image_entry in items:
            prepared = self._prepare_images(provider_name, [image_entry])
            response = client.vision(prompt, prepared, model=model)
            results.append({"image": image_entry, "response": response})
        return {"provider": provider_name, "results": results}

    def _prepare_images(self, provider: str, entries: Iterable[Any]) -> List[str]:
        prepared: List[str] = []
        for entry in entries:
            encoded, mime_type = self._normalise_image_entry(entry)
            prepared.append(self._format_for_provider(provider, encoded, mime_type))
        return prepared

    def _normalise_image_entry(self, entry: Any) -> Tuple[str, str | None]:
        if isinstance(entry, str):
            return self._load_image(entry)
        if isinstance(entry, dict):
            if "data_uri" in entry:
                value = entry["data_uri"]
                return value, None
            if "base64" in entry:
                return entry["base64"], entry.get("mime")
            if "path" in entry:
                return self._load_image(entry["path"], mime_hint=entry.get("mime"))
        raise ValueError("Unsupported image entry format. Use a path string or an object with 'path', 'base64' or 'data_uri'.")

    def _load_image(self, path: str, mime_hint: str | None = None) -> Tuple[str, str | None]:
        mime_type = mime_hint or mimetypes.guess_type(path)[0]
        encoded = encode_image_to_base64(path)
        return encoded, mime_type

    def _format_for_provider(self, provider: str, encoded: str, mime_type: str | None) -> str:
        if provider == "lmstudio":
            if encoded.startswith("data:"):
                return encoded
            mime = mime_type or "image/png"
            return f"data:{mime};base64,{encoded}"
        if provider == "ollama":
            if encoded.startswith("data:"):
                _, _, data = encoded.partition(",")
                return data
            return encoded
        return encoded


class MCPRequestHandler(BaseHTTPRequestHandler):
    server_version = "DarktableMCP/0.1"

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _parse_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Missing request body")
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc.msg}") from exc

    def do_OPTIONS(self) -> None:  # noqa: N802 (http method name)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        if parsed.path == "/config":
            state: MCPServerState = self.server.state  # type: ignore[attr-defined]
            self._send_json(200, state.config.as_dict())
            return
        self._send_json(404, {"error": "Unknown endpoint"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._parse_json()
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        state: MCPServerState = self.server.state  # type: ignore[attr-defined]
        try:
            if parsed.path == "/chat":
                result = state.chat(payload)
            elif parsed.path == "/analyze":
                result = state.vision(payload)
            elif parsed.path == "/batch":
                result = state.batch(payload)
            else:
                self._send_json(404, {"error": "Unknown endpoint"})
                return
            self._send_json(200, result)
        except (ValueError, LLMClientError) as exc:
            LOGGER.error("Request processing failed: %s", exc)
            self._send_json(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive programming
            LOGGER.exception("Unexpected server error")
            self._send_json(500, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 (shadowing)
        LOGGER.info("%s - %s", self.client_address[0], format % args)


class MCPServer:
    """Convenience wrapper to start and stop the HTTP server."""

    def __init__(self, config: MCPServerConfig):
        self._config = config
        self._state = MCPServerState(config)
        self._httpd = ThreadedHTTPServer((config.host, config.port), MCPRequestHandler)
        self._httpd.state = self._state  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    @property
    def config(self) -> MCPServerConfig:
        return self._config

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Server already running")
        LOGGER.info("Starting MCP server on %s:%s", self._config.host, self._config.port)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def wait_forever(self) -> None:
        try:
            self._httpd.serve_forever()
        except KeyboardInterrupt:  # pragma: no cover - manual shutdown
            LOGGER.info("Shutting down after interrupt")
        finally:
            self.stop()

    def stop(self) -> None:
        LOGGER.info("Stopping MCP server")
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


def create_server(config: MCPServerConfig | None = None) -> MCPServer:
    """Factory helper for external callers."""
    return MCPServer(config or MCPServerConfig.from_env())


__all__ = [
    "MCPServer",
    "MCPServerState",
    "MCPRequestHandler",
    "create_server",
]
