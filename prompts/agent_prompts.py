# prompts/agent_prompts.py
"""
Small prompts agents could use (via LLM) to select tools when multiple tools are available.
In this skeleton we mostly choose tools via rules, but this shows how you'd delegate choice to LLM if needed.
"""

DISCOVERY_TOOL_PICKER = """You are a tool selector for product discovery.
User goal: {goal}
Available tools:
1) Catalog.semantic_search — semantic search over catalog
2) Recommender.rank — re-rank a list of items

Return JSON: {{"tool": "Catalog.semantic_search" | "Recommender.rank", "reason": "short"}}"""

ORDER_TOOL_PICKER = """You are a tool selector for order workflows.
Goal: {goal}
Tools:
- Orders.get
- Orders.cancel
- Orders.modify

Return JSON: {{"tool": "Orders.get" | "Orders.cancel" | "Orders.modify", "reason": "short"}}"""
