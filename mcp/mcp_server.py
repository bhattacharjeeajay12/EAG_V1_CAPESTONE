# mcp_test_server.py
"""
Simple HTTP-based MCP Server for ecommerce tools
Works reliably on Windows without stdio pipe issues
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import sys
import json
import time
import os
import uvicorn
from datetime import datetime
from typing import Dict, Any, List, Optional

# ---------------------------
# Input/Output Models
# ---------------------------

class EchoInput(BaseModel):
    """Input for the echo tool."""
    data: Dict[str, Any] = Field(description="Data to echo back")


class EchoOutput(BaseModel):
    """Output from the echo tool."""
    echo: Dict[str, Any] = Field(description="Echoed data with timestamp")
    server_info: str = Field(description="Server information")


class HealthOutput(BaseModel):
    """Output from the health check tool."""
    status: str = Field(description="Health status")
    timestamp: str = Field(description="Current server timestamp")
    uptime_seconds: float = Field(description="Server uptime in seconds")


class SumInput(BaseModel):
    """Input for the sum_numbers tool."""
    a: float = Field(description="First number")
    b: float = Field(description="Second number")


class SumOutput(BaseModel):
    """Output from the sum_numbers tool."""
    result: float = Field(description="The sum of the two numbers")
    calculation: str = Field(description="Human readable calculation")


class ProductSearchInput(BaseModel):
    """Input for product search tool."""
    category: str = Field(description="Product category (electronics, sports, books, etc.)")
    subcategory: Optional[str] = Field(description="Product subcategory", default=None)
    budget_max: Optional[float] = Field(description="Maximum budget", default=None)
    specifications: Optional[List[str]] = Field(description="Required specifications", default=[])


class ProductSearchOutput(BaseModel):
    """Output from product search."""
    products: List[Dict[str, Any]] = Field(description="Found products")
    total_found: int = Field(description="Total products found")
    search_query: str = Field(description="Search query used")


class OrderStatusInput(BaseModel):
    """Input for order status check."""
    order_id: str = Field(description="Order ID to check")


class OrderStatusOutput(BaseModel):
    """Output from order status check."""
    order_id: str = Field(description="Order ID")
    status: str = Field(description="Order status")
    tracking_info: Dict[str, Any] = Field(description="Tracking information")
    estimated_delivery: Optional[str] = Field(description="Estimated delivery date")


# ---------------------------
# Simple HTTP Server Setup
# ---------------------------

# Server startup time for uptime calculation
SERVER_START_TIME = datetime.now()

# Initialize FastAPI server
app = FastAPI(title="Ecommerce MCP Server", description="Simple HTTP-based MCP tools")

# Tool registry for MCP compatibility
AVAILABLE_TOOLS = []

def register_tool(name: str, description: str, input_schema: dict, handler):
    """Register a tool for MCP compatibility"""
    AVAILABLE_TOOLS.append({
        "name": name,
        "description": description,
        "inputSchema": input_schema,
        "handler": handler
    })

# ---------------------------
# Basic Tools
# ---------------------------

def echo_handler(input_data: EchoInput) -> EchoOutput:
    """Echo back the input data with server information."""
    print(f"CALLED: echo() with data keys: {list(input_data.data.keys())}")
    return EchoOutput(
        echo=input_data.data,
        server_info=f"EcommerceMCPServer at {datetime.now().isoformat()}"
    )

def health_handler() -> HealthOutput:
    """Return the health status of the ecommerce MCP server."""
    print("CALLED: health() -> HealthOutput")
    uptime = (datetime.now() - SERVER_START_TIME).total_seconds()
    return HealthOutput(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        uptime_seconds=uptime
    )

def sum_numbers_handler(input_data: SumInput) -> SumOutput:
    """Calculate the sum of two numbers."""
    print(f"CALLED: sum_numbers({input_data.a}, {input_data.b}) -> SumOutput")
    result = input_data.a + input_data.b
    return SumOutput(
        result=result,
        calculation=f"{input_data.a} + {input_data.b} = {result}"
    )

# Register basic tools
register_tool("echo", "Echo back the input data", {"type": "object", "properties": {"data": {"type": "object"}}}, echo_handler)
register_tool("health", "Get server health status", {"type": "object", "properties": {}}, health_handler)
register_tool("sum_numbers", "Calculate sum of two numbers", {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}, sum_numbers_handler)


# ---------------------------
# Ecommerce Specific Tools
# ---------------------------

def search_products_handler(input_data: ProductSearchInput) -> ProductSearchOutput:
    """Search for products based on category, budget, and specifications."""
    print(f"CALLED: search_products() category={input_data.category}, budget_max={input_data.budget_max}")

    # Mock product database
    mock_products = {
        "electronics": [
            {
                "id": "laptop_001",
                "name": "Dell Inspiron 15",
                "price": 899.99,
                "category": "electronics",
                "subcategory": "laptop",
                "specifications": ["Intel i5", "8GB RAM", "256GB SSD", "15.6 inch"],
                "rating": 4.3,
                "availability": "in_stock"
            },
            {
                "id": "laptop_002",
                "name": "MacBook Air M2",
                "price": 1299.99,
                "category": "electronics",
                "subcategory": "laptop",
                "specifications": ["Apple M2", "8GB RAM", "256GB SSD", "13.3 inch"],
                "rating": 4.7,
                "availability": "in_stock"
            },
            {
                "id": "phone_001",
                "name": "iPhone 15",
                "price": 799.99,
                "category": "electronics",
                "subcategory": "smartphone",
                "specifications": ["A17 chip", "128GB storage", "6.1 inch display"],
                "rating": 4.5,
                "availability": "in_stock"
            }
        ],
        "sports": [
            {
                "id": "shoes_001",
                "name": "Nike Air Max",
                "price": 129.99,
                "category": "sports",
                "subcategory": "shoes",
                "specifications": ["size 10", "running", "mesh upper"],
                "rating": 4.2,
                "availability": "in_stock"
            }
        ]
    }

    # Filter products
    products = mock_products.get(input_data.category, [])

    # Filter by subcategory
    if input_data.subcategory:
        products = [p for p in products if p.get("subcategory") == input_data.subcategory]

    # Filter by budget
    if input_data.budget_max:
        products = [p for p in products if p.get("price", 0) <= input_data.budget_max]

    # Filter by specifications (simple contains check)
    if input_data.specifications:
        filtered_products = []
        for product in products:
            product_specs = product.get("specifications", [])
            if any(spec.lower() in " ".join(product_specs).lower() for spec in input_data.specifications):
                filtered_products.append(product)
        products = filtered_products

    search_query = f"category:{input_data.category}"
    if input_data.subcategory:
        search_query += f", subcategory:{input_data.subcategory}"
    if input_data.budget_max:
        search_query += f", max_budget:{input_data.budget_max}"
    if input_data.specifications:
        search_query += f", specs:{input_data.specifications}"

    return ProductSearchOutput(
        products=products,
        total_found=len(products),
        search_query=search_query
    )


def check_order_status_handler(input_data: OrderStatusInput) -> OrderStatusOutput:
    """Check the status of an order by order ID."""
    print(f"CALLED: check_order_status() order_id={input_data.order_id}")

    # Mock order database
    mock_orders = {
        "ORD001": {
            "status": "shipped",
            "tracking_number": "TRK123456789",
            "estimated_delivery": "2024-12-30",
            "current_location": "Distribution Center - Chicago"
        },
        "ORD002": {
            "status": "processing",
            "tracking_number": None,
            "estimated_delivery": "2024-12-28",
            "current_location": "Fulfillment Center"
        },
        "12345": {
            "status": "delivered",
            "tracking_number": "TRK987654321",
            "estimated_delivery": "2024-12-25",
            "current_location": "Delivered to doorstep"
        }
    }

    order_info = mock_orders.get(input_data.order_id)

    if not order_info:
        return OrderStatusOutput(
            order_id=input_data.order_id,
            status="not_found",
            tracking_info={"error": "Order not found in system"},
            estimated_delivery=None
        )

    tracking_info = {
        "tracking_number": order_info.get("tracking_number"),
        "current_location": order_info.get("current_location"),
        "last_updated": datetime.now().isoformat()
    }

    return OrderStatusOutput(
        order_id=input_data.order_id,
        status=order_info["status"],
        tracking_info=tracking_info,
        estimated_delivery=order_info.get("estimated_delivery")
    )

# Register ecommerce tools
register_tool("search_products", "Search for products", {"type": "object"}, search_products_handler)
register_tool("check_order_status", "Check order status", {"type": "object"}, check_order_status_handler)


# ---------------------------
# HTTP Endpoints
# ---------------------------

@app.get("/health")
async def health_endpoint():
    """Health check endpoint"""
    result = health_handler()
    return result.dict()

@app.get("/tools")
async def list_tools():
    """List available tools (MCP compatible)"""
    return {"tools": AVAILABLE_TOOLS}

@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, arguments: dict):
    """Call a specific tool"""
    # Find the tool
    tool = None
    for t in AVAILABLE_TOOLS:
        if t["name"] == tool_name:
            tool = t
            break

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")

    try:
        # Call the handler based on tool name
        if tool_name == "echo":
            result = echo_handler(EchoInput(**arguments))
        elif tool_name == "health":
            result = health_handler()
        elif tool_name == "sum_numbers":
            result = sum_numbers_handler(SumInput(**arguments))
        elif tool_name == "search_products":
            result = search_products_handler(ProductSearchInput(**arguments))
        elif tool_name == "check_order_status":
            result = check_order_status_handler(OrderStatusInput(**arguments))
        else:
            raise HTTPException(status_code=404, detail=f"Handler for {tool_name} not implemented")

        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------
# Main Entry Point
# ---------------------------

if __name__ == "__main__":
    print("🚀 Simple HTTP-based MCP Server starting...")
    print("🛠️  Available tools: echo, health, sum_numbers, search_products, check_order_status")

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8000"))

    print(f"🌐 Running HTTP server on {host}:{port}")
    print(f"📡 Health endpoint: http://{host}:{port}/health")
    print(f"🛠️  Tools endpoint: http://{host}:{port}/tools")

    uvicorn.run(app, host=host, port=port, log_level="info")
