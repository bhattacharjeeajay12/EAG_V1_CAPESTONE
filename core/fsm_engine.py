# core/fsm_engine.py
from typing import Dict, List

class FSMEngine:
    def __init__(self, transitions: Dict[str, List[str]]):
        self.transitions = transitions

    def can_transition(self, current: str, next_state: str) -> bool:
        """Check if transition is valid."""
        return next_state in self.transitions.get(current, [])

    def next_state(self, current: str, next_state: str) -> str:
        """Move to next state if valid, else raise error."""
        if self.can_transition(current, next_state):
            return next_state
        raise ValueError(f"Invalid transition: {current} → {next_state}")
