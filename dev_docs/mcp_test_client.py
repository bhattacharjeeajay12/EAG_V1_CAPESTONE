# mcp_client.py
"""
MCP Client for connecting to independent MCP server via WebSocket
"""

import json
import asyncio
import websockets
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import threading
import queue
import time


@dataclass
class MCPTool:
    """Represents an available MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPClient:
    """
    Client for communicating with MCP server via WebSocket.
    """

    def __init__(self, server_url: str = "ws://localhost:8000/ws"):
        """
        Initialize MCP client.

        Args:
            server_url (str): WebSocket URL of the MCP server
        """
        self.server_url = server_url
        self.websocket = None
        self.connected = False
        self.request_id = 0
        self.available_tools = {}

        # For handling async operations in sync context
        self.loop = None
        self.loop_thread = None
        self._response_futures = {}

    def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            bool: True if connection successful
        """
        try:
            # Start event loop in separate thread
            self._start_event_loop()

            # Wait a moment for loop to start
            time.sleep(0.1)

            # Connect to server
            future = asyncio.run_coroutine_threadsafe(self._connect_async(), self.loop)
            success = future.result(timeout=10)

            if success:
                # Initialize connection
                init_result = self.send_request("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "ecommerce-client", "version": "1.0.0"}
                })

                if init_result and not init_result.get("error"):
                    # Discover tools
                    self._discover_tools()
                    self.connected = True
                    print(f"[INFO] Connected to MCP server. Tools: {list(self.available_tools.keys())}")
                    return True

            return False

        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
            return False

    def _start_event_loop(self):
        """Start event loop in separate thread."""

        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()

    async def _connect_async(self) -> bool:
        """Async connection to WebSocket server."""
        try:
            self.websocket = await websockets.connect(self.server_url)
            print(f"[INFO] WebSocket connected to {self.server_url}")
            return True
        except Exception as e:
            print(f"[ERROR] WebSocket connection failed: {e}")
            return False

    def send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send request to MCP server and wait for response.

        Args:
            method (str): RPC method name
            params (Dict): Method parameters

        Returns:
            Dict: Response from server or None if failed
        """
        if not self.connected and not self.websocket:
            print("[ERROR] Not connected to MCP server")
            return None

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": str(self.request_id),
            "method": method,
            "params": params
        }

        try:
            # Send request and get response
            future = asyncio.run_coroutine_threadsafe(
                self._send_request_async(request),
                self.loop
            )
            response = future.result(timeout=10)
            return response

        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            return None

    async def _send_request_async(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send request asynchronously."""
        try:
            # Send request
            await self.websocket.send(json.dumps(request))

            # Wait for response
            response_text = await self.websocket.recv()
            response = json.loads(response_text)

            return response

        except Exception as e:
            print(f"[ERROR] Async request failed: {e}")
            return None

    def _discover_tools(self):
        """Discover available tools from the MCP server."""
        response = self.send_request("tools/list", {})

        if response and "result" in response:
            tools_data = response["result"].get("tools", [])

            for tool_info in tools_data:
                tool_name = tool_info.get("name")
                if tool_name:
                    self.available_tools[tool_name] = MCPTool(
                        name=tool_name,
                        description=tool_info.get("description", ""),
                        input_schema=tool_info.get("input_schema", {})
                    )

            print(f"[INFO] Discovered {len(self.available_tools)} tools")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call an MCP tool.

        Args:
            tool_name (str): Name of the tool to call
            arguments (Dict): Tool arguments

        Returns:
            Dict: Tool response or None if failed
        """
        if not self.connected:
            print("[ERROR] Not connected to MCP server")
            return None

        if tool_name not in self.available_tools:
            print(f"[ERROR] Tool '{tool_name}' not available. Available: {list(self.available_tools.keys())}")
            return None

        response = self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            print(f"[ERROR] Tool call failed: {response['error']}")
            return None
        else:
            print(f"[ERROR] No response for tool: {tool_name}")
            return None

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.available_tools.keys())

    def get_tool_info(self, tool_name: str) -> Optional[MCPTool]:
        """Get information about a specific tool."""
        return self.available_tools.get(tool_name)

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.connected and self.websocket is not None

    def disconnect(self):
        """Disconnect from MCP server."""
        self.connected = False

        if self.websocket:
            future = asyncio.run_coroutine_threadsafe(
                self.websocket.close(),
                self.loop
            )
            try:
                future.result(timeout=5)
            except:
                pass

        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

        print("[INFO] MCP Client disconnected")


def test_mcp_client():
    """Test the MCP client."""
    print("🧪 Testing MCP Client")
    print("=" * 50)

    client = MCPClient()

    try:
        # Connect to server
        if client.connect():
            print("✅ Connected to MCP server")

            # List tools
            tools = client.get_available_tools()
            print(f"🛠️  Available tools: {tools}")

            # Test tools
            print("\n🔧 Testing tools:")

            # Test health
            health = client.call_tool("health", {})
            print(f"   Health: {health}")

            # Test echo
            echo = client.call_tool("echo", {
                "data": {"message": "Hello from client!", "timestamp": time.time()}
            })
            print(f"   Echo: {echo}")

            # Test sum
            sum_result = client.call_tool("sum_numbers", {"a": 25.5, "b": 14.7})
            print(f"   Sum: {sum_result}")

        else:
            print("❌ Failed to connect to server")
            print("💡 Make sure to start the server first: python mcp_server.py")

    finally:
        client.disconnect()


if __name__ == "__main__":
    test_mcp_client()