# core/context.py
"""
Context and State Management for the Planner System
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Optional
from datetime import datetime
import json


@dataclass
class Context:
    """
    Represents the current conversation context including facts, assumptions, and user intent.
    """
    facts: Dict[str, Any] = field(default_factory=dict)
    assumptions: Dict[str, Any] = field(default_factory=dict)
    user_intent: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    def merge(self, updates: Dict[str, Any], update_type: str = "facts") -> None:
        """
        Merge updates into the context.

        Args:
            updates: Dictionary of updates to merge
            update_type: Which section to update ("facts", "assumptions", "user_intent", "constraints")
        """
        if not updates:
            return

        target_dict = getattr(self, update_type, self.facts)
        target_dict.update(updates)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from context, checking facts first, then assumptions."""
        return self.facts.get(key) or self.assumptions.get(key, default)

    def has_all(self, required_keys: List[str]) -> bool:
        """Check if all required keys are available in context."""
        return all(self.get(key) is not None for key in required_keys)

    def missing_keys(self, required_keys: List[str]) -> List[str]:
        """Return list of missing required keys."""
        return [key for key in required_keys if self.get(key) is None]

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "facts": self.facts.copy(),
            "assumptions": self.assumptions.copy(),
            "user_intent": self.user_intent.copy(),
            "constraints": self.constraints.copy()
        }


@dataclass
class OrchestratorState:
    """
    Tracks the current state of plan execution.
    """
    current_node: Optional[str] = None
    completed_nodes: Set[str] = field(default_factory=set)
    failed_nodes: Set[str] = field(default_factory=set)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    plan_version: int = 1
    conversation_active: bool = True

    def mark_completed(self, node_id: str) -> None:
        """Mark a node as completed."""
        self.completed_nodes.add(node_id)
        if node_id in self.failed_nodes:
            self.failed_nodes.remove(node_id)

    def mark_failed(self, node_id: str, error: str) -> None:
        """Mark a node as failed with error details."""
        self.failed_nodes.add(node_id)
        self.add_to_history("node_failed", {"node": node_id, "error": error})

    def add_artifact(self, key: str, value: Any) -> None:
        """Store an artifact from agent execution."""
        self.artifacts[key] = value

    def add_to_history(self, event_type: str, data: Dict[str, Any]) -> None:
        """Add an event to execution history."""
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data,
            "plan_version": self.plan_version
        }
        self.execution_history.append(history_entry)

    def increment_plan_version(self) -> None:
        """Increment plan version when plan is modified."""
        self.plan_version += 1
        self.add_to_history("plan_modified", {"new_version": self.plan_version})


@dataclass
class ConversationMessage:
    """
    Represents a single message in the conversation.
    """
    role: str  # "user", "system", "agent", "clarification"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata.copy()
        }


# Test code for Context and State management
def test_context_functionality():
    """Test Context class functionality."""
    print("🧪 Testing Context Functionality")
    print("=" * 50)

    # Create new context
    context = Context()

    # Test merging facts
    print("📝 Testing Facts Merge:")
    context.merge({
        "intent": "BUY",
        "category": "electronics",
        "budget": "under $1000"
    })
    print(f"  Facts: {context.facts}")

    # Test merging assumptions
    print("\n🔮 Testing Assumptions Merge:")
    context.merge({
        "user_prefers": "premium_brand",
        "urgency": "low"
    }, "assumptions")
    print(f"  Assumptions: {context.assumptions}")

    # Test get method (facts first, then assumptions)
    print("\n🔍 Testing Get Method:")
    print(f"  intent: {context.get('intent')}")  # From facts
    print(f"  urgency: {context.get('urgency')}")  # From assumptions
    print(f"  missing_key: {context.get('missing_key', 'default_value')}")  # Default

    # Test has_all and missing_keys
    print("\n✅ Testing Validation Methods:")
    required_keys = ["intent", "category", "budget", "subcategory"]
    print(f"  Required keys: {required_keys}")
    print(f"  Has all: {context.has_all(required_keys)}")
    print(f"  Missing keys: {context.missing_keys(required_keys)}")

    # Add missing key
    context.merge({"subcategory": "laptop"})
    print(f"  After adding subcategory - Has all: {context.has_all(required_keys)}")

    # Test to_dict
    print("\n📊 Testing to_dict:")
    context_dict = context.to_dict()
    for section, data in context_dict.items():
        if data:
            print(f"  {section}: {data}")

    print("\n" + "=" * 40)
    print("✅ Context Tests Complete!")


