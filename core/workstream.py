from dataclasses import dataclass, field
from typing import Dict, Any, Union
from config.enums import WorkstreamState
from core.fsm_engine import FSMEngine
from core.fsm_rules import WORKSTREAM_TRANSITIONS
from config.enums import Agents

@dataclass
class Workstream:
    id: str
    state: Union[WorkstreamState, str]
    phase: Union[Agents, str]
    slots: Dict[str, Any] = field(default_factory=dict)
    # Make FSM an instance attribute so it's not shared between objects
    fsm: FSMEngine = field(default_factory=lambda: FSMEngine(WORKSTREAM_TRANSITIONS), init=False, repr=False)

    def update_slots(self, new_entities: Dict[str, Any]) -> None:
        """Merge new_entities into slots. Keep 'specifications' as a dict if provided."""
        if not new_entities:
            return
        for k, v in new_entities.items():
            if k == "specifications" and isinstance(v, dict):
                self.slots.setdefault("specifications", {})
                # merge keys, latest wins
                self.slots["specifications"].update(v)
            else:
                # store scalar or structured values directly
                self.slots[k] = v

    def _state_value(self, s: Union[WorkstreamState, str]) -> str:
        """Return plain string value for Enum or str inputs."""
        try:
            return s.value if hasattr(s, "value") else str(s)
        except Exception:
            return str(s)

    def update_status(self, target_state: Union[WorkstreamState, str]) -> bool:
        """
        Attempt to transition state using the FSM.
        Returns True on success, raises ValueError on invalid transition.
        """
        current = self._state_value(self.state)
        target = self._state_value(target_state)

        if self.fsm.can_transition(current, target):
            # preserve original type if it's an Enum, else keep string
            self.state = target_state
            return True

        raise ValueError(f"Invalid transition: {current} → {target}")
