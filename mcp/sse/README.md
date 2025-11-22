# SSE MCP Servers

This package provides reusable infrastructure for running MCP servers over Server-Sent Events (SSE). It contains:

- `base.py` – a reusable `BaseSSEMCPServer` which handles tool registration, `/tools` discovery endpoints and an SSE streaming endpoint.
- `ecommerce_server.py` – sample server exposing product search and order status tools.
- `knowledge_server.py` – sample server exposing a tiny knowledge lookup and summary tool.

## Running a server

Each server exposes a small `create_app()` helper and can be launched directly using `uvicorn`:

```bash
uvicorn mcp.sse.ecommerce_server:create_app --host 0.0.0.0 --port 8101
uvicorn mcp.sse.knowledge_server:create_app --host 0.0.0.0 --port 8102
```

Test with curl
```bash
curl -s http://127.0.0.1:8101/health
curl -s http://127.0.0.1:8101/tools
  curl -N -X POST http://127.0.0.1:8101/stream/tools/search_products \
    -H "Content-Type: application/json" \
    -d '{"category":"electronics","subcategory":"laptop","max_price":1300,"keywords":["ssd"]}'
```

Alternatively you can execute the module to use the built-in `server.run()` helper:

```bash
python -m mcp.sse.ecommerce_server
```

The servers expose:

- `GET /health` – basic health information and uptime.
- `GET /tools` – MCP-compatible tool discovery payload.
- `POST /tools/{tool_name}` – non-streaming tool invocation returning JSON.
- `POST /stream/tools/{tool_name}` – SSE endpoint returning incremental results (`event: start`, `event: data`, `event: end`).

> **Note:** These endpoints implement a lightweight REST + SSE pattern tailored for our agents. They do **not** implement the official MCP `.well-known/` SSE transport. Tools such as MCP Inspector will probe the well-known endpoints and log 404s. Use `curl`, your MCP client, or the `/stream/tools/...` routes directly to validate behaviour.

### How it works under the hood

`BaseSSEMCPServer` wraps FastAPI and provides:

1. **Tool registry** – call `@server.register_tool(...)` to register a handler. You pass:
   - Tool name + description.
   - Pydantic input model.
   - The handler function (sync/async, generator/async-generator allowed).

2. **Schema exposure** – `/tools` serialises the input model’s `model_json_schema()`, so clients know required fields.

3. **Non-streaming invocation** – `POST /tools/{name}`:
   - Payload is validated via the input model.
   - Handler must return a `dict` or Pydantic model.
   - If the handler is a generator/async-generator, a `TypeError` is raised (use the streaming route instead).

4. **Streaming invocation** – `POST /stream/tools/{name}`:
   - Handler may return/`yield` dictionaries (or Pydantic models) and they are streamed as Server-Sent Events:
     ```
     event: start
     data: {"tool":"search_products"}
     event: data
     data: {"message":"Searching category 'electronics'"}
     ...
     event: end
     data: {"tool":"search_products"}
     ```
   - Clients should use `curl -N` or any EventSource consumer to read the stream.

5. **Convenience runner** – `server.run()` wraps `uvicorn.run(create_app(), ...)`.

This architecture keeps the transport simple (REST + SSE per tool) while still giving the agent structured schemas.

## Creating a new SSE server

1. Create a new module and instantiate a `BaseSSEMCPServer`.
2. Define Pydantic models for tool inputs.
3. Register tools using the decorator returned by `server.register_tool(...)`.
4. Tool handlers may return:
   - A dictionary or Pydantic model (single response).
   - An iterator / generator / async generator yielding dictionaries for streamed responses.
5. Export a `create_app()` helper and optionally a `__main__` block that calls `server.run()` for convenience.

Example skeleton:

```python
from pydantic import BaseModel
from mcp.sse import BaseSSEMCPServer

class MyInput(BaseModel):
    query: str

server = BaseSSEMCPServer("Demo Server", "Example tools")

@server.register_tool("demo_tool", "Streams demo data", MyInput)
async def demo_tool(input_data: MyInput):
    yield {"message": f"Processing {input_data.query}"}
    yield {"result": input_data.query.upper()}


def create_app():
    return server.create_app()
```

Remember to describe tool schemas accurately – clients rely on the `inputSchema` returned by `/tools` to validate requests.
