from core.nlu import EnhancedNLU
from core.conversation_history import ConversationHistory
from agents.base import Ask, Info, AgentContext
from agents.discovery import DiscoveryAgent
from agents.order import OrderAgent
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from config.planner_config import PlannerConfig, INTENT_THRESHOLDS
from core.goals import GOALS, has_all


class Planner:
    def __init__(self, nlu=None, tools=None, llm_client=None, config=PlannerConfig()):
        self.nlu = nlu or EnhancedNLU()
        self.tools = tools or ToolRegistry()
        self.llm = llm_client or LLMClient()
        self.cfg = config
        self.history = ConversationHistory()
        self.agents = {
            "DISCOVERY": DiscoveryAgent(self.tools, self.llm, self.cfg),
            "ORDER": OrderAgent(self.tools, self.llm, self.cfg)
        }

    async def handle_user_turn(self, user_message: str):
        nlu_result = await self.nlu.analyze_message(user_message, self.history.as_nlu_context())
        self.history.append_user_turn(user_message, nlu_result)

        intent = nlu_result["current_turn"]["intent"]
        conf = nlu_result["current_turn"]["confidence"]
        cont = nlu_result["continuity"]
        entities = nlu_result["current_turn"]["entities"]

        if conf < INTENT_THRESHOLDS.get(intent, 0.5):
            a = Ask("Could you clarify?")
            self.history.append_action(a)
            return a

        self.history.apply_continuity(intent, entities, cont)
        ws = self.history.get_focused_ws() or self.history.ensure_workstream(intent, entities)
        agent = self.agents.get(ws.type)
        if not agent:
            a = Info(f"Sorry, I can’t handle {ws.type}")
            self.history.append_action(a)
            return a

        agent_ctx = AgentContext(workstream=ws, session=self.history.session_snapshot(), nlu_result=nlu_result)
        out = await agent.decide_next(agent_ctx)

        if out.updated_slots:
            ws.slots.update(out.updated_slots)
        if out.presented_items:
            ws.candidates = out.presented_items
        if out.mark_completed:
            ws.status = "completed"

        self.history.append_action(out.action)

        goal = GOALS.get((ws.type, None))
        if goal and has_all(ws.slots, goal["mandatory"]) and goal["is_done"](ws):
            ws.status = "completed"
        return out.action
