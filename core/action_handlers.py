# core/action_handlers.py
"""
Action handlers for different planner decisions.
Handles execution of various planner actions like goal achievement, re-planning, etc.
"""

from typing import Dict, Any
from datetime import datetime

from .models import PlannerDecision, PlannerStatus


class ActionHandlers:
    """Handles execution of different planner actions."""

    def __init__(self, context_manager, session_manager):
        self.context_manager = context_manager
        self.session_manager = session_manager

    def handle_goal_achieved(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle goal achievement scenario with comprehensive completion logic."""
        self.session_manager.status = PlannerStatus.GOAL_ACHIEVED

        if self.session_manager.current_goal:
            self.session_manager.current_goal.status = "completed"
            self.session_manager.current_goal.progress_score = 1.0
            self.session_manager.current_goal.updated_at = datetime.now().isoformat()

        # Create a satisfying completion message based on goal type and context
        if self.session_manager.current_goal:
            if self.session_manager.current_goal.category == "discovery":
                completion_message = (
                    decision.user_message or
                    "Excellent! I've found some great options that match your requirements perfectly. "
                    "I'm confident these recommendations will meet your needs. Is there anything else I can help you with today?"
                )
            elif self.session_manager.current_goal.category == "order":
                completion_message = (
                    decision.user_message or
                    "Great! I've provided you with complete information about your order. "
                    "Everything looks good and you're all set. Is there anything else I can help you with?"
                )
            elif self.session_manager.current_goal.category == "return":
                completion_message = (
                    decision.user_message or
                    "Perfect! I've set up your return process and you have everything you need. "
                    "The return is all arranged. Is there anything else I can assist you with today?"
                )
            else:
                completion_message = (
                    decision.user_message or
                    "Wonderful! I've successfully helped you accomplish what you needed. "
                    "I'm glad I could assist you today. Is there anything else I can help you with?"
                )
        else:
            completion_message = decision.user_message or "Great! I've successfully helped you accomplish your goal. Is there anything else you'd like to do?"

        self.context_manager.add_message("system", completion_message)

        return {
            "response": completion_message,
            "status": "goal_achieved",
            "action": "session_complete",
            "goal": self.session_manager.current_goal.description if self.session_manager.current_goal else None,
            "goal_category": self.session_manager.current_goal.category if self.session_manager.current_goal else None,
            "session_complete": True,
            "business_outcome": "successful_completion",
            "satisfaction_level": "high" if self.session_manager.satisfaction_signals_detected > 0 else "good"
        }

    def handle_re_planning(self, decision: PlannerDecision, spec_handler) -> Dict[str, Any]:
        """Handle re-planning scenario with user explanation and goal transition."""
        self.session_manager.status = PlannerStatus.RE_PLANNING

        # Create explanation message that acknowledges the change
        explanation = decision.user_message or (
            "I understand you'd like to focus on something different now. "
            f"That's perfectly fine! Let me help you with this new request. {decision.reasoning}"
        )

        self.context_manager.add_message("system", explanation)

        # Reset specification state for new planning
        spec_handler.reset_specifications()

        # Handle goal transition
        if self.session_manager.current_goal:
            self.session_manager.current_goal.status = "replanning"
            self.session_manager.current_goal.updated_at = datetime.now().isoformat()

        self.session_manager.status = PlannerStatus.READY

        return {
            "response": explanation,
            "status": "re_planning",
            "action": "re_plan",
            "reasoning": decision.reasoning,
            "new_goal_direction": decision.goal_description,
            "goal_transition": "acknowledged_and_adapting"
        }

    def handle_clarification(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle clarification request with helpful, business-focused messaging."""
        clarification_message = decision.user_message or (
            "I want to make sure I give you exactly what you need. "
            "Could you provide a bit more detail about what you're looking for? "
            "The more specific you can be, the better I can help you."
        )

        self.context_manager.add_message("system", clarification_message)

        return {
            "response": clarification_message,
            "status": "clarification_needed",
            "action": "clarify",
            "reasoning": decision.reasoning,
            "goal_status": decision.goal_status,
            "business_intent": "ensuring_accurate_assistance"
        }

    def handle_unknown_action(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle unknown action type with business-appropriate messaging."""
        fallback_message = "I want to make sure I help you in the best way possible. Could you help me understand what you'd like to accomplish?"
        self.context_manager.add_message("system", fallback_message)

        return {
            "response": fallback_message,
            "status": "unknown_action",
            "action": "clarify",
            "original_decision": decision.action,
            "business_recovery": "attempting_clarification"
        }

    def handle_error(self, error_message: str, context: str, spec_handler) -> Dict[str, Any]:
        """Handle errors gracefully with customer service focus."""
        self.session_manager.status = PlannerStatus.ERROR

        user_message = "I apologize for the brief delay. Let me make sure I give you the best possible assistance. How can I help you today?"
        self.context_manager.add_message("system", user_message)
        self.context_manager.add_fact("last_error", error_message, "system")

        # Reset to ready state for recovery
        self.session_manager.status = PlannerStatus.READY
        spec_handler.reset_specifications()

        return {
            "response": user_message,
            "status": "error_recovered",
            "action": "retry",
            "error_context": context,
            "business_response": "graceful_error_recovery"
        }