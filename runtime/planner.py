from __future__ import annotations
from typing import Dict, Optional
from config.planner_config import PlannerConfig, INTENT_THRESHOLDS
from core.nlu import EnhancedNLU
from core.conversation_history import ConversationHistory
from agents.base import AgentBase, Action, Ask, Info, AgentOutput, AgentContext
from agents.discovery import DiscoveryAgent
from agents.order import OrderAgent
from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.logging_setup import configure_logging
from core.goals import GOALS, has_all   # 👈 import goal registry

logger = configure_logging("planner")

class Planner:
    def __init__(self,
                 nlu: Optional[EnhancedNLU] = None,
                 tools: Optional[ToolRegistry] = None,
                 llm_client: Optional[LLMClient] = None,
                 config: PlannerConfig = PlannerConfig()):
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
        # ---- Step 1. Run NLU ----
        convo_ctx = self.history.as_nlu_context()
        nlu_result = await self.nlu.analyze_message(user_message, conversation_context=convo_ctx)
        self.history.append_user_turn(user_message, nlu_result)

        intent = nlu_result["current_turn"]["intent"]
        sub_intent = nlu_result["current_turn"].get("sub_intent")
        confidence = nlu_result["current_turn"]["confidence"]
        continuity = nlu_result["continuity"]
        entities = nlu_result["current_turn"]["entities"]
        suggested = continuity.get("suggested_clarification") if isinstance(continuity, dict) else None

        logger.info(f"NLU intent={intent} sub_intent={sub_intent} conf={confidence:.2f} entities={entities}")

        # ---- Step 2. Confidence gate ----
        if confidence < INTENT_THRESHOLDS.get(intent, 0.5):
            question = suggested or "Could you clarify what you’d like to do?"
            action = Ask(question=question, slot=None)
            self.history.append_action(action)
            logger.info(f"Confidence low. Asking: {question}")
            return action

        # ---- Step 3. Apply continuity & get focused workstream ----
        self.history.apply_continuity(intent=intent, entities=entities, continuity=continuity)
        focused_ws = self.history.get_focused_ws()
        if not focused_ws:
            focused_ws = self.history.ensure_workstream(intent, seed_entities=entities)

        # ---- Step 4. Route to agent ----
        agent = self.agents.get(focused_ws.type)
        if not agent:
            action = Info(message=f"Sorry, I can’t handle {focused_ws.type} yet.")
            self.history.append_action(action)
            logger.warning(action.message)
            return action

        agent_ctx = AgentContext(workstream=focused_ws,
                                 session=self.history.session_snapshot(),
                                 nlu_result=nlu_result)

        output: AgentOutput = await agent.decide_next(agent_ctx)

        # ---- Step 5. Persist agent output ----
        self.history.apply_agent_output(output)
        self.history.append_action(output.action)
        logger.info(f"Action emitted: {output.action}")

        # ---- Step 6. GOAL CHECK (NEW) ----
        goal = GOALS.get((focused_ws.type, sub_intent)) or GOALS.get((focused_ws.type, None))
        if goal:
            have_mandatories = has_all(focused_ws.slots, set(goal["mandatory"]))
            done = goal["is_done"](focused_ws)
            if have_mandatories and done and focused_ws.status != "completed":
                focused_ws.status = "completed"
                logger.info(f"GOAL reached for {focused_ws.type}/{sub_intent or 'default'} "
                            f"(slots={focused_ws.slots})")

        # ---- Step 7. Return action ----
        return output.action
