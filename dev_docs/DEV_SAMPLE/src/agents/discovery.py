
from __future__ import annotations
from typing import Dict, Any, Optional, List
from .base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall, Present, Info
from core.goals import TOOL_GUARDS, has_all
from core.llm_client import LLMClient

def nonempty(v): return v not in (None,"",[],{})

class DiscoveryAgent(AgentBase):
    def __init__(self, tools, llm: LLMClient, cfg):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        turn = ctx.nlu_result["current_turn"]
        sub_intent = turn.get("sub_intent")
        entities = turn.get("entities", {})

        updated_slots = {k:v for k,v in entities.items() if nonempty(v)}

        # If collecting, enforce mandatories first (ask just one question)
        if ws.status == "collecting":
            for req in ("category","subcategory"):
                if not nonempty(ws.slots.get(req)) and not nonempty(updated_slots.get(req)):
                    return AgentOutput(action=Ask(f"Which {req}?"), updated_slots=updated_slots)

        # Ask LLM to propose tools
        payload = {
            "state": ws.status,
            "slots": {**ws.slots, **updated_slots},
            "sub_intent": sub_intent,
            "tools": [{"name":k, "requires": list(v["required"]), "next_state": v["next_state"]} for k,v in TOOL_GUARDS.items()],
        }
        proposal = await self.llm.propose_tools(payload)
        candidates = sorted(proposal.get("candidates", []), key=lambda c: c.get("score",0), reverse=True)

        chosen = None
        for c in candidates:
            name = c.get("tool")
            params = c.get("params", {})
            guard = TOOL_GUARDS.get(name)
            if not guard: continue
            merged = {**ws.slots, **params}
            if ws.status in guard["allowed_states"] and has_all(merged, guard["required"]):
                chosen = (name, params, guard["next_state"])
                break

        if not chosen:
            ask = proposal.get("fallback_ask") or "Could you clarify what to explore next?"
            return AgentOutput(action=Ask(ask), updated_slots=updated_slots)

        name, params, next_state = chosen
        ws.status = next_state
        return AgentOutput(action=ToolCall(name, params), updated_slots=updated_slots)
