from __future__ import annotations

import os
from typing import Dict, List

from pydantic import BaseModel, Field

from .base import BaseSSEMCPServer

__all__ = ["create_app", "server"]


class ProductSearchInput(BaseModel):
    category: str = Field(description="Product category")
    subcategory: str | None = Field(default=None, description="Product subcategory")
    max_price: float | None = Field(default=None, description="Maximum price filter")
    keywords: List[str] = Field(default_factory=list, description="Keywords to match in specifications")


class OrderStatusInput(BaseModel):
    order_id: str = Field(description="Order identifier")


server = BaseSSEMCPServer(
    title="Ecommerce SSE MCP Server",
    description="SSE-based MCP server exposing ecommerce utilities",
)


_FAKE_PRODUCTS: Dict[str, List[Dict[str, object]]] = {
    "electronics": [
        {
            "id": "laptop_001",
            "name": "Dell Inspiron 15",
            "price": 899.0,
            "subcategory": "laptop",
            "specifications": ["Intel i5", "8GB RAM", "256GB SSD", "15.6 inch"],
            "rating": 4.3,
        },
        {
            "id": "laptop_002",
            "name": "MacBook Air M2",
            "price": 1299.0,
            "subcategory": "laptop",
            "specifications": ["Apple M2", "8GB RAM", "512GB SSD", "13.3 inch"],
            "rating": 4.8,
        },
        {
            "id": "phone_101",
            "name": "Pixel 9",
            "price": 799.0,
            "subcategory": "smartphone",
            "specifications": ["Android 15", "128GB storage", "6.3 inch"],
            "rating": 4.6,
        },
    ],
    "sports": [
        {
            "id": "dumbbell_041",
            "name": "NordicTrack Adjustable Dumbbell",
            "price": 270.0,
            "subcategory": "dumbbells",
            "specifications": ["Adjustable", "Min 3kg", "Max 30kg"],
            "rating": 4.4,
        },
        {
            "id": "dumbbell_042",
            "name": "Amazon Basics Rubber Dumbbell",
            "price": 142.0,
            "subcategory": "dumbbells",
            "specifications": ["Fixed weight", "Rubber coated"],
            "rating": 4.1,
        },
    ],
}


_FAKE_ORDERS: Dict[str, Dict[str, object]] = {
    "ORD-1001": {
        "status": "shipped",
        "tracking": "TRK123456",
        "estimated_delivery": "2025-01-02",
        "last_location": "Distribution Center",
    },
    "ORD-2001": {
        "status": "processing",
        "tracking": None,
        "estimated_delivery": "2025-01-05",
        "last_location": "Packing Facility",
    },
}


@server.register_tool(
    name="search_products",
    description="Search products by category, price and keywords.",
    input_model=ProductSearchInput,
)
async def search_products(input_data: ProductSearchInput):
    yield {"message": f"Searching category '{input_data.category}'"}
    candidates = _FAKE_PRODUCTS.get(input_data.category.lower(), []).copy()

    if input_data.subcategory:
        yield {"message": f"Filtering subcategory '{input_data.subcategory}'"}
        candidates = [
            item for item in candidates if item.get("subcategory") == input_data.subcategory.lower()
        ]

    if input_data.max_price is not None:
        yield {"message": f"Applying price ceiling {input_data.max_price}"}
        candidates = [item for item in candidates if float(item.get("price", 0)) <= input_data.max_price]

    if input_data.keywords:
        key_string = ", ".join(input_data.keywords)
        yield {"message": f"Matching keywords: {key_string}"}
        keywords_lower = [kw.lower() for kw in input_data.keywords]
        candidates = [
            item
            for item in candidates
            if any(kw in " ".join(item.get("specifications", [])).lower() for kw in keywords_lower)
        ]

    yield {
        "products": candidates,
        "total_found": len(candidates),
        "query": input_data.model_dump(),
    }


@server.register_tool(
    name="order_status",
    description="Check status for a given order id.",
    input_model=OrderStatusInput,
)
async def order_status(input_data: OrderStatusInput):
    order = _FAKE_ORDERS.get(input_data.order_id)
    if not order:
        yield {
            "status": "not_found",
            "order_id": input_data.order_id,
            "message": "Order not found",
        }
        return

    yield {"message": "Fetching latest tracking information"}
    yield {
        "order_id": input_data.order_id,
        "status": order["status"],
        "tracking": order["tracking"],
        "estimated_delivery": order["estimated_delivery"],
        "last_location": order["last_location"],
    }


def create_app() -> FastAPI:
    return server.create_app()


if __name__ == "__main__":  # pragma: no cover - manual execution helper
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8101"))
    server.run(host=host, port=port)
