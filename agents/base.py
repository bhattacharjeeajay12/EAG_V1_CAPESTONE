# agents/base.py
"""
Base classes and shared types for all agents.
Each agent implements a tiny micro-planner: given the focused Workstream + NLU result,
decide exactly one next Action and optional state updates.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


# ----------- Actions (uniform API to the runtime/UI) -----------
class Action:
    pass

@dataclass
class Ask(Action):
    question: str
    slot: Optional[str] = None

    def __repr__(self) -> str:
        return f"ASK({self.question})"

@dataclass
class ToolCall(Action):
    name: str
    params: Dict[str, Any]

    def __repr__(self) -> str:
        return f"TOOL({self.name}, {self.params})"

@dataclass
class Present(Action):
    items: List[Dict[str, Any]]
    affordances: List[str]

    def __repr__(self) -> str:
        return f"PRESENT({len(self.items)} items, affordances={self.affordances})"

@dataclass
class Commit(Action):
    result: Dict[str, Any]

    def __repr__(self) -> str:
        return f"COMMIT({self.result})"

@dataclass
class Info(Action):
    message: str

    def __repr__(self) -> str:
        return f"INFO({self.message})"

@dataclass
class SwitchFocus(Action):
    to_ws_id: str

    def __repr__(self) -> str:
        return f"SWITCH_FOCUS({self.to_ws_id})"


# ----------- Agent I/O containers -----------
@dataclass
class AgentContext:
    workstream: Any  # Workstream
    session: Dict[str, Any]
    nlu_result: Dict[str, Any]

@dataclass
class AgentOutput:
    action: Action
    updated_slots: Optional[Dict[str, Any]] = None
    presented_items: Optional[List[Dict[str, Any]]] = None
    satisfaction_delta: float = 0.0
    mark_completed: bool = False


# ----------- Agent interface -----------
class AgentBase(Protocol):
    def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ...
