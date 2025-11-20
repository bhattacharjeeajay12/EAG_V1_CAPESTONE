from __future__ import annotations

import asyncio
import os
from typing import Dict, List

from pydantic import BaseModel, Field

from .base import BaseSSEMCPServer

__all__ = ["create_app", "server"]


class DocumentQueryInput(BaseModel):
    query: str = Field(description="Query to search in knowledge base")
    top_k: int = Field(default=3, ge=1, le=10, description="How many passages to return")


class SummariseInput(BaseModel):
    title: str = Field(description="Topic title")
    bullets: List[str] = Field(default_factory=list, description="Bullet points to include")


_FAKE_KNOWLEDGE: Dict[str, List[str]] = {
    "fastapi": [
        "FastAPI is a high-performance web framework for building APIs with Python.",
        "It is built on top of Starlette for web parts and Pydantic for data validation.",
        "FastAPI supports automatic OpenAPI schema generation and async endpoints.",
        "Background tasks in FastAPI can be scheduled using BackgroundTasks utility.",
    ],
    "mcp": [
        "MCP (Model Context Protocol) standardises tool discovery and invocation for AI agents.",
        "Servers expose tools with schemas so clients can call them consistently.",
        "Transports include stdio, HTTP/REST, SSE and WebSockets depending on deployment needs.",
    ],
    "sse": [
        "Server-Sent Events (SSE) allow servers to push text/event-stream data over HTTP.",
        "Clients consume SSE with the EventSource API or dedicated libraries.",
    ],
}


server = BaseSSEMCPServer(
    title="Knowledge SSE MCP Server",
    description="Streams knowledge-base lookups and summaries over SSE",
)


@server.register_tool(
    name="knowledge_search",
    description="Search simple knowledge base and stream passages.",
    input_model=DocumentQueryInput,
)
async def knowledge_search(input_data: DocumentQueryInput):
    query_key = input_data.query.lower().strip()
    await asyncio.sleep(0.1)
    yield {"message": f"Searching knowledge base for '{input_data.query}'"}

    passages = _FAKE_KNOWLEDGE.get(query_key, [])[: input_data.top_k]
    if not passages:
        yield {"results": [], "message": "No passages found"}
        return

    for idx, passage in enumerate(passages, start=1):
        await asyncio.sleep(0.1)
        yield {"passage_index": idx, "passage": passage}

    yield {"results_returned": len(passages)}


@server.register_tool(
    name="summarise_points",
    description="Stream a lightweight summary composed from bullet points.",
    input_model=SummariseInput,
)
async def summarise_points(input_data: SummariseInput):
    if not input_data.bullets:
        yield {"summary": f"Summary for {input_data.title}: No bullet points supplied."}
        return

    yield {"message": f"Composing summary for {input_data.title}"}
    for idx, bullet in enumerate(input_data.bullets, start=1):
        await asyncio.sleep(0.05)
        yield {"step": idx, "detail": bullet}

    summary = f"{input_data.title}: " + "; ".join(input_data.bullets)
    yield {"summary": summary}


def create_app():
    return server.create_app()


if __name__ == "__main__":  # pragma: no cover
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8102"))
    server.run(host=host, port=port)
