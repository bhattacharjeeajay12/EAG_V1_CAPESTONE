# agents/discovery.py
"""
DiscoveryAgent:
- Enforces that `category` and `subcategory` are mandatory to SEARCH.
- Treats messages like "I need a laptop" as: category=electronics, subcategory=laptop (product may be absent).
- If user gives a very specific string ("Dell Inspiron 15"), keep it as a `product` hint AND mirror brand/model in specifications
  if NLU delivered them — but do not block if specs are missing.
- quantity is NOT required at discovery time; it matters at checkout/commit.

Decision table (simplified):
1) If missing category → ASK(category)
2) Else if missing subcategory → ASK(subcategory)
3) Else if COMPARE needed and one side missing → ASK(comparison item)
4) Else → TOOL semantic_search + rank → PRESENT top-K with affordances
"""

from typing import Dict, Any, List, Optional
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall, Present
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.config import PlannerConfig  # simple dataclass, no circular deps

MANDATORY_SLOTS = ("category", "subcategory")


class DiscoveryAgent(AgentBase):
    def __init__(self, tools: ToolRegistry, llm: LLMClient, cfg: PlannerConfig):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    def decide_next(self, ctx: AgentContext) -> AgentOutput:
        slots = dict(ctx.workstream.slots or {})
        # Normalize mandatorys
        category = slots.get("category")
        subcategory = slots.get("subcategory")
        product = slots.get("product")
        specs = slots.get("specifications") or {}
        budget = slots.get("budget")

        # 1) Ask for mandatory fields
        if not category:
            return AgentOutput(action=Ask("Which category are you shopping for?", slot="category"))
        if not subcategory:
            return AgentOutput(action=Ask("Great — which subcategory? (e.g., laptop, smartphone, shoes)", slot="subcategory"))

        # 2) Compare flow needs exactly two sides
        comp = ctx.workstream.compare or {"left": None, "right": None}
        if (comp.get("left") is None) != (comp.get("right") is None):
            return AgentOutput(action=Ask("What’s the other item to compare with?", slot="comparison_items"))

        # 3) Build a semantic search query
        # Treat "product" as a strong hint in the subcategory. If product is just a repetition of subcategory, keep it but don't block.
        query = {
            "category": category,
            "subcategory": subcategory,
            "product_hint": product,
            "specifications": specs,
            "budget": budget
        }

        # 4) Choose the right tool from the registry (semantic search + rank)
        search_tool = self.tools.get("Catalog.semantic_search")
        rank_tool = self.tools.get("Recommender.rank")

        # 5) Tool calls (Planner runtime will execute; here we just emit the intent)
        # Keep it one action per turn: first call search, next turn will present results after tool execution returns
        return AgentOutput(
            action=ToolCall(name=search_tool.name, params={"query": query, "top_k": self.cfg.top_k_present}),
            updated_slots=None,
            presented_items=None
        )

    # (Your runtime would handle the actual tool execution and feed the results back next turn.)
