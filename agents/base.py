from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

class Action:
    pass

@dataclass
class Ask(Action):
    question: str
    slot: Optional[str] = None
    def __repr__(self): return f"ASK({self.question})"

@dataclass
class ToolCall(Action):
    name: str
    params: Dict[str, Any]
    def __repr__(self): return f"TOOL({self.name}, {self.params})"

@dataclass
class Present(Action):
    items: List[Dict[str, Any]]
    affordances: List[str]
    def __repr__(self): return f"PRESENT({len(self.items)} items)"

@dataclass
class Commit(Action):
    result: Dict[str, Any]
    def __repr__(self): return f"COMMIT({self.result})"

@dataclass
class Info(Action):
    message: str
    def __repr__(self): return f"INFO({self.message})"

@dataclass
class AgentContext:
    workstream: Any
    session: Dict[str, Any]
    nlu_result: Dict[str, Any]

@dataclass
class AgentOutput:
    action: Action
    updated_slots: Optional[Dict[str, Any]] = None
    presented_items: Optional[List[Dict[str, Any]]] = None
    satisfaction_delta: float = 0.0
    mark_completed: bool = False

class AgentBase(Protocol):
    async def decide_next(self, ctx: AgentContext) -> AgentOutput: ...
