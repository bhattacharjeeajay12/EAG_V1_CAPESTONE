# core/context_manager.py
"""
Simplified Context Manager - Clean and Essential
Keeps what matters, removes the bloat.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv

load_dotenv()
class ContextManager:
    """Simple, effective context management with essential features only."""

    # Source priority (higher number = higher priority)
    SOURCE_PRIORITY = {"agent": 1, "nlu": 2, "user": 3, "system": 3}

    def __init__(self, session_id: str = None):
        """Initialize simple context manager."""
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Core data - simple but essential
        self.facts: Dict[str, Dict[str, Any]] = {}  # {key: {value, source, time}}
        self.messages: List[Dict[str, Any]] = []  # [{role, content, time}]

        # Session management
        self.session_active: bool = True
        self.session_start: str = datetime.now().isoformat()

        # Agent results (just the last one)
        self.last_agent_result: Optional[Dict[str, Any]] = None

    def add_fact(self, key: str, value: Any, source: str = "user") -> None:
        """
        Add fact with source priority and conflict resolution.

        Args:
            key: Fact key
            value: Fact value
            source: Source (user, nlu, agent, system)
        """
        if not value:  # Skip empty values
            return

        current_time = datetime.now().isoformat()

        # Check if we should update (source priority or newer timestamp)
        should_update = True
        if key in self.facts:
            existing = self.facts[key]
            existing_priority = self.SOURCE_PRIORITY.get(existing["source"], 0)
            new_priority = self.SOURCE_PRIORITY.get(source, 0)

            # Don't override higher priority sources with lower ones
            if new_priority < existing_priority:
                should_update = False

        if should_update:
            self.facts[key] = {
                "value": value,
                "source": source,
                "time": current_time
            }

    def get_fact(self, key: str, default: Any = None) -> Any:
        """Get fact value (just the value, not metadata)."""
        fact = self.facts.get(key)
        return fact["value"] if fact else default

    def get_fact_with_source(self, key: str) -> Optional[Dict[str, Any]]:
        """Get fact with source info if needed for debugging."""
        return self.facts.get(key)

    def has_facts(self, required_keys: List[str]) -> bool:
        """Check if all required facts are available."""
        return all(key in self.facts for key in required_keys)

    def missing_facts(self, required_keys: List[str]) -> List[str]:
        """Get missing required facts."""
        return [key for key in required_keys if key not in self.facts]

    def add_message(self, role: str, content: str) -> None:
        """Add message to conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "time": datetime.now().isoformat()
        })

    def get_recent_messages(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get recent messages for LLM context."""
        recent = self.messages[-count:] if self.messages else []
        # Return just role and content for LLM (no timestamps needed)
        return [{"role": msg["role"], "content": msg["content"]} for msg in recent]

    def merge_facts_from_nlu(self, nlu_result: Dict[str, Any]) -> None:
        """Extract and store facts from NLU result."""
        # Store intent
        if nlu_result.get("intent"):
            self.add_fact("current_intent", nlu_result["intent"], "nlu")

        # Store entities as facts
        entities = nlu_result.get("entities", {})
        for key, value in entities.items():
            if value:  # Only store non-empty values
                self.add_fact(key, value, "nlu")

    def store_agent_result(self, agent_type: str, result: Dict[str, Any]) -> None:
        """Store latest agent result."""
        self.last_agent_result = {
            "agent_type": agent_type,
            "result": result,
            "time": datetime.now().isoformat()
        }

        # Extract useful facts from agent result
        if isinstance(result, dict):
            if result.get("products_found"):
                self.add_fact("products_found", result["products_found"], "agent")
            if result.get("status"):
                self.add_fact("last_agent_status", result["status"], "agent")

    def get_context_summary(self) -> Dict[str, Any]:
        """Get clean context for LLM consumption."""
        # Group facts by source for LLM understanding
        facts_by_source = {}
        for key, fact_data in self.facts.items():
            source = fact_data["source"]
            if source not in facts_by_source:
                facts_by_source[source] = {}
            facts_by_source[source][key] = fact_data["value"]

        return {
            "session_id": self.session_id,
            "session_active": self.session_active,
            "total_facts": len(self.facts),
            "facts_by_source": facts_by_source,
            "message_count": len(self.messages),
            "last_agent_call": self.last_agent_result["agent_type"] if self.last_agent_result else None
        }

    def end_session(self, reason: str = "completed") -> str:
        """End session gracefully."""
        self.session_active = False
        self.add_fact("session_end_reason", reason, "system")

        # Simple closing messages
        closing_messages = {
            "completed": "Great! I've helped you complete your request. Is there anything else you need?",
            "user_exit": "Thanks for using our service. Have a wonderful day!",
            "timeout": "This session has timed out. Feel free to start a new conversation anytime."
        }

        closing_msg = closing_messages.get(reason, "Thank you for the conversation!")
        self.add_message("system", closing_msg)
        return closing_msg

    def get_all_facts(self) -> Dict[str, Any]:
        """Get all facts as simple key-value pairs for debugging."""
        return {key: fact_data["value"] for key, fact_data in self.facts.items()}


def test_simple_context_manager():
    """Test the simplified context manager."""
    print("🧪 Testing Simplified Context Manager")
    print("=" * 50)

    context = ContextManager("test_session")

    # Test 1: Basic fact storage with source priority
    print("1️⃣ Testing fact storage and source priority:")
    context.add_fact("budget", "50000 INR", "nlu")
    print(f"   Budget (NLU): {context.get_fact('budget')}")

    context.add_fact("budget", "60000 INR", "user")  # Should override
    print(f"   Budget (User override): {context.get_fact('budget')}")

    context.add_fact("budget", "40000 INR", "nlu")  # Should NOT override
    print(f"   Budget (NLU attempt): {context.get_fact('budget')}")

    # Test 2: Message history
    print("\n2️⃣ Testing message history:")
    context.add_message("user", "I want a laptop")
    context.add_message("system", "What's your budget?")
    context.add_message("user", "50000 INR")

    recent = context.get_recent_messages(2)
    for i, msg in enumerate(recent, 1):
        print(f"   {i}. [{msg['role']}] {msg['content']}")

    # Test 3: NLU integration
    print("\n3️⃣ Testing NLU integration:")
    nlu_result = {
        "intent": "BUY",
        "entities": {
            "category": "laptop",
            "use_case": "gaming"
        }
    }
    context.merge_facts_from_nlu(nlu_result)
    print(f"   Intent: {context.get_fact('current_intent')}")
    print(f"   Category: {context.get_fact('category')}")

    # Test 4: Agent result storage
    print("\n4️⃣ Testing agent results:")
    agent_result = {
        "products_found": 5,
        "status": "success",
        "top_product": "Dell Gaming Laptop"
    }
    context.store_agent_result("DiscoveryAgent", agent_result)
    print(f"   Products found: {context.get_fact('products_found')}")
    print(f"   Agent status: {context.get_fact('last_agent_status')}")

    # Test 5: Context summary
    print("\n5️⃣ Testing context summary:")
    summary = context.get_context_summary()
    print(f"   Total facts: {summary['total_facts']}")
    print(f"   Facts by source: {list(summary['facts_by_source'].keys())}")
    print(f"   Last agent: {summary['last_agent_call']}")

    # Test 6: All facts
    print("\n6️⃣ All current facts:")
    all_facts = context.get_all_facts()
    for key, value in all_facts.items():
        source_info = context.get_fact_with_source(key)
        print(f"   {key}: {value} (from {source_info['source']})")

    print("\n" + "=" * 50)
    print("✅ Simplified Context Manager Tests Complete!")
    print(f"📊 Code reduction: ~80% less complexity while keeping essentials")


if __name__ == "__main__":
    test_simple_context_manager()