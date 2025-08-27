# core_1/context_manager.py
"""
Final Context Manager - Complete Data with Clean LLM Interface
Stores everything for debugging but gives LLM only what it needs.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional


class ContextManager:
    """Complete context storage with clean LLM interface."""

    def __init__(self, session_id: str = None):
        """Initialize context manager."""
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # === COMPLETE DATA STORAGE (For debugging/analytics) ===
        self.messages: List[Dict[str, Any]] = []  # Full message + component data
        self.session_active: bool = True
        self.session_start: str = datetime.now().isoformat()

        # Auto-increment counters
        self._message_counter = 0
        self._component_counter = 0

        # === CLEAN DATA FOR LLM ===
        self.llm_messages: List[Dict[str, str]] = []  # Just role + content
        self.llm_facts: Dict[str, Any] = {}  # Just key: value
        self.llm_last_agent: Dict[str, Any] = {}  # Just last agent result

    # === COMPLETE DATA METHODS (For system use) ===

    def add_message(self, role: str, content: str) -> int:
        """Add message to both complete and LLM storage."""
        self._message_counter += 1

        # Complete storage
        message = {
            "message_id": self._message_counter,
            "role": role,
            "content": content,
            "time": datetime.now().isoformat(),
            "components": []
        }
        self.messages.append(message)

        # LLM storage (clean)
        self.llm_messages.append({
            "role": role,
            "content": content
        })

        # Keep only recent messages for LLM (last 10)
        if len(self.llm_messages) > 10:
            self.llm_messages = self.llm_messages[-10:]

        return self._message_counter

    def add_component_data(self, message_id: int, component: str, input_data: Any, output_data: Any) -> int:
        """Add component data and update LLM facts."""
        # Find the message in complete storage
        message = None
        for msg in self.messages:
            if msg["message_id"] == message_id:
                message = msg
                break

        if not message:
            return -1

        self._component_counter += 1

        # Complete storage
        component_data = {
            "component_id": self._component_counter,
            "component": component,
            "input": input_data,
            "output": output_data,
            "time": datetime.now().isoformat()
        }
        message["components"].append(component_data)

        # Update LLM facts (clean)
        self._update_llm_facts(component, output_data)

        return self._component_counter

    def add_component_to_last_message(self, component: str, input_data: Any, output_data: Any) -> int:
        """Add component data to the last message."""
        if not self.messages:
            return -1

        last_message_id = self.messages[-1]["message_id"]
        return self.add_component_data(last_message_id, component, input_data, output_data)

    def _update_llm_facts(self, component: str, output_data: Any) -> None:
        """Update clean facts for LLM from component output."""
        if component == "nlu" and isinstance(output_data, dict):
            # Extract intent
            if output_data.get("intent"):
                self.llm_facts["intent"] = output_data["intent"]

            # Extract entities
            entities = output_data.get("entities", {})
            for key, value in entities.items():
                if value:  # Only store non-empty values
                    self.llm_facts[key] = value

        elif component == "agent" and isinstance(output_data, dict):
            # Store complete agent result for LLM
            self.llm_last_agent = {
                "component": component,
                "result": output_data
            }

            # Extract key facts
            if output_data.get("products_found"):
                self.llm_facts["products_found"] = output_data["products_found"]
            if output_data.get("status"):
                self.llm_facts["agent_status"] = output_data["status"]

    # === LLM INTERFACE (What LLM actually needs) ===

    def get_llm_context(self) -> Dict[str, Any]:
        """Get clean context for LLM decision making."""
        return {
            "messages": self.llm_messages.copy(),  # Recent conversation
            "facts": self.llm_facts.copy(),  # Current facts
            "last_agent": self.llm_last_agent.copy()  # Last agent result
        }

    def get_recent_messages(self, count: int = 5) -> List[Dict[str, str]]:
        """Get recent messages for LLM (clean format)."""
        return self.llm_messages[-count:]

    def get_current_facts(self) -> Dict[str, Any]:
        """Get current facts for LLM (clean format)."""
        return self.llm_facts.copy()

    # === COMPLETE DATA ACCESS (For debugging/analytics) ===

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """Get complete message history with all component data."""
        return self.messages

    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Get specific message by ID with all data."""
        for message in self.messages:
            if message["message_id"] == message_id:
                return message
        return None

    def get_component_history(self, component: str) -> List[Dict[str, Any]]:
        """Get all interactions for a specific component."""
        component_history = []
        for message in self.messages:
            for comp_data in message["components"]:
                if comp_data["component"] == component:
                    component_history.append({
                        "message_id": message["message_id"],
                        "component_id": comp_data["component_id"],
                        "input": comp_data["input"],
                        "output": comp_data["output"],
                        "time": comp_data["time"]
                    })
        return component_history

    def get_fact_evolution(self, fact_key: str) -> List[Dict[str, Any]]:
        """Get how a specific fact evolved over time."""
        evolution = []
        for message in self.messages:
            for comp_data in message["components"]:
                component = comp_data["component"]
                output = comp_data["output"]

                # Check if this component output contains the fact
                fact_value = None
                if component == "nlu" and isinstance(output, dict):
                    if fact_key == "intent" and output.get("intent"):
                        fact_value = output["intent"]
                    elif fact_key in output.get("entities", {}):
                        fact_value = output["entities"][fact_key]

                if fact_value:
                    evolution.append({
                        "message_id": message["message_id"],
                        "component_id": comp_data["component_id"],
                        "component": component,
                        "value": fact_value,
                        "time": comp_data["time"]
                    })

        return evolution

    def get_session_stats(self) -> Dict[str, Any]:
        """Get complete session statistics."""
        component_counts = {}
        for message in self.messages:
            for comp_data in message["components"]:
                component = comp_data["component"]
                component_counts[component] = component_counts.get(component, 0) + 1

        return {
            "session_id": self.session_id,
            "session_active": self.session_active,
            "total_messages": len(self.messages),
            "total_components": self._component_counter,
            "component_counts": component_counts,
            "llm_context_size": {
                "messages": len(self.llm_messages),
                "facts": len(self.llm_facts),
                "has_agent_result": bool(self.llm_last_agent)
            }
        }

    def export_complete_session(self) -> Dict[str, Any]:
        """Export everything for debugging/analytics."""
        return {
            "session_info": {
                "session_id": self.session_id,
                "session_start": self.session_start,
                "session_active": self.session_active
            },
            "complete_data": {
                "messages": self.messages,
                "message_counter": self._message_counter,
                "component_counter": self._component_counter
            },
            "llm_context": self.get_llm_context(),
            "stats": self.get_session_stats()
        }

    def end_session(self, reason: str = "completed") -> str:
        """End session gracefully."""
        self.session_active = False
        closing_msg = f"Session ended: {reason}"
        self.add_message("system", closing_msg)
        return closing_msg


