
from __future__ import annotations
from typing import Dict, Any, List

class ToolRegistry:
    async def call(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate tool results
        if name == "search_products":
            items = [{"id": f"p{i}", "title": f"Gaming Laptop {i}", "price": 1000 + i*50} for i in range(1, 6)]
            return {"items": items}
        elif name == "build_compare_view":
            return {"items": [{"id":"left"}, {"id":"right"}]}
        elif name == "fetch_specs":
            return {"specs": {"cpu":"i7","ram":"16GB"}}
        return {"ok": True}
