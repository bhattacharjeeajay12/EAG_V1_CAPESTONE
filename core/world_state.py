# core/world_state.py
"""
World State management for the planner system.
Maintains conversation state and context across agent interactions.
"""

from typing import Dict, Any, Optional
from datetime import datetime


class WorldState:
    """
    Maintains the current state of the conversation and user context.

    This includes:
    - User intent and NLU analysis
    - Extracted entities (products, orders, etc.)
    - Conversation history and context
    - Agent execution results
    - User journey progress
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self._state = initial_state or {}
        self._state.setdefault("created_at", datetime.now().isoformat())
        self._state.setdefault("last_updated", datetime.now().isoformat())

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the world state."""
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the world state."""
        self._state[key] = value
        self._state["last_updated"] = datetime.now().isoformat()

    def merge(self, updates: Dict[str, Any]) -> None:
        """Merge multiple updates into the world state."""
        self._state.update(updates)
        self._state["last_updated"] = datetime.now().isoformat()

    def remove(self, key: str) -> Any:
        """Remove and return a value from the world state."""
        self._state["last_updated"] = datetime.now().isoformat()
        return self._state.pop(key, None)

    def has(self, key: str) -> bool:
        """Check if a key exists in the world state."""
        return key in self._state

    def to_dict(self) -> Dict[str, Any]:
        """Return the world state as a dictionary."""
        return self._state.copy()

    def clear(self) -> None:
        """Clear the world state but keep timestamps."""
        created_at = self._state.get("created_at")
        self._state.clear()
        self._state["created_at"] = created_at
        self._state["last_updated"] = datetime.now().isoformat()

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return key in self._state

    def __getitem__(self, key: str) -> Any:
        """Support bracket notation for getting."""
        return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Support bracket notation for setting."""
        self.set(key, value)

    def __str__(self) -> str:
        """String representation of world state."""
        return f"WorldState({len(self._state)} keys)"

    def __repr__(self) -> str:
        """Detailed representation of world state."""
        return f"WorldState({self._state})"