from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from typing import Dict, Any
import sys
from pydantic import BaseModel, Field

# ---------------------------
# Input/Output Models
# ---------------------------

class EchoInput(BaseModel):
    """Input for the echo tool."""
    data: Dict[str, Any] = Field(description="Data to echo back")

class EchoOutput(BaseModel):
    """Output from the echo tool."""
    echo: Dict[str, Any] = Field(description="Echoed data")

class HealthOutput(BaseModel):
    """Output from the health check tool."""
    status: str = Field(description="Health status")

class SumInput(BaseModel):
    """Input for the sum_numbers tool."""
    a: float = Field(description="First number")
    b: float = Field(description="Second number")

class SumOutput(BaseModel):
    """Output from the sum_numbers tool."""
    result: float = Field(description="The sum of the two numbers")

# ---------------------------
# MCP Server Setup
# ---------------------------

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

@mcp.tool()
def sum_numbers(input: SumInput) -> SumOutput:
    """Return the sum of two numbers."""
    print(f"CALLED: sum_numbers({input.a}, {input.b}) -> SumOutput")
    return SumOutput(result=input.a + input.b)

# ---------------------------
# Main entry point
# ---------------------------

if __name__ == "__main__":
    print("MCP server starting...")
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run()
    else:
        mcp.run(transport="stdio")
        print("\nShutting down...")
