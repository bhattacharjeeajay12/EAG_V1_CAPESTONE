# core/models.py
"""
Data models and enums for the intelligent planner.
Contains goal tracking, decision structures, and status definitions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class PlannerStatus(Enum):
    """Status of the intelligent planner."""
    READY = "ready"
    ANALYZING = "analyzing"
    GATHERING_SPECS = "gathering_specifications"
    CONFIRMING_REQUIREMENTS = "confirming_requirements"
    EXECUTING_AGENT = "executing_agent"
    GOAL_ACHIEVED = "goal_achieved"
    RE_PLANNING = "re_planning"
    ERROR = "error"


@dataclass
class ConversationGoal:
    """Represents the current conversation goal with measurable success criteria."""
    description: str
    category: str  # "discovery", "order", "return", "general"
    success_criteria: List[str] = field(default_factory=list)  # Specific measurable criteria
    business_objective: str = ""  # What business value this achieves
    user_satisfaction_indicators: List[str] = field(default_factory=list)  # Signs of user satisfaction
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"
    progress_score: float = 0.0  # 0.0 to 1.0 indicating progress toward completion

    def __post_init__(self):
        """Initialize timestamps and default criteria based on category."""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

        # Set default success criteria based on category
        if not self.success_criteria:
            self.success_criteria = self._get_default_success_criteria()
        if not self.business_objective:
            self.business_objective = self._get_default_business_objective()
        if not self.user_satisfaction_indicators:
            self.user_satisfaction_indicators = self._get_default_satisfaction_indicators()

    def _get_default_success_criteria(self) -> List[str]:
        """Get default success criteria based on goal category."""
        criteria_map = {
            "discovery": [
                "User receives relevant product recommendations",
                "Products match user's specified requirements",
                "User expresses satisfaction with options presented",
                "Budget and preferences are respected"
            ],
            "order": [
                "Order status information is provided",
                "User receives clear tracking information",
                "Any order issues are identified and addressed",
                "User understands next steps"
            ],
            "return": [
                "Return process is clearly explained",
                "User receives return authorization if needed",
                "Return timeline and method are communicated",
                "User confirms understanding of process"
            ],
            "general": [
                "User's question is answered accurately",
                "User receives helpful information",
                "User expresses satisfaction or understanding"
            ]
        }
        return criteria_map.get(self.category, criteria_map["general"])

    def _get_default_business_objective(self) -> str:
        """Get default business objective based on goal category."""
        objective_map = {
            "discovery": "Help customer find and purchase suitable products",
            "order": "Provide excellent post-purchase customer service",
            "return": "Handle returns efficiently while maintaining customer satisfaction",
            "general": "Provide helpful customer support and build brand loyalty"
        }
        return objective_map.get(self.category, objective_map["general"])

    def _get_default_satisfaction_indicators(self) -> List[str]:
        """Get default user satisfaction indicators based on goal category."""
        indicators_map = {
            "discovery": [
                "User shows interest in recommended products",
                "User asks follow-up questions about products",
                "User expresses thanks or satisfaction",
                "User indicates readiness to purchase"
            ],
            "order": [
                "User expresses understanding of order status",
                "User thanks for the information",
                "User indicates their concern is resolved"
            ],
            "return": [
                "User understands the return process",
                "User expresses satisfaction with the solution",
                "User confirms they have what they need"
            ],
            "general": [
                "User thanks for the help",
                "User indicates their question is answered",
                "User expresses satisfaction"
            ]
        }
        return indicators_map.get(self.category, indicators_map["general"])


@dataclass
class PlannerDecision:
    """Represents a comprehensive decision made by the planner LLM including goal evaluation."""
    # Core action decision
    action: str  # "gather_specs", "confirm_requirements", "call_agent", "goal_achieved", "re_plan", "clarify"
    agent_type: Optional[str] = None
    agent_params: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    user_message: Optional[str] = None
    confidence: float = 0.8
    specifications_needed: List[str] = None
    confirmation_summary: Optional[str] = None

    # Goal evaluation (combined in single LLM call)
    goal_status: str = "in_progress"  # "in_progress", "achieved", "needs_replanning", "blocked"
    goal_progress_score: float = 0.0  # 0.0 to 1.0
    goal_achievement_reasoning: str = ""
    success_criteria_met: List[str] = field(default_factory=list)  # Which criteria are satisfied
    satisfaction_indicators_present: List[str] = field(default_factory=list)  # Detected satisfaction signs
    next_steps_recommendation: Optional[str] = None

    # Goal management
    goal_description: Optional[str] = None
    goal_category: Optional[str] = None
    should_update_goal: bool = False