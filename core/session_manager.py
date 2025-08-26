# core/session_manager.py
"""
Session management and conversation lifecycle handling.
Manages session state, goal tracking, and conversation flow.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .models import PlannerStatus, ConversationGoal


class SessionManager:
    """Manages session state, goals, and conversation lifecycle."""

    def __init__(self, context_manager, session_id: str = None):
        self.context_manager = context_manager
        self.status = PlannerStatus.READY
        self.current_goal: Optional[ConversationGoal] = None
        self.conversation_turns = 0
        self.agent_calls_count = 0
        self.satisfaction_signals_detected = 0
        self.success_indicators_count = 0

    def start_conversation(self) -> Dict[str, Any]:
        """Start a new intelligent conversation with clear business context."""
        welcome_message = (
            "Hi! I'm your intelligent shopping assistant. My goal is to provide you with "
            "excellent service and help you accomplish exactly what you need. I can help you:\n\n"
            "🔍 **Discover and find products** - Get personalized recommendations that match your needs and budget\n"
            "📦 **Track your orders** - Get real-time updates and resolve any delivery concerns\n"
            "↩️ **Process returns and exchanges** - Handle returns quickly and fairly\n"
            "💡 **Get expert recommendations** - Receive tailored advice based on your preferences\n\n"
            "What would you like to accomplish today? I'll make sure we find the perfect solution for you."
        )

        self.context_manager.add_message("system", welcome_message)
        self.status = PlannerStatus.READY

        return {
            "response": welcome_message,
            "status": "ready",
            "session_id": self.context_manager.session_id,
            "goal": None,
            "business_context": "Customer service excellence and satisfaction"
        }

    def update_conversation_goal(self, description: str, category: str, status: str, progress_score: float = 0.0):
        """Update or create conversation goal with comprehensive tracking."""
        if self.current_goal and self.current_goal.description == description:
            # Update existing goal
            self.current_goal.status = status
            self.current_goal.progress_score = max(self.current_goal.progress_score, progress_score)
            self.current_goal.updated_at = datetime.now().isoformat()
        else:
            # Create new goal with enhanced initialization
            self.current_goal = ConversationGoal(
                description=description,
                category=category,
                status=status,
                progress_score=progress_score
            )

        # Store goal information in context manager for persistence
        self.context_manager.add_fact("current_goal", description, "planner")
        self.context_manager.add_fact("goal_category", category, "planner")
        self.context_manager.add_fact("goal_progress", str(progress_score), "planner")

    def track_satisfaction_signal(self):
        """Track a satisfaction signal detected in user message."""
        self.satisfaction_signals_detected += 1

    def increment_agent_calls(self):
        """Increment agent calls counter."""
        self.agent_calls_count += 1

    def increment_conversation_turns(self):
        """Increment conversation turns counter."""
        self.conversation_turns += 1

    def get_session_info(self, intent_tracker) -> Dict[str, Any]:
        """Get comprehensive session information with enhanced goal tracking."""
        current_intent = intent_tracker.get_current_intent()
        context_summary = self.context_manager.get_context_summary()

        goal_info = None
        if self.current_goal:
            goal_info = {
                "description": self.current_goal.description,
                "category": self.current_goal.category,
                "status": self.current_goal.status,
                "progress_score": self.current_goal.progress_score,
                "business_objective": self.current_goal.business_objective,
                "success_criteria": self.current_goal.success_criteria,
                "satisfaction_indicators": self.current_goal.user_satisfaction_indicators,
                "created_at": self.current_goal.created_at,
                "updated_at": self.current_goal.updated_at
            }

        return {
            "session_id": self.context_manager.session_id,
            "planner_status": self.status.value,
            "current_goal": goal_info,
            "current_intent": {
                "type": current_intent.intent_type if current_intent else None,
                "summary": current_intent.get_summary() if current_intent else None
            },
            "context_summary": context_summary,
            "conversation_turns": self.conversation_turns,
            "agent_calls_made": self.agent_calls_count,
            "conversation_quality": {
                "satisfaction_signals_detected": self.satisfaction_signals_detected,
                "success_indicators_count": self.success_indicators_count
            },
            "session_active": self.context_manager.session_active,
            "business_metrics": {
                "goal_completion_rate": self.current_goal.progress_score if self.current_goal else 0.0,
                "customer_engagement": "high" if self.satisfaction_signals_detected > 0 else "moderate"
            }
        }

    def end_conversation(self, reason: str = "user_exit") -> Dict[str, Any]:
        """End conversation gracefully with business outcome tracking."""
        closing_message = self.context_manager.end_session(reason)
        self.status = PlannerStatus.GOAL_ACHIEVED

        if self.current_goal and self.current_goal.status != "completed":
            self.current_goal.status = f"ended_{reason}"
            self.current_goal.updated_at = datetime.now().isoformat()

        # Determine business outcome
        business_outcome = "natural_completion"
        if self.current_goal and self.current_goal.progress_score >= 0.8:
            business_outcome = "successful_completion"
        elif reason == "user_exit" and self.current_goal and self.current_goal.progress_score < 0.5:
            business_outcome = "early_exit"

        return {
            "response": closing_message,
            "status": "conversation_ended",
            "reason": reason,
            "business_outcome": business_outcome,
            "session_summary": self.get_session_info(None),  # Will need intent_tracker if called
            "final_satisfaction_level": "high" if self.satisfaction_signals_detected > 1 else "moderate"
        }