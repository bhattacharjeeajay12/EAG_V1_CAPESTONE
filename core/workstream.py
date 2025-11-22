# core/workstream.py
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List
from config.enums import WorkstreamState
from core.fsm_engine import FSMEngine
from core.fsm_rules import WORKSTREAM_TRANSITIONS
from config.enums import Agents

@dataclass
class Workstream:
    id: str
    current_state: Union[WorkstreamState, str]
    current_phase: Union[Agents, str]
    target_entities: Dict[str, Any] = field(default_factory=dict)
    first_phase: str = None
    chats: List[Dict[str, Any]] = field(default_factory=list)
    # Make FSM an instance attribute so it's not shared between objects
    fsm: FSMEngine = field(default_factory=lambda: FSMEngine(WORKSTREAM_TRANSITIONS), init=False, repr=False)
    specification_list: List[Dict[str, Any]] = field(default_factory=list)

    def get_workstream_id(self):
        return self.id

    def get_state(self):
        return self.current_state

    def get_phase(self):
        return self.current_phase

    def get_target_entity(self):
        return self.target_entities
    def get_chats(self):
        return self.chats

    def update_status(self, target_state: Union[WorkstreamState, str]) -> bool:
        """
        Attempt to transition state using the FSM.
        Returns True on success, raises ValueError on invalid transition.
        """

        if self.fsm.can_transition(self.current_state, target_state):
            # preserve original type if it's an Enum, else keep string
            self.current_state = target_state
            return True
        else:
            raise ValueError(f"Invalid transition: {self.current_state} → {target_state}")
