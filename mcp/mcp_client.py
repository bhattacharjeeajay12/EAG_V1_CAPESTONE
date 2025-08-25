# mcp/mcp_http_client.py
"""
HTTP-based MCP Client for connecting to FastAPI MCP server.
Designed for AWS/EC2 deployment with network communication.
"""

import json
import requests
import time
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

# loading environment variables
load_dotenv()


@dataclass
class MCPTool:
    """Represents an available MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPHttpClient:
    """
    HTTP-based client for communicating with MCP server via REST API.
    Perfect for AWS/EC2 deployment scenarios.
    """

    def __init__(self, server_url: str = None, timeout: int = 30):
        """
        Initialize MCP HTTP client.

        Args:
            server_url (str): URL of the MCP server (e.g., "http://localhost:8000")
            timeout (int): Request timeout in seconds
        """
        self.server_url = server_url or os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        self.timeout = timeout
        self.connected = False
        self.available_tools = {}

        # Remove trailing slash
        self.server_url = self.server_url.rstrip('/')

    def connect(self) -> bool:
        """
        Connect to the MCP server via HTTP.

        Returns:
            bool: True if connection successful
        """
        try:
            print(f"[INFO] Connecting to MCP server at {self.server_url}")

            # Test connection with health endpoint
            response = requests.get(
                f"{self.server_url}/health",
                timeout=self.timeout
            )

            if response.status_code == 200:
                print("[INFO] Health check passed")

                # Discover available tools
                self._discover_tools()

                self.connected = True
                print(f"[INFO] MCP Client connected. Available tools: {list(self.available_tools.keys())}")
                return True
            else:
                print(f"[ERROR] Health check failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Cannot connect to MCP server at {self.server_url}")
            return False
        except requests.exceptions.Timeout:
            print(f"[ERROR] Connection timeout to MCP server")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to connect to MCP server: {e}")
            return False

    def _discover_tools(self):
        """Discover available tools from the HTTP server."""
        try:
            response = requests.get(
                f"{self.server_url}/tools",
                timeout=self.timeout
            )

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

                print(f"[INFO] Discovered {len(tools_data)} tools")
            else:
                print(f"[WARN] Failed to get tools list: HTTP {response.status_code}")

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

        if tool_name not in self.available_tools:
            print(f"[ERROR] Tool '{tool_name}' not available. Available: {list(self.available_tools.keys())}")
            return None

        try:
            response = requests.post(
                f"{self.server_url}/tools/{tool_name}",
                json=arguments,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                    error_msg += f": {error_detail}"
                except:
                    error_msg += f": {response.text}"

                print(f"[ERROR] Tool call failed: {error_msg}")
                return None

        except requests.exceptions.Timeout:
            print(f"[ERROR] Tool call timeout for {tool_name}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Connection lost to MCP server")
            self.connected = False
            return None
        except Exception as e:
            print(f"[ERROR] Failed to call tool {tool_name}: {e}")
            return None

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
        """Disconnect from MCP server (HTTP client doesn't maintain persistent connections)."""
        self.connected = False
        print("[INFO] MCP HTTP Client disconnected")

    def ping(self) -> bool:
        """Ping the server to check if it's still alive."""
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False


def test_mcp_http_client():
    """Test the HTTP MCP client with your server."""
    print("🧪 Testing HTTP MCP Client")
    print("=" * 50)

    # Check environment variable for server URL
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
    print(f"Server URL: {server_url}")

    # Create client
    client = MCPHttpClient(server_url=server_url)

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
                "data": {"test": "Hello from HTTP MCP client!", "number": 42}
            })
            print(f"   Echo: {echo_result}")

            # Test sum_numbers tool
            sum_result = client.call_tool("sum_numbers", {
                "a": 15.5,
                "b": 24.7
            })
            print(f"   Sum: {sum_result}")

            # Test product search
            search_result = client.call_tool("search_products", {
                "category": "electronics",
                "subcategory": "laptop",
                "budget_max": 1000.0,
                "specifications": ["intel", "8gb"]
            })
            print(f"   Product Search: {search_result}")

            print("\n✅ All tool tests completed!")

        else:
            print("❌ Failed to connect to MCP server")
            print("💡 Make sure the server is running:")
            print("   python mcp/mcp_server.py")

    finally:
        client.disconnect()


if __name__ == "__main__":
    test_mcp_http_client()

"""
Deployement instruction

1. UPDATE ENVIRONMENT VARIABLES
# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
MCP_HOST=0.0.0.0
MCP_PORT=8000

# For AWS deployment, update to:
# MCP_SERVER_URL=http://your-ec2-server-ip:8000
# or
# MCP_SERVER_URL=https://your-domain.com

2.  For AWS/EC2 Deployment
When deploying to AWS:
1. **Server side (EC2 instance hosting the MCP server):**
``` bash
# Update server to bind to all interfaces
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
python mcp/mcp_server.py
```
1. **Client side (EC2 instance or local machine):**
``` bash
# Point to your server's public IP or domain
export MCP_SERVER_URL=http://your-ec2-public-ip:8000
python mcp/mcp_http_client.py
```
1. **Security Group Configuration:**
    - Open port 8000 (or your chosen port) in your EC2 security group
    - Allow HTTP traffic from your client's IP or security group

This HTTP-based approach will work perfectly for your AWS deployment and eliminates the stdio communication issues you were experiencing.

"""