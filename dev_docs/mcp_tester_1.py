import asyncio
import json

class FastMCPClient:
    def __init__(self, client_name):
        self.client_name = client_name
        self.connected = False
        print(f"Initialized {client_name}")
        
        # Mock data for demonstration
        self.available_tools = [
            {"name": "sum_numbers", "description": "Adds two numbers together"},
            {"name": "multiply_numbers", "description": "Multiplies two numbers"},
            {"name": "text_to_uppercase", "description": "Converts text to uppercase"}
        ]
    
    async def connect(self):
        print(f"Connecting {self.client_name}...")
        # Simulate connection delay
        await asyncio.sleep(0.5)
        self.connected = True
        print(f"Connected {self.client_name}")
        return True
    
    async def list_tools(self):
        if not self.connected:
            raise RuntimeError("Client not connected")
        # Return mock tool objects
        class Tool:
            def __init__(self, name, description):
                self.name = name
                self.description = description
        
        return [Tool(**t) for t in self.available_tools]
    
    async def call_tool(self, tool_name, params):
        if not self.connected:
            raise RuntimeError("Client not connected")
        
        # Implement basic tool functionality
        if tool_name == "sum_numbers":
            return params.get("a", 0) + params.get("b", 0)
        elif tool_name == "multiply_numbers":
            return params.get("a", 0) * params.get("b", 0)
        elif tool_name == "text_to_uppercase":
            return params.get("text", "").upper()
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def disconnect(self):
        if self.connected:
            print(f"Disconnecting {self.client_name}...")
            await asyncio.sleep(0.1)
            self.connected = False
            print(f"Disconnected {self.client_name}")
        return True

import asyncio

async def main():
    # Connect to MCP server (default stdio transport)
    client = FastMCPClient("MCP Client")
    await client.connect()

    # List all available tools
    tools = await client.list_tools()
    print("Available Tools:")
    for t in tools:
        print(f"- {t.name}: {t.description}")

    # Call the sum_numbers tool
    response = await client.call_tool("sum_numbers", {"a": 5, "b": 7})
    print("\nResult of sum_numbers(5,7):", response)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