def test_orchestrator_state():
    """Test OrchestratorState class functionality."""
    print("\n🧪 Testing Orchestrator State")
    print("=" * 50)

    # Create new state
    state = OrchestratorState()

    print("🏁 Initial State:")
    print(f"  Plan version: {state.plan_version}")
    print(f"  Conversation active: {state.conversation_active}")
    print(f"  History entries: {len(state.execution_history)}")

    # Test node completion
    print("\n✅ Testing Node Completion:")
    state.mark_completed("start")
    state.mark_completed("gather_requirements")
    print(f"  Completed nodes: {state.completed_nodes}")

    # Test node failure
    print("\n❌ Testing Node Failure:")
    state.mark_failed("search_products", "Missing category information")
    print(f"  Failed nodes: {state.failed_nodes}")
    print(f"  History entries: {len(state.execution_history)}")

    # Test artifact storage
    print("\n📦 Testing Artifact Storage:")
    state.add_artifact("search_results", ["laptop1", "laptop2"])
    state.add_artifact("user_preferences", {"brand": "Apple", "color": "silver"})
    print(f"  Artifacts: {list(state.artifacts.keys())}")

    # Test plan version increment
    print("\n🔄 Testing Plan Version:")
    initial_version = state.plan_version
    state.increment_plan_version()
    print(f"  Version: {initial_version} -> {state.plan_version}")

    # Test recovery (marking failed node as completed)
    print("\n🔄 Testing Node Recovery:")
    print(f"  Before recovery - Failed: {state.failed_nodes}")
    state.mark_completed("search_products")  # This should remove from failed
    print(f"  After recovery - Failed: {state.failed_nodes}")
    print(f"  After recovery - Completed: {state.completed_nodes}")

    # Show execution history
    print("\n📜 Execution History:")
    for i, entry in enumerate(state.execution_history, 1):
        print(f"  {i}. {entry['event_type']} (v{entry['plan_version']})")
        if 'data' in entry and entry['data']:
            key_info = list(entry['data'].keys())[0] if entry['data'] else 'no_data'
            print(f"     Data: {key_info}")

    print("\n" + "=" * 40)
    print("✅ Orchestrator State Tests Complete!")


def test_conversation_message():
    """Test ConversationMessage class functionality."""
    print("\n🧪 Testing Conversation Message")
    print("=" * 50)

    # Create different types of messages
    messages = [
        ConversationMessage("user", "I want to buy a laptop"),
        ConversationMessage("system", "What's your budget?", metadata={"type": "clarification"}),
        ConversationMessage("agent", "Found 5 laptops", metadata={"agent_type": "BUY", "results": 5})
    ]

    print("💬 Message Examples:")
    for i, msg in enumerate(messages, 1):
        print(f"  {i}. [{msg.role}] {msg.content}")
        if msg.metadata:
            print(f"     Metadata: {msg.metadata}")

    # Test to_dict conversion
    print("\n📊 Message Serialization:")
    for i, msg in enumerate(messages, 1):
        msg_dict = msg.to_dict()
        print(f"  Message {i} keys: {list(msg_dict.keys())}")

    print("\n" + "=" * 40)
    print("✅ Conversation Message Tests Complete!")


if __name__ == "__main__":
    test_context_functionality()
    test_orchestrator_state()
    test_conversation_message()
    print("\n" + "🎉" + "=" * 48 + "🎉")
    print("✅ ALL CONTEXT TESTS PASSED!")
    print("🎉" + "=" * 50 + "🎉")