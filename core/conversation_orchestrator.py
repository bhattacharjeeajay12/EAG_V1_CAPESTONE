# core/conversation_orchestrator.py
"""
Conversation Orchestrator - Manages complete conversation lifecycle

Purpose: Provides a conversation loop that continuously manages user interactions
until goals are achieved or the session naturally ends.

Key Features:
- Autonomous conversation management with while loop
- Goal achievement detection and termination
- Session timeout handling
- Error recovery and graceful degradation
- Clean separation from IntelligentPlanner logic
"""

from typing import Dict, Any, Callable
from datetime import datetime, timedelta
from cleaning.intelligent_planner import IntelligentPlanner, PlannerStatus
import uuid

class ConversationOrchestrator:
    """
    Orchestrates complete conversations using IntelligentPlanner.
    Manages the conversation loop until natural completion.
    """

    def __init__(self, session_id: str = None, session_timeout_minutes: int = 30):
        """Initialize the conversation orchestrator."""
        self.planner = IntelligentPlanner(session_id)
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.session_start_time = datetime.now()
        self.conversation_active = False
        self.max_turns = 50  # Safety limit to prevent infinite loops
        self.turn_count = 0

    def run_conversation(self,
                         input_handler: Callable[[], str],
                         output_handler: Callable[[str], None]) -> Dict[str, Any]:
        """
        Run a complete conversation with continuous loop.

        Args:
            input_handler: Function to get user input (e.g., lambda: input("You: "))
            output_handler: Function to display responses (e.g., lambda msg: print(f"Assistant: {msg}"))

        Returns:
            Final conversation summary
        """

        # Start the conversation
        start_response = self.planner.start_conversation()
        output_handler(start_response["response"])
        self.conversation_active = True
        self.turn_count = 0

        # Main conversation loop
        while self.conversation_active and self.turn_count < self.max_turns:
            try:
                # Check for session timeout
                if self._is_session_expired():
                    output_handler("Session has timed out. Let me help you quickly wrap up.")
                    break

                # Get user input
                user_input = input_handler()

                # Handle exit commands
                if self._is_exit_command(user_input):
                    break

                # Process user message
                response = self.planner.process_user_message(user_input)
                output_handler(response["response"])

                # Check if conversation should end
                if self._should_end_conversation(response):
                    break

                self.turn_count += 1

            except KeyboardInterrupt:
                output_handler("Conversation interrupted by user.")
                break
            except Exception as e:
                output_handler(f"An error occurred: {str(e)}. Let me try to continue helping you.")
                # Continue the loop for error recovery

        # End conversation gracefully
        return self._end_conversation()

    def run_single_exchange(self, user_message: str) -> Dict[str, Any]:
        """
        Run a single question-answer exchange.
        Useful for API/web integrations where each request is separate.

        Args:
            user_message: User's message

        Returns:
            Response with conversation status
        """

        if not self.conversation_active:
            # Start conversation if not already started
            start_response = self.planner.start_conversation()
            self.conversation_active = True

            # If user provided a message with the start, process it
            if user_message.strip():
                return self.planner.process_user_message(user_message)
            else:
                return start_response

        # Check for exit commands
        if self._is_exit_command(user_message):
            return self._end_conversation()

        # Check session timeout
        if self._is_session_expired():
            return {
                "response": "Your session has expired. Please start a new conversation.",
                "status": "session_expired",
                "conversation_active": False
            }

        # Process message
        response = self.planner.process_user_message(user_message)

        # Check if conversation should end
        if self._should_end_conversation(response):
            self.conversation_active = False
            response["conversation_active"] = False
        else:
            response["conversation_active"] = True

        self.turn_count += 1
        return response

    def _should_end_conversation(self, response: Dict[str, Any]) -> bool:
        """Determine if conversation should end based on response."""

        # Explicit session complete signals
        if response.get("session_complete", False):
            return True

        # Goal achieved status
        if response.get("status") == "goal_achieved":
            return True

        # Conversation ended status
        if response.get("status") == "conversation_ended":
            return True

        # Goal achieved flag
        if response.get("goal_achieved", False):
            return True

        # Check planner status
        if self.planner.status == PlannerStatus.GOAL_ACHIEVED:
            return True

        return False

    def _is_exit_command(self, user_input: str) -> bool:
        """Check if user wants to exit."""
        exit_commands = {
            "exit", "quit", "bye", "goodbye", "end", "stop",
            "thanks", "thank you", "that's all", "done"
        }

        user_lower = user_input.lower().strip()

        # Exact matches
        if user_lower in exit_commands:
            return True

        # Phrase matches
        exit_phrases = [
            "that's all i need", "i'm done", "no more questions",
            "thank you for your help", "that helps", "perfect thanks"
        ]

        return any(phrase in user_lower for phrase in exit_phrases)

    def _is_session_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now() - self.session_start_time > self.session_timeout

    def _end_conversation(self) -> Dict[str, Any]:
        """End conversation gracefully and return summary."""
        self.conversation_active = False

        # Get session summary
        session_info = self.planner.get_session_info()

        # End the planner session
        end_response = self.planner.end_conversation("natural_completion")

        return {
            "response": end_response["response"],
            "status": "conversation_completed",
            "conversation_active": False,
            "turn_count": self.turn_count,
            "session_duration_minutes": (datetime.now() - self.session_start_time).total_seconds() / 60,
            "session_summary": session_info,
            "goal_achieved": session_info["current_goal"]["status"] == "completed" if session_info["current_goal"][
                "description"] else False
        }

    def get_conversation_status(self) -> Dict[str, Any]:
        """Get current conversation status."""
        return {
            "conversation_active": self.conversation_active,
            "turn_count": self.turn_count,
            "session_duration_minutes": (datetime.now() - self.session_start_time).total_seconds() / 60,
            "session_expired": self._is_session_expired(),
            "planner_status": self.planner.status.value,
            "session_info": self.planner.get_session_info()
        }

    def reset_session(self) -> None:
        """Reset for a new conversation."""
        session_id = self.planner.context_manager.session_id
        self.planner = IntelligentPlanner(session_id)
        self.session_start_time = datetime.now()
        self.conversation_active = False
        self.turn_count = 0


