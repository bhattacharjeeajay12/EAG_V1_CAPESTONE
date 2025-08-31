# tools/registry.py
from typing import Callable, Dict, Awaitable, Any

class ToolRegistry:
    def __init__(self):
        # Register available tools here
        self._registry: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {
            "search_products": self._search_products,
            "place_order": self._place_order,
        }

    async def call(self, name: str, params: dict):
        """Dispatcher: find tool by name and call it."""
        tool = self._registry.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return await tool(params)

    # ---------- Tools ----------
    async def _search_products(self, params: dict):
        # Stub: return fake products
        return [
            {"id": "p1", "name": "Gaming Laptop 1", "brand": "Dell"},
            {"id": "p2", "name": "Gaming Laptop 2", "brand": "HP"},
        ]

    async def _place_order(self, params: dict):
        # Stub: fake order placement
        return {
            "order_id": "ord_123",
            "product_id": params.get("product_id"),
            "status": "confirmed"
        }
