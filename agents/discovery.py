
from typing import Dict, Any, List
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, Present, Info
from core.goals import TOOL_GUARDS, has_all
from core.states import DiscoveryState
from core.fsm_engine import FSMEngine
from core.fsm_rules import DISCOVERY_TRANSITIONS

class DiscoveryAgent(AgentBase):
    def __init__(self, tools, llm=None, cfg=None):
        super().__init__()
        self.tools = tools
        self.llm = llm
        self.cfg = cfg
        self.fsm = FSMEngine(DISCOVERY_TRANSITIONS)

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream

        # === STEP 0: Ensure initial state ===
        if ws.status == DiscoveryState.NEW:
            ws.status = DiscoveryState.COLLECTING

        # === STEP 1: Merge slim entities (top-level) → slots ===
        entities: Dict[str, Any] = ctx.nlu_result.get("entities", {}) or {}
        updated: Dict[str, Any] = {}
        if entities.get("subcategory"):
            updated["subcategory"] = entities["subcategory"]
        if entities.get("order_id"):
            updated["order_id"] = entities["order_id"]
        if updated:
            ws.update_slots(updated)

        # === STEP 2: Mandatory slots (only subcategory in slim schema) ===
        if ws.status == DiscoveryState.COLLECTING:
            if not has_all(ws.slots, {"subcategory"}):
                return AgentOutput(
                    action=Ask(question="Which subcategory are you interested in?", slot="subcategory"),
                    updated_slots=updated
                )
            # All mandatory present → READY
            if self.fsm.can_transition(ws.status.value, DiscoveryState.READY.value):
                ws.status = DiscoveryState.READY

        # === STEP 3: Optional specification prompting ===
        # Ask for up to 3 missing specs unless user opted to skip.
        if ws.status in (DiscoveryState.COLLECTING, DiscoveryState.READY):
            if hasattr(ws, "missing_specifications") and callable(getattr(ws, "missing_specifications")):
                missing_specs = ws.missing_specifications() or []
            else:
                missing_specs = []
            if missing_specs and not getattr(ws, "skip_specifications", False):
                specs_str = ", ".join(missing_specs[:3])
                return AgentOutput(
                    action=Ask(question=f"Would you like to add specifications like {specs_str}?", slot=None),
                    updated_slots=updated
                )

        # === STEP 4: Execute tool when READY ===
        if ws.status == DiscoveryState.READY:
            # Decide which discovery tool to use
            proposed_tool = None
            params: Dict[str, Any] = {}
            # Prefer LLM tool proposal if available
            if self.llm and hasattr(self.llm, "propose_tools"):
                try:
                    proposal = await self.llm.propose_tools(ws)
                    proposed_tool = (proposal or {}).get("tool")
                    params = (proposal or {}).get("params") or {}
                except Exception:
                    proposed_tool = None
                    params = {}
            # Fallbacks
            if not proposed_tool:
                proposed_tool = "filter_products"
                params = {"subcategory": ws.slots.get("subcategory")}

            # Guard requirements
            guard = TOOL_GUARDS.get(proposed_tool)
            if guard and not has_all(ws.slots, set(guard.get("required", []))):
                # Ask for whatever guard requires (should be rare with slim schema)
                need = ", ".join(guard.get("required", []))
                return AgentOutput(action=Ask(question=f"To search properly, I need: {need}. Could you provide these?"))

            # Execute tool
            try:
                results: List[Dict[str, Any]] = await self.tools.call(proposed_tool, params)
            except Exception as e:
                return AgentOutput(action=Info(message=f"Search failed: {e}"), updated_slots=updated)

            ws.candidates = results or []
            # READY → PRESENTING
            if self.fsm.can_transition(ws.status.value, DiscoveryState.PRESENTING.value):
                ws.status = DiscoveryState.PRESENTING

            return AgentOutput(
                action=Present(items=results, text="Here are some options.",
                               affordances=["compare", "select", "refine"]),
                presented_items=results
            )

        # === STEP 5: PRESENTING ===
        if ws.status == DiscoveryState.PRESENTING:
            return AgentOutput(action=Info(message="You can compare, select, or refine your choices."))

        # Fallback
        return AgentOutput(action=Info(message="Still collecting more details..."))
