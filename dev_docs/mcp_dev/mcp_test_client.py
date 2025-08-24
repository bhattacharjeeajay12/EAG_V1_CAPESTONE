# mcp_test_client.py  
"""
Simple HTTP-based MCP Client
Connects to HTTP MCP server without Windows subprocess issues
"""

import json
import subprocess
import time
import os
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    from flask.cli import load_dotenv
    load_dotenv()
except ImportError:
    # If flask not available, just continue
    pass

@dataclass
class MCPTool:
    """Represents an available MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPClient:
    """
    Simple HTTP-based MCP Client.
    Connects to HTTP server and avoids Windows subprocess issues.
    """

    def __init__(self,
                 server_url: Optional[str] = None,
                 server_command: Optional[List[str]] = None):
        """
        Initialize MCP client.

        Args:
            server_url (str, optional): URL for MCP server (e.g. "http://localhost:8000")
            server_command (List[str], optional): Command to start local MCP server
        """
        self.server_url = server_url or "http://localhost:8000"
        self.server_command = server_command or ["python", "dev_docs/mcp_dev/mcp_test_server.py"]
        self.process = None
        self.connected = False
        self.available_tools = {}
        self.start_local_server = server_url is None

    def connect(self) -> bool:
        """
        Connect to the MCP server via HTTP.

        Returns:
            bool: True if connection successful
        """
        # Start local server if needed
        if self.start_local_server:
            if not self._start_local_server():
                return False

        # Test connection to HTTP server
        return self._test_connection()

    def _start_local_server(self) -> bool:
        """Start local MCP server if needed."""
        try:
            print(f"[INFO] Starting local MCP server: {' '.join(self.server_command)}")

            # Start the server process
            self.process = subprocess.Popen(
                self.server_command,
                stdout=subprocess.DEVNULL,  # Don't capture output to avoid pipe issues
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )

            # Wait for server to start
            time.sleep(3.0)

            # Check if process is still running
            if self.process.poll() is not None:
                print(f"[ERROR] Server process exited with code: {self.process.returncode}")
                return False

            print("[INFO] Local server process started")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start local server: {e}")
            return False

    def _test_connection(self) -> bool:
        """Test connection to HTTP server."""
        try:
            print(f"[INFO] Testing connection to {self.server_url}")

            # Test health endpoint
            response = requests.get(f"{self.server_url}/health", timeout=10)
            if response.status_code == 200:
                print("[INFO] Health check passed")

                # Discover tools
                self._discover_tools()

                self.connected = True
                print(f"[INFO] Connected successfully. Available tools: {list(self.available_tools.keys())}")
                return True
            else:
                print(f"[ERROR] Health check failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] Connection test failed: {e}")
            return False

    def _discover_tools(self):
        """Discover available tools from the HTTP server."""
        try:
            response = requests.get(f"{self.server_url}/tools", timeout=5)
            if response.status_code == 200:
                data = response.json()
                tools_data = data.get("tools", [])

                for tool_info in tools_data:
                    tool_name = tool_info.get("name")
                    if tool_name:
                        self.available_tools[tool_name] = MCPTool(
                            name=tool_name,
                            description=tool_info.get("description", ""),
                            input_schema=tool_info.get("inputSchema", {})
                        )

                if tools_data:
                    print(f"[INFO] Discovered {len(tools_data)} tools")
                else:
                    print("[WARN] No tools returned from server")
            else:
                print(f"[WARN] Failed to get tools list: {response.status_code}")
        except Exception as e:
            print(f"[WARN] Failed to discover tools: {e}")

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Call an MCP tool via HTTP.

        Args:
            tool_name (str): Name of the tool to call
            arguments (Dict): Tool arguments

        Returns:
            Dict: Tool response or None if failed
        """
        if not self.connected:
            print("[ERROR] MCP client not connected")
            return None

        try:
            response = requests.post(
                f"{self.server_url}/tools/{tool_name}",
                json=arguments,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] Tool call failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"[ERROR] Failed to call tool {tool_name}: {e}")
            return None

    def _cleanup_process(self):
        """Clean up local process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            finally:
                self.process = None

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.available_tools.keys())

    def get_tool_info(self, tool_name: str) -> Optional[MCPTool]:
        """Get information about a specific tool."""
        return self.available_tools.get(tool_name)

    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self.connected

    def disconnect(self):
        """Disconnect from MCP server."""
        self.connected = False
        self._cleanup_process()
        print("[INFO] MCP Client disconnected")


def test_mcp_client():
    """Test the MCP client with HTTP MCP server."""
    print("🧪 Testing MCP Client with HTTP MCP Server")
    print("=" * 50)

    # Check for environment variables to configure client
    server_url = os.environ.get("MCP_SERVER_URL")
    print("server_url : ", server_url)

    # Create client
    if server_url:
        print(f"[INFO] Using remote server at {server_url}")
        client = MCPClient(server_url=server_url)
    else:
        print("[INFO] Using local server (will start automatically)")
        server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_test_server.py")
        client = MCPClient(server_command=["python", server_script])

    try:
        # Connect
        if client.connect():
            print("✅ Connected to FastMCP server")

            # List available tools
            tools = client.get_available_tools()
            print(f"🛠️  Available tools: {tools}")

            # Test tools even if they're not in the available list
            # This helps diagnose communication issues
            print("\n🔧 Testing basic tools:")

            # Test health tool
            health_result = client.call_tool("health", {})
            print(f"   Health: {health_result}")

            # Test echo tool
            echo_result = client.call_tool("echo", {
                "data": {
                    "test_message": "Hello from MCP client!",
                    "timestamp": time.time(),
                    "client_info": "ecommerce-planner"
                }
            })
            print(f"   Echo: {echo_result}")

            # Test sum_numbers tool
            sum_result = client.call_tool("sum_numbers", {
                "a": 25.5,
                "b": 14.7
            })
            print(f"   Sum: {sum_result}")

            # Test ecommerce tools if available
            print("\n🛒 Testing ecommerce tools:")

            # Test product search
            search_result = client.call_tool("search_products", {
                "category": "electronics",
                "subcategory": "laptop",
                "budget_max": 1000.0,
                "specifications": ["intel", "8gb"]
            })
            print(f"   Product Search: {search_result}")

            # Test order status
            order_result = client.call_tool("check_order_status", {
                "order_id": "12345"
            })
            print(f"   Order Status: {order_result}")

            print("\n✅ Tests completed")

        else:
            print("❌ Failed to connect to FastMCP server")

    finally:
        client.disconnect()


if __name__ == "__main__":
    test_mcp_client()