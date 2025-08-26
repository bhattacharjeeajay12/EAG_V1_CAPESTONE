# core/context_manager.py
"""
Context Manager - Single Source of Truth for Conversation State

Purpose: Manages all conversation context, facts, and state in a unified way.
Preserves context across intent transitions and plan changes while providing
clean interfaces for accessing and updating conversation state.

Key Responsibilities:
- Store and retrieve conversation facts
- Maintain conversation history
- Track plan progress and agent artifacts
- Provide context summaries for other components
- Ensure context preservation during intent switches

This module acts as the "memory" of the conversation, ensuring that information
is not lost when users change directions or when plans are adapted.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass
class ConversationFact:
    """Represents a single fact with metadata about its source and reliability."""

    value: Any
    source: str  # "user", "nlu", "agent", "system"
    confidence: float  # How reliable this fact is
    timestamp: str  # When this fact was recorded
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> Dict[str, Any]:
        """Convert fact to dictionary representation."""
        return {
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "context": self.context
        }


@dataclass
class ConversationMessage:
    """Represents a single message in the conversation with metadata."""

    role: str  # "user", "system", "agent"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata.copy()
        }


class ContextManager:
    """
    Unified context manager for conversation state.

    This class serves as the single source of truth for all conversation
    information, providing consistent access to facts, history, and state
    across all system components.
    """

    def __init__(self, session_id: str = None):
        """
        Initialize Context Manager.

        Args:
            session_id: Unique session identifier. If None, generates one.
        """
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Core conversation state
        self.facts: Dict[str, ConversationFact] = {}
        self.conversation_history: List[ConversationMessage] = []

        # Plan and execution state
        self.current_plan_goal: Optional[str] = None
        self.plan_progress: Dict[str, Any] = {}
        self.agent_artifacts: Dict[str, Any] = {}

        # Session management
        self.session_active: bool = True
        self.session_start_time: str = datetime.now().isoformat()

    def add_fact(self, key: str, value: Any, source: str = "user",
                 confidence: float = 1.0, context: Dict[str, Any] = None) -> None:
        """
        Add or update a fact in the context.

        Args:
            key: The fact key/name
            value: The fact value
            source: Source of the fact (user, nlu, agent, system)
            confidence: Confidence in this fact (0.0 to 1.0)
            context: Additional context about this fact
        """
        if value is None:
            return  # Don't store null values

        self.facts[key] = ConversationFact(
            value=value,
            source=source,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
            context=context or {}
        )

    def get_fact(self, key: str, default: Any = None) -> Any:
        """
        Get fact value by key.

        Args:
            key: The fact key to retrieve
            default: Default value if key not found

        Returns:
            The fact value or default
        """
        fact = self.facts.get(key)
        return fact.value if fact else default

    def get_fact_with_metadata(self, key: str) -> Optional[ConversationFact]:
        """
        Get complete fact with metadata.

        Args:
            key: The fact key to retrieve

        Returns:
            ConversationFact object or None if not found
        """
        return self.facts.get(key)

    def has_facts(self, required_keys: List[str]) -> bool:
        """
        Check if all required facts are available.

        Args:
            required_keys: List of fact keys that must be present

        Returns:
            True if all facts are available, False otherwise
        """
        return all(self.get_fact(key) is not None for key in required_keys)

    def missing_facts(self, required_keys: List[str]) -> List[str]:
        """
        Get list of missing required facts.

        Args:
            required_keys: List of fact keys that should be present

        Returns:
            List of missing fact keys
        """
        return [key for key in required_keys if self.get_fact(key) is None]

    def merge_facts_from_nlu(self, nlu_result: Dict[str, Any]) -> None:
        """
        Merge facts from NLU analysis result.

        Args:
            nlu_result: Result dictionary from NLU module
        """
        # Add intent information
        if nlu_result.get("intent"):
            self.add_fact("current_intent", nlu_result["intent"], "nlu", nlu_result.get("confidence", 0.5))

        # Add entities as facts
        entities = nlu_result.get("entities", {})
        for key, value in entities.items():
            if value is not None and value != [] and value != "":
                # Use higher confidence for specific entities
                entity_confidence = nlu_result.get("confidence", 0.5)
                if key in ["order_id", "product", "budget"]:  # Specific, important facts
                    entity_confidence = min(1.0, entity_confidence + 0.2)

                self.add_fact(key, value, "nlu", entity_confidence)

        # Store NLU metadata
        self.add_fact("last_nlu_confidence", nlu_result.get("confidence", 0.5), "system")
        if nlu_result.get("reasoning"):
            self.add_fact("last_nlu_reasoning", nlu_result["reasoning"], "system")

    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        Add message to conversation history.

        Args:
            role: Message role (user, system, agent)
            content: Message content
            metadata: Additional message metadata

        Returns:
            Generated message ID
        """
        import uuid
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        message = ConversationMessage(
            role=role,
            content=content,
            metadata={**(metadata or {}), "message_id": message_id}
        )

        self.conversation_history.append(message)
        return message_id

    def get_recent_messages(self, count: int = 5, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        Get recent conversation messages.

        Args:
            count: Number of recent messages to retrieve
            include_metadata: Whether to include message metadata

        Returns:
            List of recent messages
        """
        recent_messages = self.conversation_history[-count:] if self.conversation_history else []

        if include_metadata:
            return [msg.to_dict() for msg in recent_messages]
        else:
            return [
                {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
                for msg in recent_messages
            ]

    def set_plan_goal(self, goal: str, required_facts: List[str] = None) -> Dict[str, Any]:
        """
        Set current plan goal and assess readiness.

        Args:
            goal: The plan goal description
            required_facts: Facts required to execute this plan

        Returns:
            Plan readiness assessment
        """
        self.current_plan_goal = goal
        self.plan_progress = {
            "goal": goal,
            "start_time": datetime.now().isoformat(),
            "required_facts": required_facts or [],
            "status": "planning"
        }

        if required_facts:
            missing = self.missing_facts(required_facts)
            available = [f for f in required_facts if f not in missing]

            return {
                "goal": goal,
                "ready": len(missing) == 0, # Can we proceed?
                "missing_facts": missing, # What's missing?
                "available_facts": available, # What do we have?
                "readiness_score": len(available) / len(required_facts) if required_facts else 1.0
            }

        return {"goal": goal, "ready": True, "readiness_score": 1.0}

    def update_plan_progress(self, status: str, step: str = None, details: Dict[str, Any] = None) -> None:
        """
        Update plan execution progress.

        Args:
            status: Current plan status (planning, executing, completed, failed)
            step: Current step being executed
            details: Additional progress details
        """
        self.plan_progress.update({
            "status": status,
            "last_update": datetime.now().isoformat(),
            "current_step": step,
            "details": details or {}
        })

    def store_agent_result(self, agent_type: str, result: Dict[str, Any],
                           confidence: float = 0.8) -> None:
        """
        Store result from agent execution.

        Args:
            agent_type: Type of agent that produced the result
            result: The agent result data
            confidence: Confidence in the agent result
        """
        artifact_key = f"{agent_type.lower()}_result"

        self.agent_artifacts[artifact_key] = {
            "agent_type": agent_type,
            "result": result,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }

        # Also add relevant result data as facts
        if isinstance(result, dict):
            for key, value in result.items():
                if value is not None:
                    fact_key = f"agent_{key}"
                    self.add_fact(fact_key, value, f"agent_{agent_type.lower()}", confidence)

    def get_clarification_message(self, missing_facts: List[str]) -> Optional[str]:
        """
        Generate appropriate clarification message for missing facts.

        Args:
            missing_facts: List of fact keys that are missing

        Returns:
            Clarification message or None if no clarification needed
        """
        if not missing_facts:
            return None

        # Custom prompts for common facts
        fact_prompts = {
            "category": "What type of product are you interested in?",
            "subcategory": "Could you be more specific about what you're looking for?",
            "budget": "What's your budget range?",
            "order_id": "Could you provide your order ID?",
            "return_reason": "Could you tell me why you'd like to return this item?",
            "preferences": "What features are important to you?",
            "quantity": "How many do you need?"
        }

        if len(missing_facts) == 1:
            fact = missing_facts[0]
            return fact_prompts.get(fact, f"I need to know: {fact}")

        elif len(missing_facts) <= 3:
            prompts = []
            for fact in missing_facts:
                prompt = fact_prompts.get(fact, fact)
                prompts.append(f"• {prompt}")

            return f"I need a bit more information:\n" + "\n".join(prompts)

        else:
            return "I need some additional information to help you better. Could you provide more details?"

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive context summary for other components.

        Returns:
            Dictionary with context summary information
        """
        # Categorize facts by source
        facts_by_source = {}
        for key, fact in self.facts.items():
            source = fact.source
            if source not in facts_by_source:
                facts_by_source[source] = {}
            facts_by_source[source][key] = fact.value

        # Calculate session duration
        start_time = datetime.fromisoformat(self.session_start_time)
        duration_seconds = (datetime.now() - start_time).total_seconds()

        return {
            "session_id": self.session_id,
            "session_active": self.session_active,
            "session_duration_seconds": duration_seconds,
            "total_facts": len(self.facts),
            "facts_by_source": facts_by_source,
            "message_count": len(self.conversation_history),
            "current_plan_goal": self.current_plan_goal,
            "plan_status": self.plan_progress.get("status"),
            "agent_artifacts_count": len(self.agent_artifacts),
            "high_confidence_facts": [
                key for key, fact in self.facts.items()
                if fact.confidence >= 0.8
            ]
        }

    def export_context(self) -> Dict[str, Any]:
        """
        Export complete context for persistence or debugging.

        Returns:
            Complete context data as dictionary
        """
        return {
            "session_id": self.session_id,
            "session_active": self.session_active,
            "session_start_time": self.session_start_time,
            "facts": {key: fact.to_dict() for key, fact in self.facts.items()},
            "conversation_history": [msg.to_dict() for msg in self.conversation_history],
            "current_plan_goal": self.current_plan_goal,
            "plan_progress": self.plan_progress.copy(),
            "agent_artifacts": self.agent_artifacts.copy()
        }

    def end_session(self, reason: str = "completed") -> str:
        """
        End the conversation session gracefully.

        Args:
            reason: Reason for ending (completed, timeout, error, user_exit)

        Returns:
            Closing message
        """
        self.session_active = False

        # Add session end to facts
        self.add_fact("session_end_reason", reason, "system")
        self.add_fact("session_end_time", datetime.now().isoformat(), "system")

        # Generate appropriate closing message
        closing_messages = {
            "completed": "Great! I've helped you complete your request. Is there anything else you need?",
            "user_exit": "Thanks for using our service. Have a wonderful day!",
            "timeout": "This session has timed out. Feel free to start a new conversation anytime.",
            "error": "I apologize for the technical issue. Please try again or contact support if needed."
        }

        closing_msg = closing_messages.get(reason, "Thank you for the conversation!")
        self.add_message("system", closing_msg)

        return closing_msg


def test_context_manager():
    """Test Context Manager functionality with comprehensive scenarios."""
    print("🧪 Testing Context Manager")
    print("=" * 50)

    # Initialize context manager
    context_mgr = ContextManager("test_session_001")

    # Test 1: Basic fact storage and retrieval
    print("1️⃣ Testing fact storage and retrieval:")
    context_mgr.add_fact("category", "electronics", "user", 0.9)
    context_mgr.add_fact("budget", "under $1000", "user", 0.8)
    context_mgr.add_fact("user_preference", "gaming", "nlu", 0.7)

    print(f"   Category: {context_mgr.get_fact('category')}")
    print(f"   Budget: {context_mgr.get_fact('budget')}")
    print(f"   Missing fact: {context_mgr.get_fact('nonexistent', 'default_value')}")

    # Test 2: Fact metadata and sources
    print("\n2️⃣ Testing fact metadata:")
    category_fact = context_mgr.get_fact_with_metadata("category")
    print(f"   Category source: {category_fact.source}")
    print(f"   Category confidence: {category_fact.confidence}")
    print(f"   Category timestamp: {category_fact.timestamp[:19]}")  # Truncate for readability

    # Test 3: NLU result integration
    print("\n3️⃣ Testing NLU result integration:")
    nlu_result = {
        "intent": "BUY",
        "confidence": 0.85,
        "entities": {
            "subcategory": "laptop",
            "specifications": ["gaming", "RTX graphics"],
            "quantity": 1
        },
        "reasoning": "Clear purchase intent with specific product details"
    }

    context_mgr.merge_facts_from_nlu(nlu_result)
    print(f"   Intent: {context_mgr.get_fact('current_intent')}")
    print(f"   Subcategory: {context_mgr.get_fact('subcategory')}")
    print(f"   Specifications: {context_mgr.get_fact('specifications')}")

    # Test 4: Conversation history
    print("\n4️⃣ Testing conversation history:")
    msg1_id = context_mgr.add_message("user", "I want to buy a gaming laptop")
    msg2_id = context_mgr.add_message("system", "What's your budget range?")
    msg3_id = context_mgr.add_message("user", "Under $1500")

    recent_messages = context_mgr.get_recent_messages(3)
    print(f"   Recent messages count: {len(recent_messages)}")
    for i, msg in enumerate(recent_messages, 1):
        print(f"   {i}. [{msg['role']}] {msg['content']}")

    # Test 5: Plan goal and readiness assessment
    print("\n5️⃣ Testing plan goal and readiness:")
    required_facts = ["category", "subcategory", "budget"]
    readiness = context_mgr.set_plan_goal("complete_laptop_purchase", required_facts)

    print(f"   Goal: {readiness['goal']}")
    print(f"   Ready: {readiness['ready']}")
    print(f"   Readiness score: {readiness['readiness_score']:.2f}")
    print(f"   Available facts: {readiness['available_facts']}")
    print(f"   Missing facts: {readiness['missing_facts']}")

    # Test 6: Agent result storage
    print("\n6️⃣ Testing agent result storage:")
    agent_result = {
        "products_found": 5,
        "top_recommendation": "Dell Gaming Laptop",
        "price_range": "$1200-$1400"
    }

    context_mgr.store_agent_result("BUY", agent_result, 0.9)
    print(f"   Agent artifacts count: {len(context_mgr.agent_artifacts)}")
    print(f"   Top recommendation fact: {context_mgr.get_fact('agent_top_recommendation')}")

    # Test 7: Clarification message generation
    print("\n7️⃣ Testing clarification messages:")
    clarification1 = context_mgr.get_clarification_message(["preferences"])
    clarification2 = context_mgr.get_clarification_message(["order_id", "return_reason"])

    print(f"   Single missing fact: {clarification1}")
    print(f"   Multiple missing facts: {clarification2}")

    # Test 8: Context summary
    print("\n8️⃣ Testing context summary:")
    summary = context_mgr.get_context_summary()
    print(f"   Session ID: {summary['session_id']}")
    print(f"   Total facts: {summary['total_facts']}")
    print(f"   Message count: {summary['message_count']}")
    print(f"   High confidence facts: {summary['high_confidence_facts']}")
    print(f"   Facts by source: {list(summary['facts_by_source'].keys())}")

    # Test 9: Session ending
    print("\n9️⃣ Testing session ending:")
    closing_message = context_mgr.end_session("completed")
    print(f"   Session active: {context_mgr.session_active}")
    print(f"   Closing message: {closing_message}")

    print("\n" + "=" * 50)
    print("✅ Context Manager Tests Complete!")


if __name__ == "__main__":
    test_context_manager()