
from __future__ import annotations
from typing import Dict, Any

class LLMClient:
    async def propose_tools(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Dummy heuristic response for offline demo
        slots = payload.get("slots", {})
        state = payload.get("state")
        if "category" in slots and "subcategory" in slots and state in {"collecting","presenting"}:
            return {"candidates":[{"tool":"search_products","params":slots,"score":0.85,"reason":"mandatories present"}]}
        return {"candidates":[], "fallback_ask":"Could you tell me the category?"}
