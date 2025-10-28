"""Command line entry point for the Darktable MCP server."""
from __future__ import annotations

import argparse
import logging
import signal
from dataclasses import replace
from typing import Optional

from .config import MCPServerConfig
from .server import create_server

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Darktable MCP bridge server.")
    parser.add_argument("--host", default=None, help="Host/IP address to bind (default: env or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: env or 8082)")
    parser.add_argument(
        "--provider",
        choices=["lmstudio", "ollama"],
        default=None,
        help="Default provider used when requests do not specify one.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity.",
    )
    return parser


def _apply_overrides(config: MCPServerConfig, host: Optional[str], port: Optional[int], provider: Optional[str]) -> MCPServerConfig:
    updated = config
    if host is not None:
        updated = replace(updated, host=host)
    if port is not None:
        updated = replace(updated, port=port)
    if provider is not None:
        updated = replace(updated, default_provider=provider)
    return updated


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="[%(levelname)s] %(name)s: %(message)s")

    config = MCPServerConfig.from_env()
    config = _apply_overrides(config, args.host, args.port, args.provider)

    server = create_server(config)

    def _shutdown(signum: int, frame) -> None:  # type: ignore[override]
        LOGGER.info("Received signal %s, shutting down...", signum)
        server.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    LOGGER.info(
        "MCP server ready on %s:%s (default provider: %s)",
        server.config.host,
        server.config.port,
        server.config.default_provider,
    )
    server.wait_forever()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
