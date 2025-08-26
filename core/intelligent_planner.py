# core/intelligent_planner.py
"""
Intelligent Planner - LLM-Driven Goal-Oriented Conversational AI

A streamlined conversational orchestrator that coordinates between:
- NLU analysis and intent tracking
- LLM-driven decision making with goal evaluation
- Specification gathering and confirmation
- Agent execution and goal achievement validation

Architecture: Composition-based with specialized handlers for different concerns.
"""

from typing import Dict, Any
from datetime import datetime

from core.enhanced_nlu import EnhancedNLU
from core.intent_tracker import IntentTracker
from core.context_manager import ContextManager
from core.llm_client import LLMClient
from core.mock_agents import MockAgentManager

from .models import PlannerStatus, PlannerDecision
from .specification_handler import SpecificationHandler
from .decision_engine import DecisionEngine
from .session_manager import SessionManager
from .action_handlers import ActionHandlers


class IntelligentPlanner:
    """
    Streamlined intelligent conversation planner focused on orchestration.
    Uses composition pattern with specialized handlers for different concerns.
    """

    def __init__(self, session_id: str = None):
        """Initialize the Intelligent Planner with modular components."""
        # Core services
        self.enhanced_nlu = EnhancedNLU()
        self.intent_tracker = IntentTracker()
        self.context_manager = ContextManager(session_id)
        self.llm_client = LLMClient()
        self.mock_agents = MockAgentManager()

        # Specialized handlers
        self.session_manager = SessionManager(self.context_manager, session_id)
        self.spec_handler = SpecificationHandler()
        self.decision_engine = DecisionEngine(self.llm_client, self.context_manager, self.intent_tracker)
        self.action_handlers = ActionHandlers(self.context_manager, self.session_manager)

    @property
    def status(self):
        """Get current planner status."""
        return self.session_manager.status

    def start_conversation(self) -> Dict[str, Any]:
        """Start a new intelligent conversation."""
        return self.session_manager.start_conversation()

    def process_user_message(self, user_message: str) -> Dict[str, Any]:
        """
        Main processing pipeline with specification gathering, confirmation, and goal evaluation.

        Args:
            user_message: User's input message

        Returns:
            Complete response with actions taken and goal evaluation
        """
        try:
            # Add user message to context and update counters
            self.context_manager.add_message("user", user_message)
            self.session_manager.increment_conversation_turns()

            # Route based on current state
            if self.status == PlannerStatus.GATHERING_SPECS:
                return self._handle_specification_gathering(user_message)
            elif self.status == PlannerStatus.CONFIRMING_REQUIREMENTS:
                return self._handle_requirement_confirmation(user_message)
            else:
                return self._process_new_user_input(user_message)

        except Exception as e:
            return self.action_handlers.handle_error(f"Processing error: {str(e)}", user_message, self.spec_handler)

    def _process_new_user_input(self, user_message: str) -> Dict[str, Any]:
        """Process new user input through analysis and decision pipeline."""
        # Step 1: NLU Analysis with satisfaction tracking
        nlu_result = self._analyze_with_nlu(user_message)

        # Step 2: Intent tracking
        intent_result = self._analyze_intent_continuity(nlu_result)

        # Step 3: LLM decision making with goal evaluation
        self.session_manager.status = PlannerStatus.ANALYZING
        planner_decision = self.decision_engine.make_comprehensive_planning_decision(
            user_message, nlu_result, intent_result, self.session_manager.current_goal
        )

        # Step 4: Execute decision
        return self._execute_planner_decision(planner_decision)

    def _execute_planner_decision(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute the decision made by the planner LLM."""
        # Update goal progress if applicable (never decrease)
        if self.session_manager.current_goal and decision.goal_progress_score > 0:
            # Ensure progress never goes backwards
            new_progress = max(
                decision.goal_progress_score,
                self.session_manager.current_goal.progress_score
            )
            self.session_manager.current_goal.progress_score = new_progress
            self.session_manager.current_goal.updated_at = datetime.now().isoformat()

        # Update goal based on LLM evaluation
        if decision.should_update_goal and decision.goal_description:
            self.session_manager.update_conversation_goal(
                decision.goal_description,
                decision.goal_category or "general",
                decision.goal_status,
                max(decision.goal_progress_score,
                    self.session_manager.current_goal.progress_score if self.session_manager.current_goal else 0)
            )

        # Route to appropriate handler
        action_map = {
            "gather_specs": self._start_specification_gathering,
            "confirm_requirements": self._request_requirement_confirmation,
            "call_agent": self._execute_agent_call,
            "goal_achieved": self.action_handlers.handle_goal_achieved,
            "re_plan": lambda d: self.action_handlers.handle_re_planning(d, self.spec_handler),
            "clarify": self.action_handlers.handle_clarification
        }

        handler = action_map.get(decision.action, self.action_handlers.handle_unknown_action)
        return handler(decision)

    def _execute_agent_call(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute agent call with goal achievement evaluation."""
        self.session_manager.status = PlannerStatus.EXECUTING_AGENT

        try:
            # Call agent and process results
            agent_result = self.mock_agents.call_agent(
                decision.agent_type, decision.agent_params, self.context_manager.get_context_summary()
            )

            self.context_manager.store_agent_result(decision.agent_type, agent_result)
            self.session_manager.increment_agent_calls()

            if agent_result.get("user_message"):
                self.context_manager.add_message("system", agent_result["user_message"])

            # Evaluate goal BEFORE any state changes
            goal_evaluation = self.decision_engine.evaluate_post_agent_goal_status(
                agent_result, decision, self.session_manager.current_goal
            )

            # IMMEDIATELY update session manager's current goal with evaluation results
            if self.session_manager.current_goal:
                # Apply goal progress update immediately
                self.session_manager.current_goal.progress_score = goal_evaluation["progress_score"]

                if goal_evaluation["achieved"]:
                    self.session_manager.current_goal.status = "completed"
                    self.session_manager.current_goal.progress_score = 1.0
                else:
                    self.session_manager.current_goal.status = "in_progress"

                self.session_manager.current_goal.updated_at = datetime.now().isoformat()

                # Update context manager facts immediately
                self.context_manager.add_fact("goal_progress", str(self.session_manager.current_goal.progress_score),
                                              "planner")
                self.context_manager.add_fact("goal_status", self.session_manager.current_goal.status, "planner")

            # Reset only specification state, not session state
            self.spec_handler.reset_specifications()

            response = {
                "response": agent_result.get("user_message",
                                             "I've processed your request successfully and found great options for you."),
                "status": "agent_executed",
                "action": "agent_call",
                "agent_type": decision.agent_type,
                "agent_result": agent_result,
                "goal_status": goal_evaluation["status"],
                "goal_achieved": goal_evaluation["achieved"],
                "goal_progress": goal_evaluation["progress_score"],  # This should match session info now
                "goal_evaluation": {
                    "reasoning": goal_evaluation["reasoning"],
                    "criteria_met": goal_evaluation["criteria_met"],
                    "satisfaction_signals": goal_evaluation["satisfaction_signals"],
                    "business_value": goal_evaluation["business_value"]
                }
            }

            # Update planner status based on goal evaluation
            if goal_evaluation["achieved"]:
                self.session_manager.status = PlannerStatus.GOAL_ACHIEVED
                response["session_complete"] = True
            else:
                self.session_manager.status = PlannerStatus.READY

            return response

        except Exception as e:
            return self.action_handlers.handle_error(f"Agent execution error: {str(e)}", "agent_call",
                                                     self.spec_handler)

    def _start_specification_gathering(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Start specification gathering process."""
        self.session_manager.status = PlannerStatus.GATHERING_SPECS
        self.spec_handler.start_specification_gathering(decision.specifications_needed or [])

        spec_questions = self.spec_handler.generate_specification_questions(decision.specifications_needed or [])
        message = decision.user_message or spec_questions
        self.context_manager.add_message("system", message)

        return {
            "response": message,
            "status": "gathering_specifications",
            "action": "gather_specs",
            "specifications_needed": decision.specifications_needed,
            "reasoning": decision.reasoning,
            "goal_status": decision.goal_status,
            "goal_progress": decision.goal_progress_score,
            "goal_evaluation": {
                "reasoning": decision.goal_achievement_reasoning,
                "criteria_met": decision.success_criteria_met,
                "satisfaction_signals": decision.satisfaction_indicators_present
            }
        }

    def _handle_specification_gathering(self, user_message: str) -> Dict[str, Any]:
        """Handle user responses during specification gathering."""
        nlu_result = self._analyze_with_nlu(user_message)
        update_result = self.spec_handler.update_specifications(
            nlu_result.get("entities", {}), user_message, self.context_manager
        )

        if update_result.get("all_specs_flexible") or not update_result.get("missing_specs"):
            return self._move_to_confirmation()
        elif update_result.get("specs_updated"):
            return self._continue_gathering(update_result.get("missing_specs", []))
        else:
            return self._provide_helpful_guidance(update_result.get("missing_specs", []), user_message)

    def _continue_gathering(self, missing_specs) -> Dict[str, Any]:
        """Continue gathering missing specifications."""
        questions = self.spec_handler.generate_specification_questions(missing_specs)
        self.context_manager.add_message("system", questions)

        return {
            "response": questions,
            "status": "gathering_specifications",
            "action": "continue_gathering",
            "specifications_needed": missing_specs,
            "specifications_gathered": self.spec_handler.gathered_specs,  # FIX: Always include current specs
            "goal_progress": min(0.7, len([s for s in self.spec_handler.required_specs.values() if s]) / len(
                self.spec_handler.required_specs))
        }

    def _provide_helpful_guidance(self, missing_specs, user_message) -> Dict[str, Any]:
        """Provide helpful guidance when no progress is made."""
        helpful_response = self.spec_handler.generate_helpful_clarification(missing_specs, user_message)
        self.context_manager.add_message("system", helpful_response)

        return {
            "response": helpful_response,
            "status": "gathering_specifications",
            "action": "clarify_specs",
            "specifications_needed": missing_specs,
            "specifications_gathered": self.spec_handler.gathered_specs  # FIX: Always include current specs
        }

    def _move_to_confirmation(self) -> Dict[str, Any]:
        """Move to requirement confirmation phase."""
        self.session_manager.status = PlannerStatus.CONFIRMING_REQUIREMENTS

        summary = self.spec_handler.create_requirement_summary()
        confirmation_message = (
            f"{summary}\n\n"
            "I want to make sure I have everything right before finding the perfect options for you. "
            "Does this look correct? Is there anything else you'd like me to consider?"
        )

        self.context_manager.add_message("system", confirmation_message)

        return {
            "response": confirmation_message,
            "status": "confirming_requirements",
            "action": "confirm_requirements",
            "requirement_summary": summary,
            "gathered_specifications": self.spec_handler.gathered_specs,
            "goal_progress": 0.8
        }

    def _handle_requirement_confirmation(self, user_response: str) -> Dict[str, Any]:
        """Handle user response to requirement confirmation."""
        confirmation_result = self.spec_handler.handle_confirmation_response(user_response, self.context_manager)

        if confirmation_result.get("confirmed"):
            if confirmation_result.get("satisfaction_detected"):
                self.session_manager.track_satisfaction_signal()
            return self._proceed_to_agent_call()
        elif confirmation_result.get("modifications_made"):
            return self._move_to_confirmation()
        else:
            return self._request_confirmation_clarification()

    def _request_confirmation_clarification(self) -> Dict[str, Any]:
        """Request clarification for confirmation response."""
        clarification = (
            "I want to make sure I understand correctly so I can find the best options for you. "
            "Should I proceed with the requirements I've listed, or would you like to change something specific? "
            "You can say 'yes, proceed' or tell me what you'd like to modify."
        )
        self.context_manager.add_message("system", clarification)

        return {
            "response": clarification,
            "status": "confirming_requirements",
            "action": "clarify_confirmation"
        }

    def _request_requirement_confirmation(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle requirement confirmation request from decision engine."""
        self.session_manager.status = PlannerStatus.CONFIRMING_REQUIREMENTS

        message = decision.user_message or decision.confirmation_summary or "Please confirm if these requirements look correct."
        self.context_manager.add_message("system", message)

        return {
            "response": message,
            "status": "confirming_requirements",
            "action": "confirm_requirements",
            "reasoning": decision.reasoning,
            "goal_status": decision.goal_status,
            "goal_progress": decision.goal_progress_score
        }

    def _proceed_to_agent_call(self) -> Dict[str, Any]:
        """Proceed to call appropriate agent after confirmation."""
        current_intent = self.intent_tracker.get_current_intent()

        # Determine agent and parameters based on intent
        agent_type, agent_params = self._determine_agent_call(current_intent)

        decision = PlannerDecision(
            action="call_agent",
            agent_type=agent_type,
            agent_params=agent_params,
            reasoning="All requirements confirmed, proceeding with high-quality agent call",
            goal_progress_score=0.9
        )

        return self._execute_agent_call(decision)

    def _determine_agent_call(self, current_intent):
        """Determine appropriate agent and parameters based on intent."""
        if current_intent and current_intent.intent_type in ["BUY", "RECOMMEND"]:
            return "DiscoveryAgent", {
                "category": self.spec_handler.gathered_specs.get("category", "electronics"),
                "subcategory": self.spec_handler.gathered_specs.get("subcategory") or "laptop",  # ADD: or "laptop"
                "specifications": {k: v for k, v in self.spec_handler.gathered_specs.items()
                                   if k not in ["category", "subcategory", "budget"]},
                "budget": self.spec_handler.gathered_specs.get("budget"),
                "user_message": f"Looking for {self.spec_handler.gathered_specs.get('subcategory') or 'laptop'} based on confirmed requirements",
                "discovery_mode": "auto",
                "quality_focus": True
            }
        elif current_intent and current_intent.intent_type == "ORDER":
            return "OrderAgent", {
                "order_id": self.spec_handler.gathered_specs.get("order_id"),
                "action": "track",
                "priority": "high"
            }
        elif current_intent and current_intent.intent_type == "RETURN":
            return "ReturnAgent", {
                "order_id": self.spec_handler.gathered_specs.get("order_id"),
                "return_reason": self.spec_handler.gathered_specs.get("return_reason", "not_specified"),
                "priority": "high"
            }
        else:
            return "DiscoveryAgent", self.spec_handler.gathered_specs

    def _execute_agent_call(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute agent call with goal achievement evaluation."""
        self.session_manager.status = PlannerStatus.EXECUTING_AGENT

        try:
            # Call agent and process results
            agent_result = self.mock_agents.call_agent(
                decision.agent_type, decision.agent_params, self.context_manager.get_context_summary()
            )

            self.context_manager.store_agent_result(decision.agent_type, agent_result)
            self.session_manager.increment_agent_calls()

            if agent_result.get("user_message"):
                self.context_manager.add_message("system", agent_result["user_message"])

            # Reset state and evaluate goal
            self.session_manager.status = PlannerStatus.READY
            self.spec_handler.reset_specifications()

            goal_evaluation = self.decision_engine.evaluate_post_agent_goal_status(
                agent_result, decision, self.session_manager.current_goal
            )

            response = {
                "response": agent_result.get("user_message",
                                             "I've processed your request successfully and found great options for you."),
                "status": "agent_executed",
                "action": "agent_call",
                "agent_type": decision.agent_type,
                "agent_result": agent_result,
                "goal_status": goal_evaluation["status"],
                "goal_achieved": goal_evaluation["achieved"],
                "goal_progress": goal_evaluation["progress_score"],
                "goal_evaluation": {
                    "reasoning": goal_evaluation["reasoning"],
                    "criteria_met": goal_evaluation["criteria_met"],
                    "satisfaction_signals": goal_evaluation["satisfaction_signals"],
                    "business_value": goal_evaluation["business_value"]
                }
            }

            # Handle goal achievement
            if goal_evaluation["achieved"]:
                self.session_manager.status = PlannerStatus.GOAL_ACHIEVED
                response["session_complete"] = True
                if self.session_manager.current_goal:
                    self.session_manager.current_goal.status = "completed"
                    self.session_manager.current_goal.progress_score = 1.0
                    self.session_manager.current_goal.updated_at = datetime.now().isoformat()

            return response

        except Exception as e:
            return self.action_handlers.handle_error(f"Agent execution error: {str(e)}", "agent_call",
                                                     self.spec_handler)

    def _analyze_with_nlu(self, user_message: str) -> Dict[str, Any]:
        """Analyze user message with NLU and track satisfaction signals."""
        conversation_context = self.context_manager.get_recent_messages(6)
        nlu_result = self.enhanced_nlu.analyze_message(user_message, conversation_context)

        # Track satisfaction signals
        satisfaction_keywords = ["thanks", "perfect", "great", "excellent", "wonderful", "amazing", "helpful",
                                 "exactly"]
        if any(keyword in user_message.lower() for keyword in satisfaction_keywords):
            self.session_manager.track_satisfaction_signal()

        self.context_manager.merge_facts_from_nlu(nlu_result)
        return nlu_result

    def _analyze_intent_continuity(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze intent continuity with enhanced goal awareness."""
        conversation_context = self.context_manager.get_recent_messages(6)
        return self.intent_tracker.track_new_intent(nlu_result, conversation_context)

    def get_session_info(self) -> Dict[str, Any]:
        """Get comprehensive session information."""
        session_info = self.session_manager.get_session_info(self.intent_tracker)
        session_info["specification_gathering"] = {
            "required_specs": self.spec_handler.required_specs,
            "gathered_specs": self.spec_handler.gathered_specs,
            "confirmed": self.spec_handler.specs_confirmed
        }
        return session_info

    def end_conversation(self, reason: str = "user_exit") -> Dict[str, Any]:
        """End conversation gracefully."""
        return self.session_manager.end_conversation(reason)