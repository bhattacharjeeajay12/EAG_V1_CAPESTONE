from typing import Any, Dict, Optional

from agents.buy_agent import BuyAgent
from agents.recommend_agent import RecommendationAgent
from agents.order_agent import OrderAgent
from utils.logger import get_logger, log_decision
from utils.graph_viz import AgentGraph


class PlannerAgent:
    """
    Orchestrates agent calls based on user intent.

    Constraints enforced:
    - Recommendations are provided via the Buy agent delegating to RecommendationAgent
      when the user asks for a recommendation.
    - Orders are triggered through the Buy agent when a purchase is requested.
    """

    def __init__(self) -> None:
        self.logger = get_logger("planner")
        self.graph = AgentGraph(base_dir="memory")
        self.buy = BuyAgent()
        self.recommendation = RecommendationAgent()
        self.order = OrderAgent()
        self.session_label: Optional[str] = None

    def new_session(self, label: Optional[str] = None) -> None:
        self.session_label = label or "session"
        self.buy.new_session(label=self.session_label)
        self.recommendation.new_session(label=self.session_label)
        self.order.new_session(label=self.session_label)
        # Use BuyAgent session_id for graph naming convenience
        self.session_id = self.buy.memory.session_id
        log_decision(self.logger, agent="planner", event="new_session", why="initialize all agents", data={"label": self.session_label}, session_id=self.session_id)

    def _needs_recommendation(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ["recommend", "suggest", "recommendation", "options", "find"])

    def _is_purchase_intent(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ["buy", "purchase", "order", "checkout", "place order"])

    def handle(self, query: str) -> Dict[str, Any]:
        """Plan and execute based on the query."""
        if not getattr(self.buy.memory, "session_id", None):
            # Lazy initialize a session if not started
            self.new_session(label=self.session_label)

        if self._needs_recommendation(query):
            # Buy agent delegates to RecommendationAgent
            log_decision(self.logger, agent="buy", event="call_agent", why="user asked for recommendations", data={"callee": "recommendation"}, session_id=self.session_id)
            self.graph.add_interaction("buy", "recommendation", why="recommendation request")
            rec_result = self.buy.delegate_recommendation(self.recommendation, query)
            self.graph.save(self.session_id)
            return {"agent": "recommendation", "result": rec_result}

        # Otherwise, start with Buy agent to capture details
        log_decision(self.logger, agent="planner", event="route", why="default to buy agent for detail extraction", data={"callee": "buy"}, session_id=self.session_id)
        self.graph.add_interaction("planner", "buy", why="detail extraction")
        buy_result = self.buy.handle(query)

        # If the query indicates purchase, trigger the Order agent via the Buy agent context
        if self._is_purchase_intent(query):
            order_payload: Dict[str, Any] = {
                "product_id": buy_result.product_name if hasattr(buy_result, "product_name") else None,
                "product_name": getattr(buy_result, "product_name", None),
                "quantity": getattr(buy_result, "quantity", 1),
            }
            log_decision(self.logger, agent="buy", event="call_agent", why="user requested purchase", data={"callee": "order", "payload": order_payload}, session_id=self.session_id)
            self.graph.add_interaction("buy", "order", why="purchase request")
            order_result = self.buy.place_order(self.order, order_payload)
            self.graph.save(self.session_id)
            return {"agent": "order", "result": order_result}

        # No further action needed
        self.graph.save(self.session_id)
        return {"agent": "buy", "result": buy_result.model_dump() if hasattr(buy_result, "model_dump") else str(buy_result)}
