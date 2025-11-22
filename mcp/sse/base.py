from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass
from typing import (Any, AsyncGenerator, Awaitable, Callable, Dict, Generator,
                    Iterable, Optional, Type, Union)

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

__all__ = ["BaseSSEMCPServer", "ToolDefinition", "ToolHandler"]

ToolHandler = Callable[[BaseModel], Union[
    Dict[str, Any],
    BaseModel,
    Iterable[Dict[str, Any]],
    Generator[Dict[str, Any], None, None],
    AsyncGenerator[Dict[str, Any], None],
    Awaitable[Union[Dict[str, Any], BaseModel]]
]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_model: Type[BaseModel]
    handler: ToolHandler

    @property
    def json_schema(self) -> Dict[str, Any]:
        return self.input_model.model_json_schema()


class BaseSSEMCPServer:
    """Reusable SSE MCP server that can be extended for domain-specific tools."""

    def __init__(self, title: str, description: str) -> None:
        self._title = title
        self._description = description
        self._tools: Dict[str, ToolDefinition] = {}
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register_tool(self, name: str, description: str, input_model: Type[BaseModel]):
        def decorator(func: ToolHandler) -> ToolHandler:
            if name in self._tools:
                raise ValueError(f"Tool '{name}' already registered")
            self._tools[name] = ToolDefinition(name, description, input_model, func)
            return func

        return decorator

    # ------------------------------------------------------------------
    # FastAPI application factory
    # ------------------------------------------------------------------
    def create_app(self) -> FastAPI:
        app = FastAPI(title=self._title, description=self._description)

        @app.get("/health")
        async def health() -> Dict[str, Any]:
            return {
                "status": "healthy",
                "uptime_seconds": round(time.time() - self._start_time, 2),
                "tool_count": len(self._tools),
            }

        @app.get("/tools")
        async def list_tools() -> Dict[str, Any]:
            tools_payload = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.json_schema,
                }
                for tool in self._tools.values()
            ]
            return {"tools": tools_payload}

        @app.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, payload: Dict[str, Any]):
            tool = self._tools.get(tool_name)
            if not tool:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

            parsed = tool.input_model(**payload)
            result = await self._resolve_result(tool.handler, parsed)
            return JSONResponse(content=result)

        @app.post("/stream/tools/{tool_name}")
        async def stream_tool(tool_name: str, payload: Dict[str, Any]):
            tool = self._tools.get(tool_name)
            if not tool:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

            parsed = tool.input_model(**payload)

            async def event_publisher():
                yield self._format_event("start", {"tool": tool_name})
                try:
                    async for chunk in self._iterate(tool.handler, parsed):
                        yield self._format_event("data", chunk)
                    yield self._format_event("end", {"tool": tool_name})
                except Exception as exc:  # pragma: no cover - runtime safety
                    error_payload = {"error": str(exc), "tool": tool_name}
                    yield self._format_event("error", error_payload)

            return EventSourceResponse(event_publisher(), media_type="text/event-stream")

        return app

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _resolve_result(self, handler: ToolHandler, parsed: BaseModel) -> Dict[str, Any]:
        result = handler(parsed)
        if inspect.isawaitable(result):
            result = await result  # type: ignore[assignment]
        if isinstance(result, BaseModel):
            return result.model_dump()
        if isinstance(result, dict):
            return result
        raise TypeError("Tool handler must return dict or BaseModel when not streaming")

    async def _iterate(self, handler: ToolHandler, parsed: BaseModel) -> AsyncGenerator[Dict[str, Any], None]:
        result = handler(parsed)

        if inspect.isasyncgen(result):
            async for chunk in result:  # type: ignore[async-for]
                yield self._normalise_chunk(chunk)
            return

        if inspect.isawaitable(result):
            awaited = await result  # type: ignore[assignment]
            if inspect.isasyncgen(awaited):
                async for chunk in awaited:  # type: ignore[async-for]
                    yield self._normalise_chunk(chunk)
                return
            if inspect.isgenerator(awaited) or isinstance(awaited, Iterable):
                for chunk in awaited:  # type: ignore[assignment]
                    yield self._normalise_chunk(chunk)
                return
            yield self._normalise_chunk(awaited)  # type: ignore[arg-type]
            return

        if inspect.isgenerator(result) or isinstance(result, Iterable):
            for chunk in result:  # type: ignore[assignment]
                yield self._normalise_chunk(chunk)
            return

        if isinstance(result, (dict, BaseModel)):
            yield self._normalise_chunk(result)
            return

        raise TypeError("Unsupported tool handler return type for streaming")

    def _normalise_chunk(self, chunk: Any) -> Dict[str, Any]:
        if isinstance(chunk, BaseModel):
            return chunk.model_dump()
        if isinstance(chunk, dict):
            return chunk
        raise TypeError("Streamed chunks must be dict or BaseModel instances")

    @staticmethod
    def _format_event(event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"event": event, "data": json.dumps(payload)}

    # ------------------------------------------------------------------
    # Convenience runner
    # ------------------------------------------------------------------
    def run(self, host: str = "0.0.0.0", port: int = 8000):  # pragma: no cover - manual start
        import uvicorn

        app = self.create_app()
        uvicorn.run(app, host=host, port=port)
