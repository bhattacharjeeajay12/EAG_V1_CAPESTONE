# runtime/planner.py (updated to consume slim planner JSON)
from typing import Dict, Optional, Any
from config.planner_config import PlannerConfig, INTENT_THRESHOLDS
from nlu.planner import PlannerNLU
from core.conversation_history import ConversationHistory
from agents.base import AgentBase, Action, Ask, Info, AgentOutput, AgentContext
from agents.discovery import DiscoveryAgent
from agents.order import OrderAgent
from agents.payment import PaymentAgent
from agents.return_agent import ReturnAgent
from agents.exchange import ExchangeAgent
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.logging_setup import configure_logging
from core.goals import GOALS, has_all
from core.states import DiscoveryState, OrderState

logger = configure_logging("planner")


def _to_enum_status(ws_type: str, upper_name: str):
    try:
        if ws_type == "DISCOVERY":
            return DiscoveryState[upper_name]
        if ws_type == "ORDER":
            return OrderState[upper_name]
    except Exception:
        pass
    return upper_name


class Planner:
    def __init__(self,
                 nlu: Optional[PlannerNLU] = None,
                 tools: Optional[ToolRegistry] = None,
                 llm_client: Optional[LLMClient] = None,
                 config: PlannerConfig = PlannerConfig()):
        self.nlu = nlu or PlannerNLU()
        self.tools = tools or ToolRegistry()
        self.llm = llm_client or LLMClient()
        self.cfg = config
        self.history = ConversationHistory()
        self.agents: Dict[str, AgentBase] = {
            "DISCOVERY": DiscoveryAgent(self.tools, self.llm, self.cfg),
            "ORDER": OrderAgent(self.tools, self.llm, self.cfg),
            # "PAYMENT": PaymentAgent(self.tools),
            # "RETURN": ReturnAgent(self.tools),
            # "EXCHANGE": ExchangeAgent(self.tools),
        }

    async def handle_user_turn(self, user_message: str) -> Action:
        convo_ctx = self.history.as_nlu_context()
        nlu = await self._analyze_and_record(user_message, convo_ctx)

        """
        👉 early = self._check_confidence(nlu)
        It checks if the LLM is confident enough about the detected intent.If confidence is too low, Planner doesn’t continue the pipeline.
        Instead, it immediately returns an Ask action: “Could you clarify what you’d like to do?” So its purpose = stop early and ask the user again if intent detection is uncertain.
        """
        early = self._check_confidence(nlu)
        if early is not None:
            return self._finalize_and_return(early)

        """
        👉 self._consume_pending_ask_if_any(user_message, nlu) 
        checks if the system had earlier asked the user a question (a pending Ask). If yes, it uses the current reply (from nlu.entities or raw text) to fill that missing slot in the workstream.
        Then it clears the pending ask so the workflow can continue.
        So: its job is to take the user’s answer to a previous question and store it in the right place.
        """
        self._consume_pending_ask_if_any(user_message, nlu)

        """
        focused_ws = self._resolve_continuity_and_focus(nlu)
        👉 decides which workflow the user’s message belongs to right now. If the message continues the current workflow → keep focus there.
        If it looks like a switch or unclear → store a pending decision and ask the user to clarify. If a previous pending decision exists → try to match the new entities/references to the right workflow and resume it.
        """
        focused_ws = self._resolve_continuity_and_focus(nlu)

        """
        👉 makes sure that some workflow is active after continuity is resolved. 
        If no workflow is focused yet → Create a new one from decision. new_workstreams (or from intent).
        Pause any extra workflows if multiple are created.
        If there is a focused workflow, but the user referred to another (via referenced_entities) → Resume that referenced workflow if it was paused.
        So: its job is to guarantee that the planner always has the right workflow in focus, either by creating or resuming one.
        """
        focused_ws = self._ensure_focus(
            intent=nlu["intent"],
            decision=nlu.get("decision"),
            nlu_result=nlu,
            focused_ws=focused_ws
        )

        logger.info(f"Focused workstream type: {getattr(focused_ws, 'type', None)}")

        """
        👉 self._route_and_decide(focused_ws, nlu) 
        Look at the focused workflow’s type (e.g., DISCOVERY, ORDER, RETURN). Pick the matching agent (DiscoveryAgent, OrderAgent, etc.). Give it the current workflow + NLU result.
        Let the agent decide the next action (ask for more info, present items, confirm an order, etc.).
        """
        output = await self._route_and_decide(focused_ws, nlu)

        """
        👉 self._apply_agent_output(focused_ws, output) 
        takes whatever the agent decided and applies it to the workflow + history. Updates workflow slots with any new info. Saves candidates if items were presented. 
        Changes workflow status (e.g., PRESENTING, COMPLETED). Records any Ask so the next user reply can fill it. Adds the action to the conversation history.
        So: its job is to update the workflow’s state and history based on the agent’s output.
        """
        self._apply_agent_output(focused_ws, output)

        """
        👉 self._check_and_mark_goal_completion(focused_ws) 
        looks at the current workflow and checks: “Have all the required pieces of information been collected?”, 
        “Does this workflow now meet the goal (e.g., Discovery finished, Order placed)?”. If yes → it marks the workflow’s status as COMPLETED. 
        So: its job is to decide if the workflow is finished and mark it done.
        """
        self._check_and_mark_goal_completion(focused_ws)

        """
        👉 self._finalize_and_return(output.action) 
        just wraps things up at the end of the turn and gives back the final action (Ask, Present, Info, Confirm, etc.) to the caller/UI.
        So: its job is to return the agent’s chosen action as the Planner’s final response for this user turn.
        """
        return self._finalize_and_return(output.action)

    async def _analyze_and_record(self, user_message: str, conversation_context: Any) -> Dict[str, Any]:
        nlu_result = await self.nlu.analyze_message(user_message, conversation_context=conversation_context)
        self.history.append_user_turn(user_message, nlu_result)
        return nlu_result

    def _check_confidence(self, nlu: Dict[str, Any]) -> Optional[Action]:
        intent = nlu.get("intent")
        conf = nlu.get("intent_confidence", 0.0)
        if not intent or conf < INTENT_THRESHOLDS.get(intent, 0.5):
            action = Ask(question="Could you clarify what you’d like to do?", slot=None)
            self.history.append_action(action)
            return action
        return None

    def _find_ws_by_target(self, intent: str, target: dict):
        for ws in self.history.workstreams.values():
            if ws.type != intent:
                continue
            if target.get("order_id") and ws.slots.get("order_id") == target["order_id"]:
                return ws
            if target.get("subcategory") and ws.slots.get("subcategory") == target["subcategory"]:
                return ws
        return None

    def _consume_pending_ask_if_any(self, user_message: str, nlu: Dict[str, Any]) -> None:
        pending_pair = self.history.find_any_pending_ask()
        if not pending_pair:
            return
        pending_ws_id, ask_info = pending_pair
        slot_name = (ask_info or {}).get("slot")
        entities = nlu.get("entities", {})

        filled_value = None
        if slot_name == "subcategory":
            filled_value = entities.get("subcategory") or user_message
        elif slot_name == "order_id":
            filled_value = entities.get("order_id") or user_message
        else:
            filled_value = user_message

        ws = self.history.workstreams.get(pending_ws_id)
        if ws is not None:
            ws.slots[slot_name or "last_answer"] = filled_value
            try:
                ws.status = _to_enum_status(ws.type, "COLLECTING")
            except Exception:
                pass
            self.history.set_focus(ws.id)
        self.history.clear_pending_ask(pending_ws_id)

    def _resolve_continuity_and_focus(self, nlu: Dict[str, Any]):
        ctype = nlu.get("continuity")
        clarify = nlu.get("clarify")

        if ctype in ("SWITCH", "UNCLEAR"):
            self.history.set_pending_decision({"nlu_result": nlu})
            action = Ask(question=(clarify or "Can you confirm how you'd like to proceed?"), slot=None)
            self.history.append_action(action)
            return None

        pending = self.history.get_pending_decision()
        if pending:
            refs = nlu.get("referenced_entities") or []
            candidate_ws = None
            if refs:
                target = refs[0]
                candidate_ws = self._find_ws_by_target(pending["nlu_result"]["intent"], target)
            else:
                ent = nlu.get("entities") or {}
                target = {"subcategory": ent.get("subcategory"), "order_id": ent.get("order_id")}
                candidate_ws = self._find_ws_by_target(pending["nlu_result"]["intent"], target)

            if candidate_ws:
                self.history.resume_workstream(candidate_ws.id)
                self.history.clear_pending_decision()
                return candidate_ws

            self.history.clear_pending_decision()
            return None

        return self.history.get_focused_ws()

    def _ensure_focus(self, intent: str, decision: Optional[Dict[str, Any]], nlu_result: Dict[str, Any], focused_ws):
        if not focused_ws:
            # Create new workstreams if decision provides multiple
            new_list = (decision or {}).get("new_workstreams", [])
            if new_list:
                first = new_list[0]
                target = first.get("target") or {}
                seed = {}
                if target.get("subcategory"):
                    seed["subcategory"] = target["subcategory"]
                if target.get("order_id"):
                    seed["order_id"] = target["order_id"]

                focused_ws = self.history.ensure_workstream(first.get("type", intent), seed_entities=seed)

                # Pause or create extra workstreams
                for extra in new_list[1:]:
                    ew = self.history.ensure_workstream(extra.get("type", intent),
                                                        seed_entities=extra.get("target", {}))
                    self.history.pause_workstream(ew.id)
            else:
                focused_ws = self.history.ensure_workstream(intent, seed_entities={})
        else:
            # Resume from referenced_entities if pointing to paused WS
            refs = nlu_result.get("referenced_entities") or []
            if refs:
                candidate_ws = self._find_ws_by_target(intent, refs[0])
                if candidate_ws and getattr(candidate_ws, "status", None) == "paused":
                    self.history.resume_workstream(candidate_ws.id)
                    focused_ws = candidate_ws

        return focused_ws

    async def slot_check(self, focused_ws, nlu: Dict[str, Any]) -> Optional[AgentOutput]:
        return
    async def _route_and_decide(self, focused_ws, nlu: Dict[str, Any]) -> AgentOutput:
        ws_type = getattr(focused_ws, "type", None)
        ws_key = ws_type.upper() if isinstance(ws_type, str) else ws_type
        agent = self.agents.get(ws_key)
        if not agent:
            info = Info(message=f"Sorry, I can’t handle {ws_key} yet.")
            self.history.append_action(info)
            return AgentOutput(action=info)
        agent_ctx = AgentContext(workstream=focused_ws, session=self.history.session_snapshot(), nlu_result=nlu)

        # call agent NLU
        # then call decide_next
        return await agent.decide_next(agent_ctx)

    def _apply_agent_output(self, focused_ws, output: AgentOutput) -> None:
        if output.updated_slots:
            focused_ws.slots.update(output.updated_slots)

        presented = getattr(output, "presented_items", None) or getattr(output.action, "items", None)
        if presented is not None:
            focused_ws.candidates = presented or []
            if getattr(focused_ws, "status", None) not in (DiscoveryState.COMPLETED, OrderState.COMPLETED, "completed"):
                try:
                    focused_ws.status = _to_enum_status(focused_ws.type, "PRESENTING")
                except Exception:
                    pass

        if getattr(output, "mark_completed", False):
            try:
                focused_ws.status = _to_enum_status(focused_ws.type, "COMPLETED")
            except Exception:
                focused_ws.status = "completed"

        from agents.base import Ask
        if isinstance(output.action, Ask):
            ask_slot = getattr(output.action, "slot", None)
            ask_prompt = getattr(output.action, "question", None) or repr(output.action)
            self.history.set_pending_ask(focused_ws.id, ask_slot, ask_prompt)

        self.history.append_action(output.action)

    def _check_and_mark_goal_completion(self, focused_ws) -> None:
        goal = GOALS.get((focused_ws.type, None))
        if goal and has_all(focused_ws.slots, set(goal.get("mandatory", []))) and goal["is_done"](focused_ws):
            try:
                focused_ws.status = _to_enum_status(focused_ws.type, "COMPLETED")
            except Exception:
                focused_ws.status = "completed"

    def _finalize_and_return(self, action: Action) -> Action:
        return action
