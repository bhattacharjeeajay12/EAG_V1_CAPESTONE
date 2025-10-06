
from typing import Dict, Any, List
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, Present, Info
from core.goals import TOOL_GUARDS, has_all
from core.states import DiscoveryState
from core.fsm_engine import FSMEngine
# from core.fsm_rules import DISCOVERY_TRANSITIONS
from prompts.discovery import SYSTEM_PROMPT as DISCOVERY_SYSTEM_PROMPT
import json


class DiscoveryAgent(AgentBase):
    def __init__(self, tools, llm=None, cfg=None):
        super().__init__()
        self.tools = tools
        self.llm = llm
        self.cfg = cfg
        # self.fsm = FSMEngine(DISCOVERY_TRANSITIONS)
        self.specifications_ask = False
        # try load discovery SYSTEM_PROMPT from prompts.discovery if present
        self.discovery_prompt = DISCOVERY_SYSTEM_PROMPT

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
        if updated:
            ws.update_slots(updated)

        # === NEW: Call Discovery LLM to collect/normalize specifications (if LLM available) ===
        spec_package = None
        try:
            # prepare current query and context
            current_query = ctx.nlu_result.get("raw_text") or (ctx.session and ctx.session.get("turns") and ctx.session.get("turns")[-1].get("content")) or ""
            conv = ctx.session.get("turns") if ctx.session else []
            if self.llm:
                user_prompt = "CURRENT_QUERY: " + (current_query or "") + "\nSLOTS_TILL_NOW: " + json.dumps(ws.slots or {}) + "\nCONTEXT: " + json.dumps(conv[-5:] if conv else [])
                raw = await self.llm.generate(self.discovery_prompt, user_prompt)
                # try parse json
                try:
                    spec_package = json.loads(raw.strip())
                except Exception:
                    # attempt to extract JSON blob from text
                    import re as _re
                    t = raw or ""
                    i = t.find("{"); j = t.rfind("}")
                    if i!=-1 and j!=-1:
                        try:
                            spec_package = json.loads(t[i:j+1])
                        except Exception:
                            spec_package = None
        except Exception:
            spec_package = None

        # apply spec_package if present
        if spec_package:
            updated_slots_pkg = spec_package.get("updated_slots") or {}
            if updated_slots_pkg:
                ws.update_slots(updated_slots_pkg)
            # allow discovery LLM to indicate missing spec keys
            missing_from_pkg = spec_package.get("missing_spec_keys")
            if missing_from_pkg is not None:
                missing_specs = missing_from_pkg
            else:
                # fallback to existing method
                if hasattr(ws, "missing_specifications") and callable(getattr(ws, "missing_specifications")):
                    missing_specs = ws.missing_specifications() or []
                else:
                    missing_specs = []
        else:
            # existing behavior for missing specs
            if hasattr(ws, "missing_specifications") and callable(getattr(ws, "missing_specifications")):
                missing_specs = ws.missing_specifications() or []
            else:
                missing_specs = []

                # === STEP 2: Mandatory slots (only subcategory in slim schema) ===
        if ws.status == DiscoveryState.COLLECTING:
            if not has_all(ws.slots, {"subcategory"}):
                return AgentOutput(
                    action=Ask(question="Which subcategory are you interested in?", slot="subcategory"),
                    updated_slots=updated
                )
            # # All mandatory present → READY
            # if self.fsm.can_transition(ws.status.value, DiscoveryState.READY.value):
            #     ws.status = DiscoveryState.READY

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
            # # READY → PRESENTING
            # if self.fsm.can_transition(ws.status.value, DiscoveryState.PRESENTING.value):
            #     ws.status = DiscoveryState.PRESENTING

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
