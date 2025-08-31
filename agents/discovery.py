from .base import AgentBase, AgentContext, AgentOutput, Ask, Present, Info
from core.goals import TOOL_GUARDS, has_all
from core.states import DiscoveryState
from core.fsm_engine import FSMEngine
from core.fsm_rules import DISCOVERY_TRANSITIONS

class DiscoveryAgent(AgentBase):
    def __init__(self, tools, llm, cfg):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg
        self.fsm = FSMEngine(DISCOVERY_TRANSITIONS)  # 👈 FSM engine here

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream

        # === STEP 1: FSM progression NEW → COLLECTING
        if ws.status == DiscoveryState.NEW:
            ws.status = DiscoveryState.COLLECTING

        # Update slots from NLU entities (later: agent-specific LLM extraction)
        entities = ctx.nlu_result["current_turn"].get("entities", {})
        ws.update_slots(entities)

        # === STEP 2: Mandatory slots
        if ws.status == DiscoveryState.COLLECTING:
            if not has_all(ws.slots, {"category", "subcategory"}):
                # Still missing mandatory slots → stay in COLLECTING
                return AgentOutput(action=Ask("Could you specify the category and subcategory?"))

            # All mandatory slots present → transition to READY
            if self.fsm.can_transition(ws.status.value, DiscoveryState.READY.value):
                ws.status = DiscoveryState.READY

        # === STEP 3: Optional specs
        missing_specs = ws.missing_specifications()
        if missing_specs and not ws.skip_specifications:
            specs_str = ", ".join(missing_specs[:3])  # show top 3
            return AgentOutput(action=Ask(f"Would you like to add specifications like {specs_str}?"))

        # === STEP 4: READY → PROCESSING
        if ws.status == DiscoveryState.READY:
            proposal = await self.llm.propose_tools(ws)
            tool = proposal.get("tool")
            params = proposal.get("params", {})

            guard = TOOL_GUARDS.get(tool)
            if guard and has_all(ws.slots, guard["required"]):
                # 1️⃣ Execute tool(s)
                results = await self.tools.call(tool, params)
                ws.candidates = results

                # # 2️⃣ Summarizer hook (LLM post-processing)
                # results = await self.llm.summarize(results)

                # 3️⃣ Transition FSM
                ws.status = DiscoveryState.PRESENTING

                return AgentOutput(action=Present(results, affordances=["compare","select"]))

        # === STEP 5: PRESENTING
        if ws.status == DiscoveryState.PRESENTING:
            return AgentOutput(action=Info("You can compare, select, or refine your choices."))

        # Default
        return AgentOutput(action=Info("Still collecting more details..."))
