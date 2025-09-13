# planner.py (updated to handle pending Ask -> slot mapping)
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

        # Real NLU call should go here
        nlu_result = await self.nlu.analyze_message(user_message, conversation_context=convo_ctx)
        # nlu_result: Dict[str, Any] = {'continuity': {'clarification_message': None, 'confidence': 0.9, 'continuity_type': 'CONTINUATION', 'reasoning': 'First message of the conversation, new DISCOVERY workflow must be created.', 'workstream_decision': {'existing_workflow_status': 'NULL', 'new_workstreams': [{'target': {'category': 'electronics', 'subcategory': 'laptop'}, 'type': 'DISCOVERY'}]}}, 'current_turn': {'confidence': 0.95, 'entities': {'category': [], 'products': [{'category': 'electronics', 'subcategory': 'laptop'}], 'specifications': {}, 'subcategory': []}, 'intent': 'DISCOVERY', 'reasoning': 'User explicitly states a need for a laptop.', 'referenced_entities': []}}

        # Append user turn to history
        self.history.append_user_turn(user_message, nlu_result)

        intent = nlu_result["current_turn"]["intent"]
        confidence = nlu_result["current_turn"]["confidence"]

        # Confidence check
        if confidence < INTENT_THRESHOLDS.get(intent, 0.5):
            action = Ask("Could you clarify what you’d like to do?")
            self.history.append_action(action)
            return action

        # --- Pending Ask consumption ---
        pending_pair = self.history.find_any_pending_ask()
        if pending_pair:
            pending_ws_id, ask_info = pending_pair
            # Prefer NLU-extracted entity value if available, else raw user_message
            # This simple mapping writes reply into the pending slot for that workstream.
            slot_name = ask_info.get("slot")
            filled_value = None
            # Check NLU entities for a simple scalar mapping (fallback to user_message)
            entities = nlu_result["current_turn"].get("entities", {})
            # If slot_name likely refers to category/subcategory and entities present, use them
            if slot_name in ("category", "subcategory") and entities.get("products"):
                first_prod = entities["products"][0]
                filled_value = first_prod.get(slot_name) or user_message
            elif slot_name and entities.get(slot_name):
                filled_value = entities.get(slot_name)
            else:
                filled_value = user_message

            # Apply to the workstream slots
            ws = self.history.workstreams.get(pending_ws_id)
            if ws:
                ws.slots[slot_name or "last_answer"] = filled_value
                # resume this workstream (user answered the ask -> make it focused)
                ws.status = "active"
                self.history.set_focus(ws.id)
            # clear pending ask
            self.history.clear_pending_ask(pending_ws_id)
            # continue with normal pipeline using this workstream as focused
        # --- end pending ask consumption ---

        # Handle continuity decisions
        continuity = nlu_result.get("continuity", {})
        continuity_type = continuity.get("continuity_type")
        work_decision = continuity.get("workstream_decision", {})
        clarification_message = continuity.get("clarification_message")

        # If continuity indicates SWITCH or UNCLEAR, ask the user for clarification (store pending decision)
        if continuity_type in ("SWITCH", "UNCLEAR"):
            pending = {
                "continuity": continuity,
                "nlu_result": nlu_result
            }
            self.history.set_pending_decision(pending)
            ask_msg = clarification_message or "Can you confirm how you'd like to proceed?"
            action = Ask(ask_msg)
            self.history.append_action(action)
            return action

        # If there is a pending continuity decision but user now replied, attempt to resolve (resume/create)
        pending = self.history.get_pending_decision()
        if pending:
            referenced = nlu_result["current_turn"].get("referenced_entities", []) or []
            entities_products = nlu_result["current_turn"].get("entities", {}).get("products", [])
            candidate_ws = None
            if referenced:
                target = referenced[0]
                candidate_ws = self.history.find_workstream_by_target(pending["nlu_result"]["current_turn"]["intent"], target)
            elif entities_products:
                target = entities_products[0]
                candidate_ws = self.history.find_workstream_by_target(pending["nlu_result"]["current_turn"]["intent"], target)

            if candidate_ws:
                self.history.resume_workstream(candidate_ws.id)
                self.history.clear_pending_decision()
                focused_ws = candidate_ws
            else:
                self.history.clear_pending_decision()
                focused_ws = None
        else:
            focused_ws = self.history.get_focused_ws()

        # Create or select focused workstream
        if not focused_ws:
            new_ws_list = work_decision.get("new_workstreams", []) if work_decision else []
            if new_ws_list:
                first = new_ws_list[0]
                seed = {}
                target = first.get("target") or {}
                if target:
                    seed["category"] = target.get("category")
                    seed["subcategory"] = target.get("subcategory")
                focused_ws = self.history.ensure_workstream(first.get("type", intent), seed_entities=seed)
                for extra in new_ws_list[1:]:
                    ew = self.history.ensure_workstream(extra.get("type", intent), seed_entities=extra.get("target", {}))
                    self.history.pause_workstream(ew.id)
            else:
                focused_ws = self.history.ensure_workstream(intent, seed_entities={})

        else:
            # if focused exists but user references a paused ws, resume that one
            referenced = nlu_result["current_turn"].get("referenced_entities", []) or []
            if referenced:
                target = referenced[0]
                candidate_ws = self.history.find_workstream_by_target(focused_ws.type, target)
                if candidate_ws and getattr(candidate_ws, "status") == "paused":
                    self.history.resume_workstream(candidate_ws.id)
                    focused_ws = candidate_ws

        logger.info(f"Focused workstream type: {getattr(focused_ws, 'type', None)}")
        # Route to agent
        agent = self.agents.get(focused_ws.type)
        if not agent:
            action = Info(f"Sorry, I can’t handle {focused_ws.type} yet.")
            self.history.append_action(action)
            return action

        agent_ctx = AgentContext(workstream=focused_ws, session=self.history.session_snapshot(), nlu_result=nlu_result)
        output: AgentOutput = await agent.decide_next(agent_ctx)

        # Apply updates from agent output
        if output.updated_slots:
            focused_ws.slots.update(output.updated_slots)

        # If agent returns presented_items, store them and mark workstream as presenting.
        if getattr(output, "presented_items", None) is not None:
            focused_ws.candidates = output.presented_items or []
            # set status to presenting unless already completed
            if getattr(focused_ws, "status", "") != "completed":
                focused_ws.status = "presenting"

        if getattr(output, "mark_completed", False):
            focused_ws.status = "completed"

        # If agent asked the user (Ask action), register a pending ask for this workstream.
        if isinstance(output.action, Ask):
            # try to obtain a slot name from Ask (slot or slot_name). If not present, use None.
            ask_slot = getattr(output.action, "slot", None) or getattr(output.action, "slot_name", None)
            ask_prompt = getattr(output.action, "text", None) or getattr(output.action, "prompt", None) or str(output.action)
            self.history.set_pending_ask(focused_ws.id, ask_slot, ask_prompt)

        self.history.append_action(output.action)

        # Goal check (unchanged)
        goal = GOALS.get((focused_ws.type, None))
        if goal and has_all(focused_ws.slots, set(goal["mandatory"])) and goal["is_done"](focused_ws):
            focused_ws.status = "completed"
            logger.info(f"GOAL reached for {focused_ws.type}")

        return output.action
