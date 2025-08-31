from .base import AgentBase, AgentContext, AgentOutput, Ask, ToolCall, Present, Info
from core.goals import TOOL_GUARDS, has_all
from core.states import DiscoveryState
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

        # Step 1: Collect mandatory slots
        if not has_all(ws.slots, {"category","subcategory"}):
            ws.status = DiscoveryState.COLLECTING
            return AgentOutput(action=Ask("Could you specify the category and subcategory?"))

        # Step 2: Ready to call tools
        if ws.status in {DiscoveryState.NEW, DiscoveryState.COLLECTING, DiscoveryState.READY}:
            ws.status = DiscoveryState.PROCESSING

            # LLM proposes tool
            proposal = await self.llm.propose_tools(ws)
            tool = proposal.get("tool")
            params = proposal.get("params", {})

            # Validate against FSM guards
            guard = TOOL_GUARDS.get(tool)
            if guard and has_all(ws.slots, guard["required"]):
                # Execute tool here 👇
                results = await self.tools.call(tool, params)
                ws.candidates = results
                ws.status = DiscoveryState.PRESENTING
                return AgentOutput(action=Present(results, affordances=["compare","select"]))

        # Step 3: If already presenting, wait for user choice
        if ws.status == DiscoveryState.PRESENTING:
            return AgentOutput(action=Info("You can compare, select, or refine your choices."))

        return AgentOutput(action=Info("Still collecting more details..."))
