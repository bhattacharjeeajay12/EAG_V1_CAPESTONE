# core/conversation_manager.py
"""
Conversation Management and Orchestration
"""

from typing import Dict, List, Any, Optional, Callable
from cleaning.context import Context, ConversationMessage
import uuid
from datetime import datetime


class ConversationManager:
    """
    Manages conversation flow, transcript, and user interactions.
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize conversation manager.

        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.conversation_history: List[ConversationMessage] = []
        self.conversation_state = "active"  # active, waiting, completed, error
        self.user_input_handler: Optional[Callable] = None

    def start_conversation(self) -> str:
        """
        Start a new conversation session.

        Returns:
            Welcome message for the user
        """
        welcome_message = (
            "👋 Welcome to our E-commerce Assistant! I can help you:\n"
            "• 🛒 Buy products and search for items\n"
            "• 📦 Track orders and check payment status\n"
            "• 💡 Get product recommendations\n"
            "• ↩️ Process returns and exchanges\n\n"
            "What can I help you with today?"
        )

        self._add_message("system", welcome_message, {
            "message_type": "welcome",
            "session_id": self.session_id
        })

        return welcome_message

    def add_user_message(self, user_input: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add user message to conversation history.

        Args:
            user_input: User's message
            metadata: Additional metadata for the message

        Returns:
            Message ID
        """
        message_id = self._add_message("user", user_input, metadata or {})
        return message_id

    def add_system_response(self, response: str, response_type: str = "response",
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add system response to conversation history.

        Args:
            response: System's response
            response_type: Type of response (response, clarification, error, etc.)
            metadata: Additional metadata

        Returns:
            Message ID
        """
        meta = metadata or {}
        meta["response_type"] = response_type

        message_id = self._add_message("system", response, meta)
        return message_id

    def add_agent_interaction(self, agent_type: str, request: Dict[str, Any],
                              response: Dict[str, Any]) -> str:
        """
        Log agent interaction in conversation history.

        Args:
            agent_type: Type of agent called
            request: Request sent to agent
            response: Response from agent

        Returns:
            Message ID
        """
        interaction_summary = f"[{agent_type} Agent] Processing request..."

        metadata = {
            "message_type": "agent_interaction",
            "agent_type": agent_type,
            "agent_request": request,
            "agent_response": response,
            "status": response.get("status", "unknown")
        }

        message_id = self._add_message("agent", interaction_summary, metadata)
        return message_id

    def request_clarification(self, missing_info: List[str], context: Context) -> str:
        """
        Generate clarification request for missing information.

        Args:
            missing_info: List of missing information keys
            context: Current context for personalization

        Returns:
            Clarification message
        """
        clarification_msg = self._generate_clarification_message(missing_info, context)

        self._add_message("system", clarification_msg, {
            "message_type": "clarification_request",
            "missing_info": missing_info,
            "awaiting_response": True
        })

        self.conversation_state = "waiting"
        return clarification_msg

    def end_conversation(self, reason: str = "completed") -> str:
        """
        End the conversation gracefully.

        Args:
            reason: Reason for ending (completed, user_exit, error, timeout)

        Returns:
            Closing message
        """
        closing_messages = {
            "completed": "✅ Great! I've helped you complete your request. Is there anything else you need?",
            "user_exit": "👋 Thank you for using our service. Have a great day!",
            "error": "😅 I apologize, but I encountered an issue. Please try again or contact support.",
            "timeout": "⏰ This session has timed out. Please start a new conversation if you need help."
        }

        closing_message = closing_messages.get(reason, "Thank you for using our service.")

        self._add_message("system", closing_message, {
            "message_type": "conversation_end",
            "reason": reason,
            "session_duration": self._calculate_session_duration()
        })

        self.conversation_state = "completed"
        return closing_message

    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get summary of the conversation.

        Returns:
            Conversation summary with key metrics
        """
        user_messages = [msg for msg in self.conversation_history if msg.role == "user"]
        system_messages = [msg for msg in self.conversation_history if msg.role == "system"]
        agent_interactions = [msg for msg in self.conversation_history if msg.role == "agent"]

        return {
            "session_id": self.session_id,
            "state": self.conversation_state,
            "total_messages": len(self.conversation_history),
            "user_messages": len(user_messages),
            "system_messages": len(system_messages),
            "agent_interactions": len(agent_interactions),
            "duration": self._calculate_session_duration(),
            "start_time": self.conversation_history[0].timestamp if self.conversation_history else None,
            "end_time": self.conversation_history[-1].timestamp if self.conversation_history else None
        }

    def get_recent_context(self, num_messages: int = 6) -> List[Dict[str, Any]]:
        """
        Get recent conversation context for LLM.

        Args:
            num_messages: Number of recent messages to include

        Returns:
            List of recent messages formatted for LLM
        """
        recent_messages = self.conversation_history[-num_messages:]

        context_messages = []
        for msg in recent_messages:
            # Skip internal agent interactions unless they have user-visible content
            if msg.role == "agent" and not msg.metadata.get("user_visible", False):
                continue

            context_messages.append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            })

        return context_messages

    def _add_message(self, role: str, content: str, metadata: Dict[str, Any]) -> str:
        """Add message to conversation history with ID generation."""
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        metadata["message_id"] = message_id

        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata
        )

        self.conversation_history.append(message)
        return message_id

    def _generate_clarification_message(self, missing_info: List[str], context: Context) -> str:
        """Generate appropriate clarification message based on missing info."""

        # Define user-friendly prompts for different missing information
        clarification_prompts = {
            "category": "What type of product are you looking for? (electronics, books, sports, etc.)",
            "subcategory": "Could you be more specific about the product category?",
            "budget": "What's your budget range for this purchase?",
            "order_id": "Please provide your order ID so I can look it up.",
            "return_reason": "Could you tell me why you'd like to return this item?",
            "preferences": "What features or specifications are important to you?",
            "product": "Which specific product are you interested in?",
            "quantity": "How many items do you need?"
        }

        if len(missing_info) == 1:
            key = missing_info[0]
            prompt = clarification_prompts.get(key, f"I need more information about: {key}")
            return f"🤔 {prompt}"

        elif len(missing_info) <= 3:
            prompts = []
            for key in missing_info:
                prompt = clarification_prompts.get(key, key)
                prompts.append(f"• {prompt}")

            return f"🤔 I need a bit more information:\n" + "\n".join(prompts)

        else:
            return (
                "🤔 I need some more details to help you better. "
                "Could you provide more specific information about what you're looking for?"
            )

    def _calculate_session_duration(self) -> Optional[str]:
        """Calculate duration of the conversation session."""
        if len(self.conversation_history) < 2:
            return None

        start_time = datetime.fromisoformat(self.conversation_history[0].timestamp)
        end_time = datetime.fromisoformat(self.conversation_history[-1].timestamp)

        duration = end_time - start_time

        if duration.total_seconds() < 60:
            return f"{int(duration.total_seconds())}s"
        elif duration.total_seconds() < 3600:
            return f"{int(duration.total_seconds() / 60)}m"
        else:
            hours = int(duration.total_seconds() / 3600)
            minutes = int((duration.total_seconds() % 3600) / 60)
            return f"{hours}h {minutes}m"


