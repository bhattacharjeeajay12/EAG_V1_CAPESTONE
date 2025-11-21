# planner_agent.py
from typing import Any, Dict, Optional, Union

from config.enums import Agents, WorkflowContinuityDecision as WfCDecision, WorkstreamState as WsState
from agents.discovery import DiscoveryAgent
from agents.payment import PaymentAgent
from agents.exchange import ExchangeAgent
from agents.return_agent import ReturnAgent
from nlu.planner_nlu import PlannerNLU
from core.conversation_history import ConversationHistory


class PlannerAgent:
    """
    PlannerAgent:
    1. Calls Planner NLU.
    2. Creates or identifies the focused workstream.
    3. Routes control to the appropriate phase agent.
    """

    def __init__(self, conv_history: ConversationHistory) -> None:
        self.discovery_agent = DiscoveryAgent()
        self.payment_agent = PaymentAgent()
        self.exchange_agent = ExchangeAgent()
        self.return_agent = ReturnAgent()
        self.planner_nlu = PlannerNLU()
        self.conversation_history: ConversationHistory = conv_history

    # -------------------------------------------------------------------------
    # Public entrypoint
    # -------------------------------------------------------------------------
    async def handle_user_turn(self, current_message: str) -> Any:
        """
        Main entrypoint.

        :param current_message: Raw user message for this turn.
        :return: Whatever the phase-specific agent returns.
        """

        # ------------------------ FIXED: missing await ------------------------
        try:
            planner_nlu_output = await self.planner_nlu.run(
                user_message=current_message,
                conversation_context=self.conversation_history
            )
        except Exception as e:
            raise Exception(f"Planner NLU execution failed: {e}")

        # ------------------------ FIXED: incorrect syntax ---------------------
        if planner_nlu_output is not None:
            phase: str = planner_nlu_output.get("phase", "UNKNOWN")
            decision: Dict[str, Any] = planner_nlu_output.get("decision", {}) or {}
            entities: Dict[str, Any] = planner_nlu_output.get("entities", {}) or {}
        else:
            raise Exception("Planner NLU returned None. Please inspect upstream logic.")

        # ---------------------------------------------------------------------
        # PHASE ROUTING — minimal, leaving full logic for you to fill later
        # ---------------------------------------------------------------------
        if phase == Agents.DISCOVERY:
            return await self.discovery_agent.handle(current_message, self.conversation_history, decision, entities)

        elif phase == Agents.PAYMENT:
            return await self.payment_agent.handle(current_message, self.conversation_history, decision, entities)

        elif phase == Agents.EXCHANGE:
            return await self.exchange_agent.handle(current_message, self.conversation_history, decision, entities)

        elif phase == Agents.RETURN:
            return await self.return_agent.handle(current_message, self.conversation_history, decision, entities)

        else:
            # Unknown or chitchat
            return "I'm here to help with shopping, orders, returns, or exchanges. Could you clarify your request?"

    async def handle_conversation_by_decision(self, sender: Union[Agents, str], llm_decision: Dict[str, Any]) -> None:
        """
            1. checks if new workstream is required to be created. if yes it creates a new workstream.
            2. Finds active workstreams and updates self.active_ws_id.
        """
        if sender == Agents.PLANNER:
            decision = llm_decision["decision"]
            new_ws, active_wf_continuity, focus_workstream_id   = decision["new_workstreams"], decision["active_workflow_continuity"], decision["focus_workstream_id"]
            if active_wf_continuity == WfCDecision.CONTINUATION:
                # should not do anything, simply pass. This if-block is optional. Keeping this if-block as a placeholder.
                pass
            if active_wf_continuity == WfCDecision.UNCLEAR:
                # todo : initiate an Ask message for gathering clarification from user
                pass
            if active_wf_continuity == WfCDecision.SWITCH:
                if new_ws:
                    # 1. create new ws
                    # 2. focus on the new one
                    if focus_workstream_id is not None:
                        # Whenever we update the active_ws_id of conversation_history, we need to update the pending and completed es list
                        self.conversation_history.active_ws_id = focus_workstream_id
                        self.conversation_history.pending_ws_ids = self.conversation_history.get_pending_ws_ids()
                    for ws in enumerate(new_ws):
                        new_ws = self.conversation_history.create_new_workstream(WsState.NEW, llm_decision["entities"])
        return