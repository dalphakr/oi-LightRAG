# LightRAG MCP (Query Only)

Query-only MCP server that calls LightRAG directly (no file indexing).

## Setup

```bash
cd mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ..
pip install -r requirements.txt
cp ../env.example .env
# edit .env for LLM/Embedding + storage settings
```

## Run (stdio)

Run through an MCP client (recommended). Stdio servers expect JSON-RPC on stdin,
so running `python server.py` directly in a terminal will show parse errors.

```bash
npx @modelcontextprotocol/inspector python server.py
```

## Run (SSE for external access)

Expose an HTTP SSE endpoint so other machines can connect (defaults to 127.0.0.1:8000):

```bash
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=3000 python server.py
```

From another machine:

```bash
npx @modelcontextprotocol/inspector http://<server-ip>:3000/sse
```

Make sure the port is open in your firewall/security group.

## Tools

- `rag_query`: returns `{response, references}`
- `rag_query_data`: returns structured retrieval data (entities/relations/chunks)

Example input:

```json
{
  "query": "What is LightRAG?",
  "mode": "mix",
  "include_references": true
}
```

## Notes

- `.env` search order: `LIGHTRAG_ENV_PATH` → current working dir `.env` → repo root `.env` → `mcp/.env`.
- Default storage is `./rag_storage` relative to `mcp/`. Set `WORKING_DIR` to reuse an existing store.
