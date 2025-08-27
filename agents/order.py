# agents/order.py
"""
OrderAgent:
- Sub-intents: check_status | modify | cancel | track
- If order_id missing, ask for it or offer most recent orders.
"""

from typing import Dict, Any, Optional
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall, Present
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.planner import PlannerConfig


class OrderAgent(AgentBase):
    def __init__(self, tools: ToolRegistry, llm: LLMClient, cfg: PlannerConfig):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    def decide_next(self, ctx: AgentContext) -> AgentOutput:
        slots = dict(ctx.workstream.slots or {})
        order_id = slots.get("order_id")
        sub_intent = ctx.nlu_result["current_turn"].get("sub_intent") or "check_status"

        if not order_id:
            # Ask, or list recent orders
            return AgentOutput(action=Ask("Could you share the order ID? I can also show your last 3 orders.", slot="order_id"))

        orders_tool = self.tools.get("Orders.get")
        if sub_intent in ("check_status", "track"):
            return AgentOutput(action=ToolCall(name=orders_tool.name, params={"order_id": order_id}))

        if sub_intent == "cancel":
            cancel_tool = self.tools.get("Orders.cancel")
            return AgentOutput(action=ToolCall(name=cancel_tool.name, params={"order_id": order_id}))

        if sub_intent == "modify":
            modify_tool = self.tools.get("Orders.modify")
            return AgentOutput(action=ToolCall(name=modify_tool.name, params={"order_id": order_id, "details": slots.get("details")}))

        return AgentOutput(action=Ask("Do you want to check, track, modify, or cancel the order?", slot=None))