def test_final_context_manager():
    """Test the final context manager with both complete and LLM interfaces."""
    print("🧪 Testing Final Context Manager")
    print("=" * 60)

    context = ContextManager("test_final")

    # Test 1: Add conversation
    print("1️⃣ Adding conversation:")
    msg1 = context.add_message("user", "I want a gaming laptop")
    msg2 = context.add_message("system", "What's your budget?")
    msg3 = context.add_message("user", "50K INR")
    print(f"   Message IDs: {msg1}, {msg2}, {msg3}")

    # Test 2: Add component data
    print("\n2️⃣ Adding component interactions:")

    # NLU for first message
    nlu_output1 = {"intent": "BUY", "entities": {"category": "laptop", "use_case": "gaming"}}
    comp1 = context.add_component_data(msg1, "nlu", "I want a gaming laptop", nlu_output1)

    # NLU for budget message
    nlu_output2 = {"entities": {"budget": "50K INR"}}
    comp2 = context.add_component_data(msg3, "nlu", "50K INR", nlu_output2)

    # Agent result
    agent_output = {"products_found": 5, "status": "success", "recommendations": ["Dell", "HP"]}
    comp3 = context.add_component_to_last_message("agent", {"category": "laptop", "budget": "50K"}, agent_output)

    print(f"   Component IDs: {comp1}, {comp2}, {comp3}")

    # Test 3: LLM Context (Clean)
    print("\n3️⃣ LLM Context (what LLM gets):")
    llm_context = context.get_llm_context()
    print(f"   Messages: {len(llm_context['messages'])}")
    print(f"   Facts: {llm_context['facts']}")
    print(f"   Agent Result: {bool(llm_context['last_agent'])}")

    # Test 4: Complete Data (For debugging)
    print("\n4️⃣ Complete Data (for debugging):")
    all_messages = context.get_all_messages()
    print(f"   Total complete messages: {len(all_messages)}")
    print(f"   Components in first message: {len(all_messages[0]['components'])}")

    # Test 5: Component History
    print("\n5️⃣ Component History:")
    nlu_history = context.get_component_history("nlu")
    print(f"   NLU interactions: {len(nlu_history)}")
    if nlu_history:
        print(f"   First NLU output: {nlu_history[0]['output']}")

    # Test 6: Fact Evolution
    print("\n6️⃣ Fact Evolution:")
    budget_evolution = context.get_fact_evolution("budget")
    print(f"   Budget changes: {len(budget_evolution)}")
    if budget_evolution:
        print(f"   Budget value: {budget_evolution[0]['value']}")

    # Test 7: Session Stats
    print("\n7️⃣ Session Statistics:")
    stats = context.get_session_stats()
    print(f"   Total messages: {stats['total_messages']}")
    print(f"   Component counts: {stats['component_counts']}")
    print(f"   LLM context size: {stats['llm_context_size']}")

    # Test 8: What LLM actually sees
    print("\n8️⃣ Raw LLM Context:")
    print("   Messages for LLM:")
    for i, msg in enumerate(llm_context['messages'], 1):
        print(f"     {i}. [{msg['role']}] {msg['content']}")
    print(f"   Current Facts: {llm_context['facts']}")

    print("\n" + "=" * 60)
    print("✅ Final Context Manager Complete!")
    print("🎯 LLM gets: Clean messages + Current facts + Last agent result")
    print("🔍 System gets: Complete audit trail with full component history")


if __name__ == "__main__":
    test_final_context_manager()