# planner_new.py
"""
Main Planner/Orchestrator - Coordinates all components
"""

from typing import Dict, Any, Optional
from cleaning.context import Context, OrchestratorState
from cleaning.conversation_manager import ConversationManager
from cleaning.plan_graph import PlanGraph
from cleaning.execution_controller import ExecutionController
from cleaning.agent_contracts import AgentInvoker
from nlu.nlu import NLUModule


class PlannerOrchestrator:
    """
    Main orchestrator that coordinates conversation, planning, and execution.

    This class stays minimal and delegates to specialized components.
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize the orchestrator with all components.

        Args:
            session_id: Optional session ID for conversation tracking
        """
        # Core components
        self.conversation_manager = ConversationManager(session_id)
        self.nlu = NLUModule()
        self.agent_invoker = AgentInvoker()
        self.execution_controller = ExecutionController(self.agent_invoker)

        # Current state
        self.context = Context()
        self.state = OrchestratorState()
        self.current_plan: Optional[PlanGraph] = None

    def start_session(self) -> str:
        """
        Start a new orchestrator session.

        Returns:
            Welcome message for user
        """
        return self.conversation_manager.start_conversation()

    def process_user_input(self, user_message: str) -> Dict[str, Any]:
        """
        Process user input through the full orchestration pipeline.

        Args:
            user_message: User's message

        Returns:
            Orchestration result with response and status
        """
        try:
            # Step 1: Add to conversation history
            self.conversation_manager.add_user_message(user_message)

            # Step 2: NLU Analysis
            chat_history = self.conversation_manager.get_recent_context()
            nlu_result = self.nlu.analyze(user_message, chat_history)

            # Step 3: Update context with NLU results
            self._update_context_from_nlu(nlu_result)

            # Step 4: Create or adapt plan based on intent
            plan_result = self._manage_plan(nlu_result)

            # Step 5: Execute plan
            if self.current_plan and plan_result.get("plan_ready", False):
                execution_result = self.execution_controller.execute_plan(
                    self.current_plan, self.context, self.state
                )

                # Step 6: Generate response based on execution
                response = self._generate_response(execution_result, nlu_result)
            else:
                # Handle case where plan isn't ready (needs clarification)
                response = self._handle_clarification_needed(nlu_result, plan_result)

            # Step 7: Add response to conversation
            self.conversation_manager.add_system_response(response["message"])

            return {
                "response": response["message"],
                "status": response["status"],
                "conversation_id": self.conversation_manager.session_id,
                "context_updated": True,
                "plan_version": self.state.plan_version
            }

        except Exception as e:
            error_response = f"I apologize, but I encountered an error: {str(e)}"
            self.conversation_manager.add_system_response(error_response, "error")

            return {
                "response": error_response,
                "status": "error",
                "conversation_id": self.conversation_manager.session_id,
                "error": str(e)
            }

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        return {
            "session_id": self.conversation_manager.session_id,
            "conversation_summary": self.conversation_manager.get_conversation_summary(),
            "context_keys": list(self.context.facts.keys()),
            "current_plan": self.current_plan.to_dict() if self.current_plan else None,
            "orchestrator_state": {
                "current_node": self.state.current_node,
                "completed_nodes": list(self.state.completed_nodes),
                "plan_version": self.state.plan_version,
                "conversation_active": self.state.conversation_active
            }
        }

    def end_session(self, reason: str = "user_exit") -> str:
        """End the orchestrator session."""
        closing_message = self.conversation_manager.end_conversation(reason)
        self.state.conversation_active = False
        return closing_message

    def _update_context_from_nlu(self, nlu_result: Dict[str, Any]) -> None:
        """Update context with NLU analysis results."""
        # Add intent and confidence
        self.context.merge({
            "intent": nlu_result["intent"],
            "confidence": nlu_result["confidence"],
            "last_nlu_reasoning": nlu_result["reasoning"]
        })

        # Add entities to context
        entities = nlu_result.get("entities", {})
        entity_updates = {}

        for key, value in entities.items():
            if value is not None and value != []:
                entity_updates[key] = value

        if entity_updates:
            self.context.merge(entity_updates)

        # Store clarification needs
        if nlu_result.get("clarification_needed"):
            self.context.merge({
                "clarification_needed": nlu_result["clarification_needed"]
            }, "assumptions")

    def _manage_plan(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create or adapt plan based on NLU results."""
        intent = nlu_result["intent"]

        # If no current plan or intent changed significantly, create new plan
        if (self.current_plan is None or
                self.current_plan.template_used != intent):
            self.current_plan = PlanGraph()
            self.current_plan.create_from_template(intent)
            self.state.increment_plan_version()

            return {
                "action": "created_new_plan",
                "plan_ready": True,
                "template_used": intent
            }

        return {
            "action": "using_existing_plan",
            "plan_ready": True,
            "template_used": self.current_plan.template_used
        }

    def _generate_response(self, execution_result: Dict[str, Any],
                           nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response based on execution results."""

        if execution_result["status"] == "completed":
            return {
                "message": "✅ I've successfully completed your request! Is there anything else you need help with?",
                "status": "success"
            }

        elif execution_result["status"] == "failed":
            failed_nodes = execution_result.get("failed_nodes", [])

            # Check if failure was due to missing information
            if any("clarification" in str(node) for node in failed_nodes):
                clarification_needed = self.context.get("clarification_needed", [])
                clarification_msg = self.conversation_manager.request_clarification(
                    clarification_needed, self.context
                )
                return {
                    "message": clarification_msg,
                    "status": "needs_clarification"
                }
            else:
                return {
                    "message": "I encountered an issue while processing your request. Could you please try rephrasing or provide more details?",
                    "status": "failed"
                }

        else:  # running or other status
            return {
                "message": "I'm working on your request. This may take a moment...",
                "status": "processing"
            }

    def _handle_clarification_needed(self, nlu_result: Dict[str, Any],
                                     plan_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cases where clarification is needed before execution."""
        clarification_needed = nlu_result.get("clarification_needed", [])

        if clarification_needed:
            clarification_msg = self.conversation_manager.request_clarification(
                clarification_needed, self.context
            )
            return {
                "message": clarification_msg,
                "status": "needs_clarification"
            }
        else:
            return {
                "message": "I need a bit more information to help you. Could you provide more details about what you're looking for?",
                "status": "needs_clarification"
            }


# Test function for the main orchestrator
def test_planner_orchestrator():
    """Test the main orchestrator with various scenarios."""
    print("🧪 Testing Planner Orchestrator")
    print("=" * 50)

    # Create orchestrator
    orchestrator = PlannerOrchestrator("test_session")

    # Start session
    welcome_msg = orchestrator.start_session()
    print(f"🤖 System: {welcome_msg}")

    # Test scenarios
    test_cases = [
        "I want to buy a laptop under $1000",
        "What's my order status for order #12345?",
        "Can you recommend the best smartphone?",
        "I need to return my defective headphones"
    ]

    for i, user_input in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"👤 User: {user_input}")

        result = orchestrator.process_user_input(user_input)
        print(f"🤖 System: {result['response']}")
        print(f"📊 Status: {result['status']}")

        # Show session info
        session_info = orchestrator.get_session_info()
        print(f"🔧 Context keys: {session_info['context_keys']}")
        print(f"🗂️ Plan version: {session_info['orchestrator_state']['plan_version']}")

    # End session
    closing_msg = orchestrator.end_session()
    print(f"\n🤖 System: {closing_msg}")

    # Final session summary
    final_info = orchestrator.get_session_info()
    conv_summary = final_info["conversation_summary"]
    print(f"\n📋 Final Session Summary:")
    print(f"  - Total messages: {conv_summary['total_messages']}")
    print(f"  - Duration: {conv_summary['duration']}")
    print(f"  - Agent interactions: {conv_summary['agent_interactions']}")

    print("\n" + "=" * 50)
    print("✅ Planner Orchestrator Test Complete!")


if __name__ == "__main__":
    test_planner_orchestrator()