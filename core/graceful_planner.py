# core/graceful_planner.py
"""
Graceful Planner - Central Orchestrator with Intent Management

Purpose: Main orchestrator that coordinates all components to provide smooth
conversation flow with graceful intent transitions, conflict resolution, and
context preservation. This is the "brain" that makes routing decisions and
manages the overall conversation flow.

Key Responsibilities:
- Coordinate user input processing through NLU → Intent Tracker → Action
- Make central routing decisions based on component outputs
- Handle intent conflicts with appropriate clarification
- Manage plan creation and execution based on current facts
- Preserve context across intent transitions and plan changes
- Provide unified response generation

Flow: User Message → NLU → Intent Tracker → Plan Decision → Action Execution
"""

from typing import Dict, List, Any, Optional
from enum import Enum
from core.enhanced_nlu import EnhancedNLU
from core.intent_tracker import IntentTracker, ContinuityAnalysis, ContinuityType
from core.context_manager import ContextManager


class PlannerState(Enum):
    """States of the planner during conversation processing."""
    READY = "ready"  # Ready to process user input
    PROCESSING_NLU = "processing_nlu"  # Analyzing user message
    ANALYZING_INTENT = "analyzing_intent"  # Checking intent continuity
    WAITING_CLARIFICATION = "waiting_clarification"  # Waiting for user clarification
    EXECUTING_PLAN = "executing_plan"  # Executing current plan
    COMPLETED = "completed"  # Conversation completed
    ERROR = "error"  # Error state


@dataclass
class PlanStep:
    """Represents a step in the execution plan."""
    step_id: str
    step_type: str  # "clarify", "agent_call", "system_action"
    description: str
    required_facts: List[str]
    expected_outputs: List[str]
    agent_type: Optional[str] = None
    completed: bool = False


