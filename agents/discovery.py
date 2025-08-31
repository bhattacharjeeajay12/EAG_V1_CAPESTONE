"""
DiscoveryAgent manages product discovery flows.
"""
from markdown_it.common.entities import entities

from .base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall, Info
from core.goals import TOOL_GUARDS, has_all
from enum import Enum



class DiscoveryAgent(AgentBase):
    def __init__(self, tools, llm, cfg):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        # todo: entites should be extracted only using discovery agent LLM
        # entities = ctx.nlu_result["current_turn"].get("entities", {})
        entities = {"category": "electronics", "subcategory": "laptop", "budget": "$500", "specifications": {}}
        ws.update_slots(entities)

        # Mandatory slot check
        if not has_all(ws.slots, {"category","subcategory"}):
            return AgentOutput(action=Ask("Could you specify what your are looking for?"))

        # Not mandatory slot check - specification
        missing_specs = ws.missing_specifications()
        if missing_specs:
            specs_str = ", ".join(missing_specs[:3])  # show top 3
            return AgentOutput(action=Ask(f"Would you like to add specifications like {specs_str}?"))

        # todo: temporary bypass specification collection
        ws.skip_specifications = True

        # Ask LLM for tool proposal
        proposal = await self.llm.propose_tools(ws)
        tool = proposal.get("tool")
        params = proposal.get("params", {})

        guard = TOOL_GUARDS.get(tool)
        if guard and has_all(ws.slots, guard["required"]) and ws.status in guard["allowed_states"]:
            ws.status = guard["next_state"]
            return AgentOutput(action=ToolCall(tool, params))

        return AgentOutput(action=Info("Still collecting more details..."))