# Test code for ConversationManager
def test_conversation_manager():
    """Test the conversation manager functionality."""
    print("🧪 Testing Conversation Manager")
    print("=" * 50)

    # Create conversation manager
    conv_mgr = ConversationManager()

    # Start conversation
    welcome_msg = conv_mgr.start_conversation()
    print(f"🤖 System: {welcome_msg}")

    # Add user messages
    conv_mgr.add_user_message("I want to buy a laptop")
    print("👤 User: I want to buy a laptop")

    # Add system response
    conv_mgr.add_system_response("Great! I can help you find a laptop. What's your budget?")
    print("🤖 System: Great! I can help you find a laptop. What's your budget?")

    # Test clarification request
    from cleaning.context import Context
    context = Context()
    context.merge({"intent": "BUY", "category": "electronics"})

    clarification = conv_mgr.request_clarification(["budget", "preferences"], context)
    print(f"🤖 System: {clarification}")

    # Add agent interaction
    conv_mgr.add_agent_interaction("BUY", {"search": "laptop"}, {"status": "success", "results": 5})

    # Test conversation summary
    summary = conv_mgr.get_conversation_summary()
    print(f"\n📊 Conversation Summary:")
    print(f"  - Session ID: {summary['session_id']}")
    print(f"  - Total messages: {summary['total_messages']}")
    print(f"  - User messages: {summary['user_messages']}")
    print(f"  - System messages: {summary['system_messages']}")
    print(f"  - Agent interactions: {summary['agent_interactions']}")
    print(f"  - Duration: {summary['duration']}")

    # Test recent context
    recent_context = conv_mgr.get_recent_context(3)
    print(f"\n💭 Recent Context ({len(recent_context)} messages):")
    for msg in recent_context:
        print(f"  {msg['role']}: {msg['content'][:50]}...")

    # End conversation
    closing_msg = conv_mgr.end_conversation("completed")
    print(f"\n🤖 System: {closing_msg}")

    print("\n" + "=" * 50)
    print("✅ Conversation Manager Test Complete!")


if __name__ == "__main__":
    test_conversation_manager()