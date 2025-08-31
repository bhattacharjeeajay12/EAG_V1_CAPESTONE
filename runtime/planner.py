"""
Planner: Slim orchestrator that routes to agents and enforces mandatory slot policy.
"""
from typing import Dict, Optional
from config.planner_config import PlannerConfig, INTENT_THRESHOLDS
from runtime.planner_nlu import EnhancedNLU
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
    def __init__(self, nlu: Optional[EnhancedNLU] = None, tools: Optional[ToolRegistry] = None,
                 llm_client: Optional[LLMClient] = None, config: PlannerConfig = PlannerConfig()):
        self.nlu = nlu or EnhancedNLU()
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

        # todo: remove hardcoing
        # nlu_result = await self.nlu.analyze_message(user_message, conversation_context=convo_ctx)
        nlu_result = {'current_turn': {'intent': "DISCOVERY", 'confidence': 1.0}, "continuity": {'continuity_type': 'NEW'}}
        #===
        self.history.append_user_turn(user_message, nlu_result)

        intent = nlu_result["current_turn"]["intent"]
        confidence = nlu_result["current_turn"]["confidence"]

        if confidence < INTENT_THRESHOLDS.get(intent, 0.5):
            action = Ask("Could you clarify what you’d like to do?")
            self.history.append_action(action)
            return action

        focused_ws = self.history.get_focused_ws()
        if not focused_ws:
            focused_ws = self.history.ensure_workstream(intent, seed_entities={})

        agent = self.agents.get(focused_ws.type)
        if not agent:
            action = Info(f"Sorry, I can’t handle {focused_ws.type} yet.")
            self.history.append_action(action)
            return action

        agent_ctx = AgentContext(workstream=focused_ws, session=self.history.session_snapshot(), nlu_result=nlu_result)
        output: AgentOutput = await agent.decide_next(agent_ctx)

        if output.updated_slots:
            focused_ws.slots.update(output.updated_slots)
        if output.presented_items is not None:
            focused_ws.candidates = output.presented_items
        if output.mark_completed:
            focused_ws.status = "completed"

        self.history.append_action(output.action)

        goal = GOALS.get((focused_ws.type, None))
        if goal and has_all(focused_ws.slots, set(goal["mandatory"])) and goal["is_done"](focused_ws):
            focused_ws.status = "completed"
            logger.info(f"GOAL reached for {focused_ws.type}")

        return output.action