def test_conversation_orchestrator():
    """Test the conversation orchestrator."""
    print("🎭 Testing Conversation Orchestrator")
    print("=" * 50)

    # Test 1: Single exchange mode (for web/API usage)
    print("1️⃣ Testing single exchange mode:")
    orchestrator = ConversationOrchestrator("test_single_session")

    # Start and first message
    response1 = orchestrator.run_single_exchange("I want to buy a laptop")
    print(f"   Response: {response1['response'][:60]}...")
    print(f"   Status: {response1['status']}")
    print(f"   Active: {response1.get('conversation_active', 'unknown')}")

    # Follow-up message
    response2 = orchestrator.run_single_exchange("For gaming, budget is $1500")
    print(f"   Response: {response2['response'][:60]}...")
    print(f"   Active: {response2.get('conversation_active', 'unknown')}")

    # Confirmation
    response3 = orchestrator.run_single_exchange("Yes, that's correct")
    print(f"   Response: {response3['response'][:60]}...")
    print(f"   Active: {response3.get('conversation_active', 'unknown')}")

    # Exit
    response4 = orchestrator.run_single_exchange("Thank you, that's perfect!")
    print(f"   Final Response: {response4['response'][:60]}...")
    print(f"   Active: {response4.get('conversation_active', 'unknown')}")
    print(f"   Goal Achieved: {response4.get('goal_achieved', 'unknown')}")

    # Test 2: Conversation status
    print(f"\n2️⃣ Final Status:")
    status = orchestrator.get_conversation_status()
    print(f"   Turn Count: {status['turn_count']}")
    print(f"   Duration: {status['session_duration_minutes']:.1f} minutes")
    print(f"   Planner Status: {status['planner_status']}")

    print("\n" + "=" * 50)
    print("✅ Conversation Orchestrator Tests Complete!")
    print("\nKey Features Demonstrated:")
    print("🔄 Autonomous conversation loop management")
    print("🎯 Goal achievement detection and termination")
    print("⏱️ Session timeout handling")
    print("🔌 Flexible input/output interface")
    print("📊 Comprehensive conversation status tracking")
    print("🛡️ Error recovery and graceful degradation")


# Example usage for CLI
def cli_example():
    """Example of how to use orchestrator for CLI."""
    print("Starting CLI conversation (type 'exit' to end)...")

    # Generate a random UUID (UUID4)
    unique_id = str(uuid.uuid4())
    orchestrator = ConversationOrchestrator("cli_session_" +str(unique_id))

    def get_user_input():
        return input("You: ")

    def show_response(message):
        print(f"Assistant: {message}")

    # This would run the complete conversation loop
    summary = orchestrator.run_conversation(get_user_input, show_response)
    print(f"\nConversation Summary:")
    print(f"Turns: {summary['turn_count']}")
    print(f"Duration: {summary['session_duration_minutes']:.1f} minutes")
    print(f"Goal Achieved: {summary.get('goal_achieved', False)}")


if __name__ == "__main__":
    # test_conversation_orchestrator()
    # print("\n" + "=" * 50)
    # print("To run CLI example, call: cli_example()")
    cli_example()