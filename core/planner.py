# planner.py
"""
Stateful Planner for the E-commerce Agent.

Responsibilities:
- Call NLU each turn with conversation context.
- Interpret continuity; manage focus/workstreams via ConversationHistory.
- Enforce one action per turn (ASK / TOOL / PRESENT / COMMIT / INFO / SWITCH_FOCUS).
- Route to the right agent (Discovery, Order, Return, Exchange, Payment, ChitChat).
- Honor mandatory-fields policy: In DISCOVERY, `category` & `subcategory` must be known before search.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from core.nlu import EnhancedNLU  # your existing NLU
from core.conversation_history import ConversationHistory
from agents.base import (
    AgentBase, Action, Ask, Info, AgentOutput, AgentContext
)

from agents.discovery import DiscoveryAgent
from agents.order import OrderAgent
from agents.return_agent import ReturnAgent
from agents.exchange import ExchangeAgent
from agents.payment import PaymentAgent

from tools.registry import ToolRegistry
from core.llm_client import LLMClient
from core.config import PlannerConfig, INTENT_THRESHOLDS

from dotenv import load_dotenv
load_dotenv()

# --- Planner configuration gates (mirror your NLU thresholds) ---
class Planner:
    """
    One planner to rule them all: a single top-level state machine
    that delegates to micro state machines (agents) per workstream.
    """

    def __init__(
        self,
        nlu: Optional[EnhancedNLU] = None,
        tools: Optional[ToolRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        config: PlannerConfig = PlannerConfig(),
    ):
        self.nlu = nlu or EnhancedNLU()
        self.tools = tools or ToolRegistry()
        self.llm = llm_client or LLMClient()
        self.cfg = config
        self.history = ConversationHistory()  # owns workstreams/focus

        # Single point where agents are registered
        self.agents: Dict[str, AgentBase] = {
            "DISCOVERY": DiscoveryAgent(self.tools, self.llm, self.cfg),
            "ORDER": OrderAgent(self.tools, self.llm, self.cfg),
            "RETURN": ReturnAgent(self.tools, self.llm, self.cfg),
            "EXCHANGE": ExchangeAgent(self.tools, self.llm, self.cfg),
            "PAYMENT": PaymentAgent(self.tools, self.llm, self.cfg),
            # ChitChat could be a trivial agent; here we fold chit-chat into INFO if needed
        }

    # ------------- Public API -------------
    def handle_user_turn(self, user_message: str) -> Action:
        """
        Main entry point per user turn:
        1) Run NLU with context
        2) Apply confidence/continuity gates to update focus/workstreams
        3) Delegate to the focused agent's micro-planner
        4) Emit ONE action and update state
        """
        # Build conversation context from history for NLU
        convo_ctx = self.history.as_nlu_context()

        nlu_result = self.nlu.analyze_message(user_message, conversation_context=convo_ctx)
        self.history.append_user_turn(user_message, nlu_result)

        intent = nlu_result["current_turn"]["intent"]
        confidence = nlu_result["current_turn"]["confidence"]
        continuity = nlu_result["continuity"]
        entities = nlu_result["current_turn"]["entities"]
        suggested = continuity.get("suggested_clarification")

        # 1) Confidence gate
        if confidence < INTENT_THRESHOLDS.get(intent, 0.5):
            # Ask one pointed clarification and stop
            question = suggested or "Could you clarify what you’d like to do?"
            action = Ask(question=question, slot=None)
            self.history.append_action(action)
            return action

        # 2) Update focus/workstreams per continuity
        self.history.apply_continuity(intent=intent, entities=entities, continuity=continuity)

        # 3) Route to focused agent
        focused_ws = self.history.get_focused_ws()
        if not focused_ws:
            # Should not happen; create a default workstream for the intent
            focused_ws = self.history.ensure_workstream(intent, seed_entities=entities)

        agent = self.agents.get(focused_ws.type)
        if not agent:
            action = Info(message=f"Sorry, I can’t handle {focused_ws.type} yet.")
            self.history.append_action(action)
            return action

        agent_ctx = AgentContext(
            workstream=focused_ws,
            session=self.history.session_snapshot(),
            nlu_result=nlu_result,
        )

        # 4) Decide → Act (single action)
        output: AgentOutput = agent.decide_next(agent_ctx)

        # 5) Update state from agent output
        self.history.apply_agent_output(output)

        # 6) Return the single action to the runtime/UI
        self.history.append_action(output.action)
        return output.action


# ----------------- Tiny demonstration -----------------
if __name__ == "__main__":
    # Minimal interactive demonstration (no external tools; stubs in tools.tools)
    planner = Planner()

    turns = [
        "Show me gaming laptops under $1500",
        "Compare it with HP laptops",
        "Actually, show me tablets instead",
        "Where is my order?",
    ]

    for t in turns:
        act = planner.handle_user_turn(t)
        print(f"USER: {t}")
        print(f"ACTION: {act}")
        print("-" * 60)
