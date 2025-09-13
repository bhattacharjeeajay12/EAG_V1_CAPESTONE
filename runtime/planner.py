# planner.py (updated)
from typing import Dict, Optional, Any
from config.planner_config import PlannerConfig, INTENT_THRESHOLDS
from nlu.discovery_nlu import PlannerNLU
from core.conversation_history import ConversationHistory
from agents.base import AgentBase, Action, Ask, Info, AgentOutput, AgentContext
from agents.discovery import DiscoveryAgent
from agents.order import OrderAgent
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.logging_setup import configure_logging
from core.goals import GOALS, has_all
logger = configure_logging("planner")

class Planner:
    def __init__(self, nlu: Optional[PlannerNLU] = None, tools: Optional[ToolRegistry] = None,
                 llm_client: Optional[LLMClient] = None, config: PlannerConfig = PlannerConfig()):
        self.nlu = nlu or PlannerNLU()
        self.tools = tools or ToolRegistry()
        self.llm = llm_client or LLMClient()
        self.cfg = config
        self.history = ConversationHistory()
        self.agents: Dict[str, AgentBase] = {
            "DISCOVERY": DiscoveryAgent(self.tools, self.llm, self.cfg),
            "ORDER": OrderAgent(self.tools, self.llm, self.cfg),
        }

    async def handle_user_turn(self, user_message: str) -> Action:
        convo_ctx = self.history.as_nlu_context()

        # TODO: replace with real NLU call
        nlu_result = await self.nlu.analyze_message(user_message, conversation_context=convo_ctx)
        # The following is placeholder; in production nlu_result must follow agreed schema.
        # nlu_result: Dict[str, Any] = {'continuity': {'clarification_message': None, 'confidence': 0.9, 'continuity_type': 'CONTINUATION', 'reasoning': 'First message of the conversation, new DISCOVERY workflow must be created.', 'workstream_decision': {'existing_workflow_status': 'NULL', 'new_workstreams': [{'target': {'category': 'electronics', 'subcategory': 'laptop'}, 'type': 'DISCOVERY'}]}}, 'current_turn': {'confidence': 0.95, 'entities': {'category': [], 'products': [{'category': 'electronics', 'subcategory': 'laptop'}], 'specifications': {}, 'subcategory': []}, 'intent': 'DISCOVERY', 'reasoning': 'User explicitly states a need for a laptop.', 'referenced_entities': []}}

        # Append user + nlu to history
        self.history.append_user_turn(user_message, nlu_result)

        intent = nlu_result["current_turn"]["intent"]
        confidence = nlu_result["current_turn"]["confidence"]

        # Confidence check for intent
        if confidence < INTENT_THRESHOLDS.get(intent, 0.5):
            action = Ask("Could you clarify what you’d like to do?")
            self.history.append_action(action)
            return action

        # --- Handle continuity decisions ---
        continuity = nlu_result.get("continuity", {})
        continuity_type = continuity.get("continuity_type")
        work_decision = continuity.get("workstream_decision", {})
        clarification_message = continuity.get("clarification_message")

        # If continuity indicates SWITCH or UNCLEAR, we MUST ask user for clarification before applying changes.
        if continuity_type in ("SWITCH", "UNCLEAR"):
            # Save pending decision so next user reply can resolve it
            pending = {
                "continuity": continuity,
                "nlu_result": nlu_result
            }
            self.history.set_pending_decision(pending)

            # Ask user the provided natural clarification message (always required per policy)
            ask_msg = clarification_message or "Can you confirm how you'd like to proceed?"
            action = Ask(ask_msg)
            self.history.append_action(action)
            return action

        # If there's a pending decision from earlier and we are now continuing, try to resolve it:
        pending = self.history.get_pending_decision()
        if pending:
            # If user answered clarifying question, we rely on current nlu_result to indicate which ws to continue.
            # We'll attempt to find a paused workstream matching referenced_entities or entities and resume it.
            referenced = nlu_result["current_turn"].get("referenced_entities", []) or []
            entities_products = nlu_result["current_turn"].get("entities", {}).get("products", [])

            candidate_ws = None
            # prefer referenced_entities (explicit)
            if referenced:
                target = referenced[0]  # take first resolved referent
                candidate_ws = self.history.find_workstream_by_target(pending["nlu_result"]["current_turn"]["intent"], target)
            elif entities_products:
                # user named a target; see if a paused WS matches
                target = entities_products[0]
                candidate_ws = self.history.find_workstream_by_target(pending["nlu_result"]["current_turn"]["intent"], target)

            if candidate_ws:
                # resume it
                self.history.resume_workstream(candidate_ws.id)
                self.history.clear_pending_decision()
                focused_ws = candidate_ws
            else:
                # No matching paused WS; fall through to normal flow (create or ensure)
                self.history.clear_pending_decision()
                focused_ws = None
        else:
            focused_ws = self.history.get_focused_ws()

        # If no focused workstream (first message or nothing active), create new workstream(s).
        if not focused_ws:
            # If NLU suggested new_workstreams, create first suggested as focused.
            new_ws_list = work_decision.get("new_workstreams", []) if work_decision else []
            if new_ws_list:
                first = new_ws_list[0]
                seed = {}
                target = first.get("target") or {}
                # seed slots with category/subcategory if present
                if target:
                    seed["category"] = target.get("category")
                    seed["subcategory"] = target.get("subcategory")
                focused_ws = self.history.ensure_workstream(first.get("type", intent), seed_entities=seed)
                # Create any additional new workstreams (paused by default)
                for extra in new_ws_list[1:]:
                    ew = self.history.ensure_workstream(extra.get("type", intent), seed_entities=extra.get("target", {}))
                    # Immediately pause extras (they were created but not focused)
                    self.history.pause_workstream(ew.id)
            else:
                # No explicit new workstreams, create based on intent
                focused_ws = self.history.ensure_workstream(intent, seed_entities={})
        else:
            # There's an active focused workstream. However, if current message references a paused workstream,
            # prefer resuming that one.
            referenced = nlu_result["current_turn"].get("referenced_entities", []) or []
            if referenced:
                target = referenced[0]
                candidate_ws = self.history.find_workstream_by_target(focused_ws.type, target)
                if candidate_ws and getattr(candidate_ws, "status") == "paused":
                    self.history.resume_workstream(candidate_ws.id)
                    focused_ws = candidate_ws

        # Route to agent for the focused workstream
        agent = self.agents.get(focused_ws.type)
        if not agent:
            action = Info(f"Sorry, I can’t handle {focused_ws.type} yet.")
            self.history.append_action(action)
            return action

        # Build agent context
        agent_ctx = AgentContext(workstream=focused_ws, session=self.history.session_snapshot(), nlu_result=nlu_result)

        # Delegate decision to agent
        output: AgentOutput = await agent.decide_next(agent_ctx)

        # Apply updates
        if output.updated_slots:
            focused_ws.slots.update(output.updated_slots)

        # If agent returns presented_items, store them and mark workstream as presenting.
        # Ensure candidates is always a list (avoid None/False).
        if output.presented_items is not None:
            # Guard: coerce falsy->empty list so bool(ws.candidates) behaves correctly.
            focused_ws.candidates = output.presented_items or []
            # Mark the workstream state so GOALS.is_done can rely on the presenting state
            focused_ws.status = getattr(focused_ws, "status", "") or "presenting"
        if output.mark_completed:
            focused_ws.status = "completed"

        self.history.append_action(output.action)

        # Goal check
        goal = GOALS.get((focused_ws.type, None))
        if goal and has_all(focused_ws.slots, set(goal["mandatory"])) and goal["is_done"](focused_ws):
            focused_ws.status = "completed"
            logger.info(f"GOAL reached for {focused_ws.type}")

        return output.action
