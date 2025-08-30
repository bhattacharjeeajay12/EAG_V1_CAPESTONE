
from __future__ import annotations
from typing import Dict, Any
from .base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall, Present, Commit, Info

def nonempty(v): return v not in (None,"",[],{})

class OrderAgent(AgentBase):
    def __init__(self, tools, llm, cfg):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        e = ctx.nlu_result["current_turn"].get("entities", {})
        updated = {k:v for k,v in e.items() if nonempty(v)}
        needed = [k for k in ["product_id","shipping_address","payment_method"] if not nonempty(ws.slots.get(k)) and not nonempty(updated.get(k))]
        if needed:
            return AgentOutput(action=Ask(f"Please provide your {needed[0].replace('_',' ')}."), updated_slots=updated)
        # pretend commit immediately
        ws.status = "committing"
        return AgentOutput(action=Commit({"order_id":"ord_456"}), updated_slots=updated, mark_completed=True)
