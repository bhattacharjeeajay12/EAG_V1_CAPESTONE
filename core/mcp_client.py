# mcp_client.py
"""
MCP Client for connecting to FastMCP server and calling tools.
"""

import json
import subprocess
import threading
import queue
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class MCPTool:
    """Represents an available MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPClient:
    """
    Client for communicating with MCP server via stdio.
    """

    def __init__(self, server_command: List[str]):
        """
        Initialize MCP client.

        Args:
            server_command (List[str]): Command to start the MCP server
        """
        self.server_command = server_command
        self.process = None
        self.connected = False
        self.request_id = 0
        self.available_tools = {}

        # Communication queues
        self._response_queue = queue.Queue()
        self._reader_thread = None
        self._writer_thread = None

    def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            bool: True if connection successful
        """
        try:
            # Start the MCP server process
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )

            # Start reader thread
            self._reader_thread = threading.Thread(
                target=self._read_responses,
                daemon=True
            )
            self._reader_thread.start()

            # Wait a moment for server to start
            time.sleep(0.5)

            # Initialize connection
            init_response = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "ecommerce-planner",
                    "version": "1.0.0"
                }
            })

            if init_response and init_response.get("result"):
                self.connected = True

                # Get available tools
                self._discover_tools()

                print(f"[INFO] MCP Client connected. Available tools: {list(self.available_tools.keys())}")
                return True
            else:
                print("[ERROR] MCP initialization failed")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to connect to MCP server: {e}")
            return False

    def _read_responses(self):
        """Read responses from MCP server in separate thread."""
        if not self.process:
            return

        try:
            for line in iter(self.process.stdout.readline, ''):
                if line.strip():
                    try:
                        response = json.loads(line.strip())
                        self._response_queue.put(response)
                    except json.JSONDecodeError:
                        print(f"[WARN] Invalid JSON from MCP server: {line}")
        except Exception as e:
            print(f"[ERROR] Error reading MCP responses: {e}")

    def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a request to MCP server and wait for response.

        Args:
            method (str): RPC method name
            params (Dict): Method parameters

        Returns:
            Dict: Response from server or None if failed
        """
        if not self.process:
            return None

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }

        try:
            # Send request
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()

            # Wait for response (with timeout)
            timeout = 10.0  # 10 second timeout
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    response = self._response_queue.get(timeout=0.1)
                    if response.get("id") == self.request_id:
                        return response
                    else:
                        # Put it back if it's not our response
                        self._response_queue.put(response)
                except queue.Empty:
                    continue

            print(f"[WARN] Timeout waiting for MCP response to {method}")
            return None

        except Exception as e:
            print(f"[ERROR] Failed to send MCP request: {e}")
            return None

    def _discover_tools(self):
        """Discover available tools from the MCP server."""
        response = self._send_request("tools/list", {})

        if response and "result" in response:
            tools_data = response["result"].get("tools", [])

            for tool_info in tools_data:
                tool_name = tool_info.get("name")
                if tool_name:
                    self.available_tools[tool_name] = MCPTool(
                        name=tool_name,
                        description=tool_info.get("description", ""),
                        input_schema=tool_info.get("inputSchema", {})
                    )

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
            print("[ERROR] MCP client not connected")
            return None

        if tool_name not in self.available_tools:
            print(f"[ERROR] Tool '{tool_name}' not available. Available: {list(self.available_tools.keys())}")
            return None

        response = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            print(f"[ERROR] MCP tool call failed: {response['error']}")
            return None
        else:
            print(f"[ERROR] No response from MCP tool: {tool_name}")
            return None

    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.

        Returns:
            List[str]: Available tool names
        """
        return list(self.available_tools.keys())

    def get_tool_info(self, tool_name: str) -> Optional[MCPTool]:
        """
        Get information about a specific tool.

        Args:
            tool_name (str): Name of the tool

        Returns:
            MCPTool: Tool information or None if not found
        """
        return self.available_tools.get(tool_name)

    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self.connected and self.process and self.process.poll() is None

    def disconnect(self):
        """Disconnect from MCP server."""
        self.connected = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                print(f"[WARN] Error terminating MCP process: {e}")

            self.process = None

        print("[INFO] MCP Client disconnected")


def test_mcp_client():
    """Test the MCP client with your server."""
    print("🧪 Testing MCP Client")
    print("=" * 50)

    # Create client
    client = MCPClient(["python", "mcp_server.py"])

    try:
        # Connect
        if client.connect():
            print("✅ Connected to MCP server")

            # List available tools
            tools = client.get_available_tools()
            print(f"📋 Available tools: {tools}")

            # Test each tool
            print("\n🔧 Testing tools:")

            # Test health tool
            health_result = client.call_tool("health", {})
            print(f"   Health: {health_result}")

            # Test echo tool
            echo_result = client.call_tool("echo", {
                "data": {"test": "Hello from MCP client!", "number": 42}
            })
            print(f"   Echo: {echo_result}")

            # Test sum_numbers tool
            sum_result = client.call_tool("sum_numbers", {
                "a": 15.5,
                "b": 24.7
            })
            print(f"   Sum: {sum_result}")

            print("\n✅ All tool tests completed!")

        else:
            print("❌ Failed to connect to MCP server")

    finally:
        client.disconnect()


if __name__ == "__main__":
    test_mcp_client()