# mcp_server.py
"""
Independent MCP Server running on HTTP/WebSocket
This server runs independently and can handle multiple clients.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
from pydantic import BaseModel, Field


# ---------------------------
# Data Models
# ---------------------------

class EchoRequest(BaseModel):
    data: Dict[str, Any] = Field(description="Data to echo back")


class HealthResponse(BaseModel):
    status: str = Field(description="Health status")
    timestamp: str = Field(description="Current timestamp")
    uptime: str = Field(description="Server uptime")


class SumRequest(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")


class SumResponse(BaseModel):
    result: float = Field(description="Sum result")
    calculation: str = Field(description="Calculation performed")


class MCPRequest(BaseModel):
    id: str = Field(description="Request ID")
    method: str = Field(description="Method name")
    params: Dict[str, Any] = Field(description="Method parameters")


class MCPResponse(BaseModel):
    id: str = Field(description="Response ID matching request")
    result: Dict[str, Any] = Field(description="Method result")
    error: str = None


# ---------------------------
# MCP Server Implementation
# ---------------------------

class MCPServer:
    def __init__(self):
        self.start_time = datetime.now()
        self.connected_clients = set()

        # Available tools
        self.tools = {
            "echo": {
                "name": "echo",
                "description": "Echo back the input data",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "object", "description": "Data to echo"}
                    },
                    "required": ["data"]
                }
            },
            "health": {
                "name": "health",
                "description": "Get server health status",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            "sum_numbers": {
                "name": "sum_numbers",
                "description": "Calculate sum of two numbers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"}
                    },
                    "required": ["a", "b"]
                }
            }
        }

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False}
            },
            "serverInfo": {
                "name": "ecommerce-mcp-server",
                "version": "1.0.0"
            }
        }

    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {
            "tools": list(self.tools.values())
        }

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Execute the tool
        if tool_name == "echo":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo response: {json.dumps(arguments.get('data', {}))}"
                    }
                ],
                "isError": False
            }

        elif tool_name == "health":
            uptime = datetime.now() - self.start_time
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "status": "healthy",
                            "timestamp": datetime.now().isoformat(),
                            "uptime_seconds": uptime.total_seconds(),
                            "connected_clients": len(self.connected_clients)
                        })
                    }
                ],
                "isError": False
            }

        elif tool_name == "sum_numbers":
            a = float(arguments.get("a", 0))
            b = float(arguments.get("b", 0))
            result = a + b
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "result": result,
                            "calculation": f"{a} + {b} = {result}"
                        })
                    }
                ],
                "isError": False
            }

        else:
            raise ValueError(f"Tool not implemented: {tool_name}")

    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP request."""
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = await self.handle_tools_list(params)
            elif method == "tools/call":
                result = await self.handle_tools_call(params)
            else:
                raise ValueError(f"Unknown method: {method}")

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }


# ---------------------------
# FastAPI Application
# ---------------------------

app = FastAPI(title="MCP Server", description="Model Context Protocol Server")
mcp_server = MCPServer()


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "MCP Server",
        "status": "running",
        "tools": list(mcp_server.tools.keys()),
        "clients": len(mcp_server.connected_clients),
        "uptime": (datetime.now() - mcp_server.start_time).total_seconds()
    }


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {"tools": list(mcp_server.tools.values())}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP communication."""
    await websocket.accept()
    mcp_server.connected_clients.add(websocket)

    print(f"[INFO] Client connected. Total clients: {len(mcp_server.connected_clients)}")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                request_data = json.loads(data)
                print(f"[INFO] Received request: {request_data.get('method')}")

                # Handle the request
                response = await mcp_server.handle_request(request_data)

                # Send response back to client
                await websocket.send_text(json.dumps(response))

            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                await websocket.send_text(json.dumps(error_response))

    except WebSocketDisconnect:
        mcp_server.connected_clients.discard(websocket)
        print(f"[INFO] Client disconnected. Total clients: {len(mcp_server.connected_clients)}")


# ---------------------------
# Server Startup
# ---------------------------

if __name__ == "__main__":
    print("🚀 Starting MCP Server...")
    print("📡 WebSocket endpoint: ws://localhost:8000/ws")
    print("🌐 HTTP endpoint: http://localhost:8000")
    print("🛠️  Available tools: echo, health, sum_numbers")

    uvicorn.run(
        app,
        host="localhost",
        port=8000,
        log_level="info"
    )