class GracefulPlanner:
    """
    Main orchestrator providing graceful conversation flow with intelligent
    intent management and adaptive planning.

    This class serves as the central coordinator, making all routing decisions
    and ensuring smooth conversation flow even when users change directions
    or when unexpected situations arise.
    """

    def __init__(self, session_id: str = None):
        """
        Initialize Graceful Planner.

        Args:
            session_id: Optional session identifier for context tracking
        """
        # Core components
        self.enhanced_nlu = EnhancedNLU()
        self.intent_tracker = IntentTracker()
        self.context_manager = ContextManager(session_id)

        # Planner state
        self.state = PlannerState.READY
        self.current_plan: List[PlanStep] = []
        self.current_step_index = 0

        # Pending operations (for clarification resolution)
        self.pending_continuity_analysis: Optional[ContinuityAnalysis] = None
        self.pending_intent_data: Optional[Dict[str, Any]] = None

        # Plan templates for different intents
        self.plan_templates = self._initialize_plan_templates()

    def start_conversation(self) -> Dict[str, Any]:
        """
        Start a new conversation session.

        Returns:
            Welcome message and session information
        """
        welcome_message = (
            "Hi! I'm your personal shopping assistant. I can help you:\n"
            "• 🛒 Find and buy products\n"
            "• 📦 Track your orders\n"
            "• 💡 Get product recommendations\n"
            "• ↩️ Process returns and exchanges\n\n"
            "What would you like to do today?"
        )

        self.context_manager.add_message("system", welcome_message)
        self.state = PlannerState.READY

        return {
            "response": welcome_message,
            "status": "ready",
            "session_id": self.context_manager.session_id,
            "state": self.state.value
        }

    def process_user_message(self, user_message: str) -> Dict[str, Any]:
        """
        Main processing pipeline for user messages.

        Args:
            user_message: The user's input message

        Returns:
            Complete response with action taken and next steps
        """
        try:
            # Add user message to context
            self.context_manager.add_message("user", user_message)

            # Handle special case: waiting for clarification
            if self.state == PlannerState.WAITING_CLARIFICATION:
                return self._handle_clarification_response(user_message)

            # Step 1: NLU Analysis
            self.state = PlannerState.PROCESSING_NLU
            nlu_result = self._analyze_with_nlu(user_message)

            # Step 2: Intent Continuity Analysis
            self.state = PlannerState.ANALYZING_INTENT
            intent_result = self._analyze_intent_continuity(nlu_result)

            # Step 3: Process based on intent analysis result
            if intent_result.get("requires_clarification"):
                return self._request_clarification(intent_result)
            else:
                return self._execute_intent_action(intent_result)

        except Exception as e:
            return self._handle_error(f"Processing error: {str(e)}", user_message)

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get comprehensive session information.

        Returns:
            Dictionary with current session state and statistics
        """
        current_intent = self.intent_tracker.get_current_intent()
        context_summary = self.context_manager.get_context_summary()

        return {
            "session_id": self.context_manager.session_id,
            "planner_state": self.state.value,
            "current_intent": {
                "type": current_intent.intent_type if current_intent else None,
                "summary": current_intent.get_summary() if current_intent else None,
                "status": current_intent.status.value if current_intent else None
            },
            "context_summary": context_summary,
            "plan_info": {
                "current_goal": self.context_manager.current_plan_goal,
                "steps_total": len(self.current_plan),
                "steps_completed": sum(1 for step in self.current_plan if step.completed),
                "current_step": self.current_step_index
            },
            "waiting_for_clarification": self.state == PlannerState.WAITING_CLARIFICATION
        }

    def end_conversation(self, reason: str = "user_exit") -> Dict[str, Any]:
        """
        End conversation gracefully.

        Args:
            reason: Reason for ending conversation

        Returns:
            Closing response and session summary
        """
        closing_message = self.context_manager.end_session(reason)
        self.state = PlannerState.COMPLETED

        return {
            "response": closing_message,
            "status": "completed",
            "reason": reason,
            "session_summary": self.get_session_info()
        }

    def _analyze_with_nlu(self, user_message: str) -> Dict[str, Any]:
        """
        Analyze user message with NLU component.

        Args:
            user_message: User's input message

        Returns:
            NLU analysis result
        """
        conversation_context = self.context_manager.get_recent_messages(6)
        nlu_result = self.enhanced_nlu.analyze_message(user_message, conversation_context)

        # Merge NLU results into context
        self.context_manager.merge_facts_from_nlu(nlu_result)

        return nlu_result

    def _analyze_intent_continuity(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze intent continuity using Intent Tracker.

        Args:
            nlu_result: Result from NLU analysis

        Returns:
            Intent tracking result with continuity analysis
        """
        conversation_context = self.context_manager.get_recent_messages(6)
        return self.intent_tracker.track_new_intent(nlu_result, conversation_context)

    def _request_clarification(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle case where clarification is needed from user.

        Args:
            intent_result: Result from intent tracking that requires clarification

        Returns:
            Clarification request response
        """
        self.state = PlannerState.WAITING_CLARIFICATION

        # Store pending information for resolution
        self.pending_continuity_analysis = intent_result.get("analysis")
        self.pending_intent_data = intent_result.get("pending_intent_data")

        clarification_message = intent_result.get("message", "I need clarification on what you'd like to do.")

        # Add clarification options for complex cases
        if intent_result.get("action") in ["clarify_switch", "clarify_addition"]:
            current_intent = self.intent_tracker.get_current_intent()
            if current_intent:
                clarification_message += f"\n\nOptions:\n" \
                                         f"• 'Continue' - keep working on {current_intent.intent_type.lower()}\n" \
                                         f"• 'Switch' - change to the new request\n" \
                                         f"• 'Both' - handle new request then return to current one"

        self.context_manager.add_message("system", clarification_message)

        return {
            "response": clarification_message,
            "status": "clarification_needed",
            "action": intent_result.get("action"),
            "state": self.state.value
        }

    def _handle_clarification_response(self, user_response: str) -> Dict[str, Any]:
        """
        Handle user's response to clarification request.

        Args:
            user_response: User's clarification response

        Returns:
            Result of clarification resolution
        """
        if not self.pending_continuity_analysis or not self.pending_intent_data:
            # No pending clarification - treat as new input
            self.state = PlannerState.READY
            return self.process_user_message(user_response)

        # Resolve clarification using Intent Tracker
        resolution = self.intent_tracker.resolve_clarification(
            user_response,
            self.pending_continuity_analysis,
            self.pending_intent_data
        )

        # Clear pending state
        self.pending_continuity_analysis = None
        self.pending_intent_data = None
        self.state = PlannerState.READY

        # Handle resolution result
        if resolution.get("action") == "re_clarify":
            return self._request_clarification(resolution)
        else:
            return self._execute_intent_action(resolution)

    def _execute_intent_action(self, intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute action based on intent analysis result.

        Args:
            intent_result: Result from intent continuity analysis

        Returns:
            Action execution result
        """
        action = intent_result.get("action")
        current_intent = self.intent_tracker.get_current_intent()

        if not current_intent:
            return self._handle_error("No current intent available", "")

        # Create or update plan based on current intent
        plan_result = self._create_plan_for_intent(current_intent)

        if not plan_result.get("success"):
            return self._handle_error(f"Plan creation failed: {plan_result.get('error')}", "")

        # Execute next step in plan
        self.state = PlannerState.EXECUTING_PLAN
        return self._execute_next_plan_step()

    def _create_plan_for_intent(self, intent: Any) -> Dict[str, Any]:
        """
        Create execution plan for given intent.

        Args:
            intent: TrackedIntent object

        Returns:
            Plan creation result
        """
        intent_type = intent.intent_type
        template = self.plan_templates.get(intent_type, self.plan_templates["DEFAULT"])

        # Create plan steps based on template and current context
        self.current_plan = []
        self.current_step_index = 0

        for step_template in template:
            step = PlanStep(
                step_id=step_template["step_id"],
                step_type=step_template["step_type"],
                description=step_template["description"],
                required_facts=step_template["required_facts"],
                expected_outputs=step_template["expected_outputs"],
                agent_type=step_template.get("agent_type")
            )
            self.current_plan.append(step)

        # Set plan goal in context
        goal = f"complete_{intent_type.lower()}_flow"
        self.context_manager.set_plan_goal(goal)

        return {"success": True, "steps": len(self.current_plan)}

    def _execute_next_plan_step(self) -> Dict[str, Any]:
        """
        Execute the next step in current plan.

        Returns:
            Step execution result
        """
        if self.current_step_index >= len(self.current_plan):
            # Plan completed
            self.intent_tracker.complete_current_intent()
            completion_message = "Great! I've completed your request. Is there anything else I can help you with?"
            self.context_manager.add_message("system", completion_message)
            self.state = PlannerState.READY

            return {
                "response": completion_message,
                "status": "completed",
                "action": "plan_completed"
            }

        current_step = self.current_plan[self.current_step_index]

        # Check if step can be executed (has required facts)
        missing_facts = self.context_manager.missing_facts(current_step.required_facts)

        if missing_facts:
            # Need clarification before executing step
            clarification_msg = self.context_manager.get_clarification_message(missing_facts)
            if clarification_msg:
                self.context_manager.add_message("system", clarification_msg)
                return {
                    "response": clarification_msg,
                    "status": "needs_clarification",
                    "action": "clarify",
                    "missing_facts": missing_facts
                }

        # Execute step based on type
        if current_step.step_type == "agent_call":
            return self._execute_agent_step(current_step)
        elif current_step.step_type == "system_action":
            return self._execute_system_step(current_step)
        else:
            # Skip unknown step types
            self._complete_current_step()
            return self._execute_next_plan_step()

    def _execute_agent_step(self, step: PlanStep) -> Dict[str, Any]:
        """
        Execute agent call step (mocked for now).

        Args:
            step: PlanStep to execute

        Returns:
            Agent execution result
        """
        agent_type = step.agent_type or "UNKNOWN"

        # Mock agent response based on type
        mock_responses = {
            "BUY": "I found 3 great options matching your criteria. Here are the top recommendations...",
            "ORDER": "I've retrieved your order information. Your order #12345 is currently being processed...",
            "RECOMMEND": "Based on your preferences, I recommend these top-rated products...",
            "RETURN": "I've initiated your return request. You'll receive a confirmation email shortly..."
        }

        response_message = mock_responses.get(agent_type, f"Processing your {agent_type.lower()} request...")

        # Store mock agent result
        mock_result = {
            "agent_type": agent_type,
            "status": "success",
            "message": response_message
        }

        self.context_manager.store_agent_result(agent_type, mock_result)
        self.context_manager.add_message("system", response_message)

        # Complete current step and continue
        self._complete_current_step()

        return {
            "response": response_message,
            "status": "processing",
            "action": "agent_call",
            "agent_type": agent_type
        }

    def _execute_system_step(self, step: PlanStep) -> Dict[str, Any]:
        """
        Execute system action step.

        Args:
            step: PlanStep to execute

        Returns:
            System action result
        """
        system_message = f"Executing {step.description}..."
        self.context_manager.add_message("system", system_message)

        # Complete step and continue
        self._complete_current_step()

        return {
            "response": system_message,
            "status": "processing",
            "action": "system_action"
        }

    def _complete_current_step(self) -> None:
        """Mark current step as completed and move to next."""
        if self.current_step_index < len(self.current_plan):
            self.current_plan[self.current_step_index].completed = True
            self.current_step_index += 1

    def _handle_error(self, error_message: str, user_message: str) -> Dict[str, Any]:
        """
        Handle errors gracefully.

        Args:
            error_message: The error that occurred
            user_message: Original user message that caused error

        Returns:
            Error response
        """
        self.state = PlannerState.ERROR

        user_friendly_message = "I apologize, but I encountered an issue processing your request. Could you please try rephrasing what you need?"

        self.context_manager.add_message("system", user_friendly_message)
        self.context_manager.add_fact("last_error", error_message, "system", 1.0)

        # Reset to ready state for recovery
        self.state = PlannerState.READY

        return {
            "response": user_friendly_message,
            "status": "error",
            "action": "retry",
            "error": error_message
        }

    def _initialize_plan_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Initialize plan templates for different intent types.

        Returns:
            Dictionary of plan templates
        """
        return {
            "BUY": [
                {
                    "step_id": "gather_requirements",
                    "step_type": "clarify",
                    "description": "Gather product requirements",
                    "required_facts": [],
                    "expected_outputs": ["category", "subcategory", "budget"]
                },
                {
                    "step_id": "search_products",
                    "step_type": "agent_call",
                    "description": "Search for matching products",
                    "required_facts": ["category", "subcategory"],
                    "expected_outputs": ["product_options"],
                    "agent_type": "BUY"
                },
                {
                    "step_id": "finalize_purchase",
                    "step_type": "agent_call",
                    "description": "Complete purchase process",
                    "required_facts": ["selected_product"],
                    "expected_outputs": ["purchase_confirmation"],
                    "agent_type": "BUY"
                }
            ],
            "ORDER": [
                {
                    "step_id": "get_order_id",
                    "step_type": "clarify",
                    "description": "Get order identifier",
                    "required_facts": [],
                    "expected_outputs": ["order_id"]
                },
                {
                    "step_id": "fetch_order",
                    "step_type": "agent_call",
                    "description": "Retrieve order information",
                    "required_facts": ["order_id"],
                    "expected_outputs": ["order_details"],
                    "agent_type": "ORDER"
                }
            ],
            "RECOMMEND": [
                {
                    "step_id": "understand_needs",
                    "step_type": "clarify",
                    "description": "Understand user preferences",
                    "required_facts": [],
                    "expected_outputs": ["category", "preferences"]
                },
                {
                    "step_id": "generate_recommendations",
                    "step_type": "agent_call",
                    "description": "Generate product recommendations",
                    "required_facts": ["category"],
                    "expected_outputs": ["recommendations"],
                    "agent_type": "RECOMMEND"
                }
            ],
            "RETURN": [
                {
                    "step_id": "get_return_details",
                    "step_type": "clarify",
                    "description": "Get return information",
                    "required_facts": [],
                    "expected_outputs": ["order_id", "return_reason"]
                },
                {
                    "step_id": "process_return",
                    "step_type": "agent_call",
                    "description": "Process return request",
                    "required_facts": ["order_id"],
                    "expected_outputs": ["return_confirmation"],
                    "agent_type": "RETURN"
                }
            ],
            "DEFAULT": [
                {
                    "step_id": "clarify_intent",
                    "step_type": "clarify",
                    "description": "Clarify user intent",
                    "required_facts": [],
                    "expected_outputs": ["intent"]
                }
            ]
        }


def test_graceful_planner():
    """Test the complete Graceful Planner system."""
    print("🧪 Testing Graceful Planner")
    print("=" * 60)

    planner = GracefulPlanner("test_graceful_session")

    # Test 1: Start conversation
    print("1️⃣ Starting conversation:")
    welcome_response = planner.start_conversation()
    print(f"   Status: {welcome_response['status']}")
    print(f"   Response: {welcome_response['response'][:80]}...")

    # Test 2: Simple intent flow
    print("\n2️⃣ User wants to buy laptop:")
    response1 = planner.process_user_message("I want to buy a gaming laptop under $1500")
    print(f"   Status: {response1['status']}")
    print(f"   Response: {response1['response'][:80]}...")

    # Test 3: Intent conflict scenario
    print("\n3️⃣ User suddenly switches to return:")
    response2 = planner.process_user_message("Actually, I want to return my broken headphones")
    print(f"   Status: {response2['status']}")
    print(f"   Action: {response2.get('action', 'N/A')}")
    if response2['status'] == 'clarification_needed':
        print(f"   Clarification: {response2['response'][:80]}...")

    # Test 4: Resolve clarification
    if response2['status'] == 'clarification_needed':
        print("\n4️⃣ User resolves clarification:")
        response3 = planner.process_user_message("Switch to the return request")
        print(f"   Status: {response3['status']}")
        print(f"   Response: {response3['response'][:80]}...")

    # Test 5: Session information
    print("\n5️⃣ Current session information:")
    session_info = planner.get_session_info()
    print(f"   Session ID: {session_info['session_id']}")
    print(f"   Planner state: {session_info['planner_state']}")
    print(f"   Current intent: {session_info['current_intent']['type']}")
    print(f"   Total facts: {session_info['context_summary']['total_facts']}")
    print(f"   Messages: {session_info['context_summary']['message_count']}")
    print(
        f"   Plan progress: {session_info['plan_info']['steps_completed']}/{session_info['plan_info']['steps_total']}")

    # Test 6: Error handling
    print("\n6️⃣ Testing error handling:")
    # Simulate error by passing empty message
    error_response = planner.process_user_message("")
    print(f"   Status: {error_response['status']}")
    print(f"   Error handled gracefully: {error_response['status'] == 'error'}")

    # Test 7: End conversation
    print("\n7️⃣ Ending conversation:")
    end_response = planner.end_conversation("completed")
    print(f"   Status: {end_response['status']}")
    print(f"   Closing: {end_response['response']}")

    print("\n" + "=" * 60)
    print("✅ Graceful Planner Tests Complete!")


if __name__ == "__main__":
    test_graceful_planner()