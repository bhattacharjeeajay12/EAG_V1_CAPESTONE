
from __future__ import annotations
from typing import Dict, Any, List

class EnhancedNLU:
    async def analyze_message(self, text: str, conversation_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Minimal heuristic NLU for demo
        text_l = text.lower()
        intent = "DISCOVERY"
        sub_intent = None
        if "buy" in text_l or "order" in text_l:
            intent = "ORDER"; sub_intent = "place_order"
        if "compare" in text_l:
            sub_intent = "compare"; intent = "DISCOVERY"
        entities = {}
        if "laptop" in text_l: entities["category"] = "laptop"
        if "tablet" in text_l: entities["subcategory"] = "tablet"
        if "gaming" in text_l: entities["subcategory"] = "gaming"
        if "$" in text_l:
            import re
            m = re.search(r"\$(\d+)", text_l)
            if m: entities["price_max"] = int(m.group(1))
        continuity = {"continuity_type": "CONTINUATION"}
        return {"current_turn": {"intent": intent, "sub_intent": sub_intent, "entities": entities, "confidence": 0.9},
                "continuity": continuity}
