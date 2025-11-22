# planner_agent.py
from typing import Any, Dict, Optional, Union

from config.enums import Agents, WorkflowContinuityDecision as WfCDecision, WorkstreamState as WsState
from agents.DiscoveryAgent import DiscoveryAgent
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
        # self.discovery_agent = DiscoveryAgent
        # self.payment_agent = PaymentAgent
        # self.exchange_agent = ExchangeAgent
        # self.return_agent = ReturnAgent
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
        planner_llm_decision = await self.planner_nlu.run(user_message=current_message, conversation_context=self.conversation_history)
        if planner_llm_decision is None:
            raise Exception("Planner NLU returned None. Please inspect upstream logic.")
        await self.handle_workstreams(planner_llm_decision)
        active_ws = self.conversation_history.get_active_workstream()
        # ---------------------------------------------------------------------
        # PHASE ROUTING
        # ---------------------------------------------------------------------
        if active_ws.current_phase == Agents.DISCOVERY:
            if active_ws.target_entities.get("subcategory"):
                subcategory = planner_llm_decision["entities"]["subcategory"]
            else:
                pass

            self.discovery_agent = DiscoveryAgent(subcategory)
            specification =  await self.discovery_agent.run(current_message)


        elif phase == Agents.PAYMENT:
            output = await self.payment_agent.handle(current_message, self.conversation_history, decision, entities)

        elif phase == Agents.EXCHANGE:
            output = await self.exchange_agent.handle(current_message, self.conversation_history, decision, entities)

        elif phase == Agents.RETURN:
            output = await self.return_agent.handle(current_message, self.conversation_history, decision, entities)

        elif phase == Agents:
            # Unknown or chitchat
            return "I'm here to help with shopping, orders, returns, or exchanges. Could you clarify your request?"
        return output

    async def handle_workstreams(self, llm_decision: Dict[str, Any]) -> None:
        """
        Role:
            1. checks if new workstream is required to be created. if yes it creates a new workstream.
            2. Finds active workstreams and updates self.active_ws_id.
        param:
            1. llm_decision: Planner LLM decision containing workstream management info.
        """
        decision = llm_decision["decision"]
        new_ws_list, active_wf_continuity, focus_workstream_id   = decision["new_workstreams"], decision["active_workflow_continuity"], decision["focus_workstream_id"]
        if active_wf_continuity == WfCDecision.CONTINUATION:
            # should not do anything, simply pass. This if-block is optional. Keeping this if-block as a placeholder.
            pass
        if active_wf_continuity == WfCDecision.UNCLEAR:
            # todo : initiate an Ask message for gathering clarification from user
            pass
        if active_wf_continuity == WfCDecision.SWITCH:
            if new_ws_list:
                # 1. create new ws
                # 2. focus on the new one
                if focus_workstream_id is not None:
                    # Whenever we update the active_ws_id of conversation_history, we need to update the pending and completed es list
                    self.conversation_history.update_active_ws_id(focus_workstream_id)
                for idx, ws in enumerate(new_ws_list):
                    new_ws = self.conversation_history.create_new_workstream(WsState.NEW, llm_decision["entities"])
                    if focus_workstream_id is None and idx == 0:
                        # Make first new workstream created as the active one.
                        self.conversation_history.update_active_ws_id(new_ws.get_workstream_id(), is_completed=False)
                        self.conversation_history.active_ws_id = new_ws.id
        return