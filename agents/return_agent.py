# agents/return_agent.py
"""
ReturnAgent:
- If neither product nor order_id present, ask for identification.
- Check eligibility first; if eligible, create RMA.
"""

from agents.base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.config import PlannerConfig


class ReturnAgent(AgentBase):
    def __init__(self, tools: ToolRegistry, llm: LLMClient, cfg: PlannerConfig):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    def decide_next(self, ctx: AgentContext) -> AgentOutput:
        slots = dict(ctx.workstream.slots or {})
        order_id = slots.get("order_id")
        product = slots.get("product")
        if not order_id and not product:
            return AgentOutput(action=Ask("Which order or product is this return for?", slot="order_id"))

        eligible_tool = self.tools.get("Returns.check_eligibility")
        return AgentOutput(action=ToolCall(name=eligible_tool.name, params={"order_id": order_id, "product": product}))
