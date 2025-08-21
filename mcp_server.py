from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from typing import Dict, Any, Optional, List
import sys
from pydantic import BaseModel, Field

# Define input/output models
class EchoInput(BaseModel):
    """Input for the echo tool."""
    data: Dict[str, Any] = Field(description="Data to echo back")

class EchoOutput(BaseModel):
    """Output from the echo tool."""
    echo: Dict[str, Any] = Field(description="Echoed data")

class HealthOutput(BaseModel):
    """Output from the health check tool."""
    status: str = Field(description="Health status")

# Create FastMCP instance
mcp = FastMCP("MCP Server")

@mcp.tool()
def echo(input: EchoInput) -> EchoOutput:
    """Echo back the input data."""
    print("CALLED: echo(EchoInput) -> EchoOutput")
    return EchoOutput(echo=input.data)

@mcp.tool()
def health() -> HealthOutput:
    """Return the health status of the server."""
    print("CALLED: health() -> HealthOutput")
    return HealthOutput(status="ok")

# Main entry point
if __name__ == "__main__":
    print("MCP server starting...")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        # Run without transport for dev server
        # Default port is 8765, matching the original implementation
        mcp.run()
    else:
        # Run with stdio for direct execution
        mcp.run(transport="stdio")
        print("\nShutting down...")
