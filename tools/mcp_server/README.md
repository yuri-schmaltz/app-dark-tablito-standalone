# Darktable MCP Server

This experimental server exposes a minimal [Model Context Protocol](https://github.com/modelcontextprotocol) style bridge so
`darktable` can orchestrate local large language models (LLMs) with vision support.  It focuses on integrating two popular local
runtimes:

* [LM Studio](https://lmstudio.ai/) via its OpenAI-compatible REST API
* [Ollama](https://ollama.com/) via its native REST interface

The service enables darktable automation scenarios like asking an LLM to describe a photo, proposing editing steps, or running
batch jobs over multiple images.

## Features

* `/chat` endpoint for general text interactions with either provider.
* `/analyze` endpoint that forwards an image (or multiple images) to a multimodal model for visual analysis.
* `/batch` endpoint that loops over a list of images using the same prompt, ideal for lighttable automation.
* `/config` endpoint exposing the active configuration for debugging.
* `/health` endpoint for simple readiness checks.

All responses include the provider name and the raw payload returned by the underlying LLM server.

## Installation

No additional dependencies are required beyond Python 3.8+.  The server relies on the standard library, so it can be executed
directly inside the darktable source tree:

```bash
python -m tools.mcp_server --host 0.0.0.0 --port 8082
```

The command above honours environment variables (documented below) and enables signal handling for clean shutdowns.

## Configuration

Environment variables let you adapt the bridge to your local setup:

| Variable | Description | Default |
| --- | --- | --- |
| `DARKTABLE_MCP_HOST` | Default bind address | `127.0.0.1` |
| `DARKTABLE_MCP_PORT` | Default bind port | `8082` |
| `DARKTABLE_MCP_PROVIDER` | Default provider (`lmstudio` or `ollama`) | `lmstudio` |
| `LM_STUDIO_URL` | Base URL for LM Studio | `http://localhost:1234` |
| `LM_STUDIO_API_KEY` | Optional API key for LM Studio | _none_ |
| `LM_STUDIO_MODEL` | Default LM Studio model name | `vision` |
| `LM_STUDIO_TIMEOUT` | Request timeout in seconds | `60` |
| `OLLAMA_URL` | Base URL for Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default Ollama model name | `llava` |
| `OLLAMA_TIMEOUT` | Request timeout in seconds | `60` |

CLI flags `--host`, `--port`, and `--provider` override the environment values.  Run `python -m tools.mcp_server --help` for a full
list of options.

## Request formats

### Chat

```http
POST /chat
Content-Type: application/json

{
  "provider": "lmstudio",
  "model": "gpt-vision",
  "messages": [
    {"role": "user", "content": "Suggest a tagging strategy for concert photos."}
  ]
}
```

`provider` is optional; when omitted the default provider is used.

### Single image analysis

```http
POST /analyze
Content-Type: application/json

{
  "prompt": "Describe the mood of this scene",
  "images": ["/path/to/image.nef"],
  "provider": "ollama",
  "model": "llava"
}
```

Each entry in `images` may be a filesystem path, an object with a `path` field, an object with a `base64` field (optionally with
`mime`), or a `data_uri`.  Paths are read and encoded automatically.

### Batch analysis

```http
POST /batch
Content-Type: application/json

{
  "prompt": "List three colour-grading suggestions",
  "images": [
    "/collection/shot1.cr2",
    "/collection/shot2.cr2"
  ],
  "provider": "lmstudio"
}
```

The response contains the original entry alongside the provider response for each processed image.

## Darktable integration ideas

* Use `curl` or a Lua script in darktable to send selected images to `/analyze` and annotate returned keywords.
* Combine with darktable's batch export hooks to trigger `/batch` before rendering JPEGs, letting an LLM verify exposure or
  generate captions.
* Run `/chat` interactions to request editing recipes; the replies can be parsed and translated into darktable styles.

These examples rely on LM Studio or Ollama running locally with multimodal models (e.g., `llava`, `bakllava`, or compatible
vision checkpoints).

## Safety considerations

The server trusts the caller.  If you expose it over a network, ensure your environment is secured (firewalls, VPN, etc.).
