# agents/exchange.py
"""
ExchangeAgent:
- Similar to Return but asks for replacement criteria when eligible.
"""

from agents.base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.config import PlannerConfig


class ExchangeAgent(AgentBase):
    def __init__(self, tools: ToolRegistry, llm: LLMClient, cfg: PlannerConfig):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    def decide_next(self, ctx: AgentContext) -> AgentOutput:
        slots = dict(ctx.workstream.slots or {})
        order_id = slots.get("order_id")
        product = slots.get("product")
        if not order_id and not product:
            return AgentOutput(action=Ask("Which order or product would you like to exchange?", slot="order_id"))

        eligible_tool = self.tools.get("Exchanges.check_eligibility")
        return AgentOutput(action=ToolCall(name=eligible_tool.name, params={"order_id": order_id, "product": product}))
