# tools/registry.py
"""
ToolRegistry:
- Central store for available tools (backed by DB or services).
- Provides .get(name) and simple grouping/lookup.
- Agents can also ask LLM to pick a tool from an allowed list (see prompts/agent_prompts.py).
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from tools.tools import (
    CatalogSemanticSearch, RecommenderRank, OrdersGet, OrdersCancel, OrdersModify,
    ReturnsCheckEligibility, ExchangesCheckEligibility, PaymentsCharge
)

@dataclass
class ToolSpec:
    name: str
    fn: Any
    description: str

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {
            "Catalog.semantic_search": ToolSpec("Catalog.semantic_search", CatalogSemanticSearch(), "Semantic search over products"),
            "Recommender.rank": ToolSpec("Recommender.rank", RecommenderRank(), "Re-rank search results"),
            "Orders.get": ToolSpec("Orders.get", OrdersGet(), "Get order and tracking status"),
            "Orders.cancel": ToolSpec("Orders.cancel", OrdersCancel(), "Cancel an order"),
            "Orders.modify": ToolSpec("Orders.modify", OrdersModify(), "Modify an order"),
            "Returns.check_eligibility": ToolSpec("Returns.check_eligibility", ReturnsCheckEligibility(), "Check return eligibility"),
            "Exchanges.check_eligibility": ToolSpec("Exchanges.check_eligibility", ExchangesCheckEligibility(), "Check exchange eligibility"),
            "Payments.charge": ToolSpec("Payments.charge", PaymentsCharge(), "Perform a payment charge"),
        }

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")
        return self._tools[name]

    def all(self) -> Dict[str, ToolSpec]:
        return dict(self._tools)
