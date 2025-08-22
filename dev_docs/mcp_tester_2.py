import asyncio
from dataclasses import dataclass
from mcp_tester_1 import FastMCPClient  # Import the class from your existing file


# Example agent class that can use the MCP client
@dataclass
class Agent:
    name: str

    async def use_tool(self, client, tool_name, params):
        print(f"Agent {self.name} is using tool: {tool_name}")
        try:
            result = await client.call_tool(tool_name, params)
            print(f"Agent {self.name} got result: {result}")
            return result
        except Exception as e:
            print(f"Agent {self.name} encountered an error: {e}")
            return None


async def main():
    # Connect to MCP server
    client = FastMCPClient("MCP Client")
    await client.connect()

    # Create multiple agents
    agent1 = Agent("Calculator")
    agent2 = Agent("TextProcessor")

    # Pass the same client to different agents
    await agent1.use_tool(client, "sum_numbers", {"a": 10, "b": 20})
    await agent2.use_tool(client, "text_to_uppercase", {"text": "hello world"})

    # Agents can use the client concurrently
    tasks = [
        agent1.use_tool(client, "multiply_numbers", {"a": 5, "b": 7}),
        agent2.use_tool(client, "text_to_uppercase", {"text": "concurrent call"})
    ]
    await asyncio.gather(*tasks)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())