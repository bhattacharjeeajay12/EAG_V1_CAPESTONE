# core/workstream.py
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List
from config.enums import WorkstreamState
from core.fsm_engine import FSMEngine
from core.fsm_rules import WORKSTREAM_TRANSITIONS
from config.enums import Agents
from agents import DiscoveryAgent

@dataclass
class Workstream:
    id: str
    current_state: Union[WorkstreamState, str]
    current_phase: Union[Agents, str]
    first_phase: Union[Agents, str]
    target: Dict[str, Any] = field(default_factory=dict)
    chats: List[Dict[str, Any]] = field(default_factory=list)
    processing: Dict[str, Any] = field(default_factory=dict)
    # Make FSM an instance attribute so it's not shared between objects
    fsm: FSMEngine = field(default_factory=lambda: FSMEngine(WORKSTREAM_TRANSITIONS), init=False, repr=False)
    specification_list: List[Dict[str, Any]] = field(default_factory=list)
    specification_Ask: bool = field(default=True, init=True, repr=True)

    def get_workstream_id(self):
        return self.id

    def get_state(self):
        return self.current_state

    def get_phase(self):
        return self.current_phase

    def get_target_entity(self):
        return self.target
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

    async def run(self):
        if self.current_phase == Agents.DISCOVERY:
            subcategory = self.target.get("subcategory")
            if self.specification_Ask:
                discovery_phase = DiscoveryAgent(subcategory=subcategory, specification_list=self.specification_list, specification_Ask = self.specification_Ask)
                self.specification_Ask = False
            else:
                discovery_phase = DiscoveryAgent(subcategory=subcategory, specification_list=self.specification_list)
        return