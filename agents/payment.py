# agents/payment.py
"""
PaymentAgent:
- sub_intents: select_method | complete | resolve_issue
- Only needs method to attempt payment; if missing, present methods or ask.
"""

from agents.base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.planner import PlannerConfig


class PaymentAgent(AgentBase):
    def __init__(self, tools: ToolRegistry, llm: LLMClient, cfg: PlannerConfig):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    def decide_next(self, ctx: AgentContext) -> AgentOutput:
        sub = ctx.nlu_result["current_turn"].get("sub_intent") or "select_method"
        slots = dict(ctx.workstream.slots or {})
        method = slots.get("method")
        amount = slots.get("amount")
        issue = slots.get("issue")

        if sub == "select_method" and not method:
            return AgentOutput(action=Ask("How would you like to pay? (card / upi / cod)", slot="method"))

        if sub == "complete" and method:
            pay_tool = self.tools.get("Payments.charge")
            return AgentOutput(action=ToolCall(name=pay_tool.name, params={"method": method, "amount": amount}))

        if sub == "resolve_issue" and not issue:
            return AgentOutput(action=Ask("What issue are you seeing with payment?", slot="issue"))

        return AgentOutput(action=Ask("Do you want to select a method, complete a payment, or fix an issue?", slot=None))
