# core/workstream.py
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List
from config.enums import WorkstreamState
from core.fsm_engine import FSMEngine
from core.fsm_rules import PHASE_TRANSITIONS
from config.enums import Agents, ChatInfo
from agents.DiscoveryAgent import DiscoveryAgent
import uuid

@dataclass
class Workstream:
    id: str
    current_state: Union[WorkstreamState, str]
    current_phase: str
    first_phase: Union[Agents, str]
    target: Dict[str, Any] = field(default_factory=dict)
    chats: List[Dict[str, Any]] = field(default_factory=list)
    processing: Dict[str, Any] = field(default_factory=dict)
    # Make FSM an instance attribute so it's not shared between objects
    fsm: FSMEngine = field(default_factory=lambda: FSMEngine(PHASE_TRANSITIONS), init=False, repr=False)
    specification_list: List[Dict[str, Any]] = field(default_factory=list)
    specification_Ask: bool = field(default=True, init=True, repr=True)
    all_phases: Dict[str, Any] = field(default_factory=dict)

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

    def add_chat_in_ws(self, msg_type: str, message: str) -> bool:
        """
        A sample chats looks like this:
        chats = {
        ws_id: [{ChatInfo.user_message: "", ChatInfo.ai_message: ""}]
        }
        """
        if msg_type == ChatInfo.user_message:
            # chats = self.workstreams[ws_id].chats
            self.chats.append({ChatInfo.chat_id: uuid.uuid4(),
                          ChatInfo.user_message: message,
                          ChatInfo.ai_message: None,
                          ChatInfo.msg_source: None})
            return True

        elif msg_type == ChatInfo.ai_message:
            # chats = self.workstreams[ws_id].chats
            if not self.chats:
                raise Exception("Cannot add AI message before a user message")
            if ChatInfo.user_message not in self.chats[-1].keys():
                raise Exception("Cannot add AI message before a user message")
            if ChatInfo.ai_message in self.chats[-1].keys():
                if self.chats[-1][ChatInfo.ai_message] is None:
                    self.chats[-1][ChatInfo.ai_message] = message
                    self.chats[-1][ChatInfo.msg_source] = self.current_phase
                return True
        return False
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

    async def run(self, user_query: str) -> str|None:
        if self.current_phase == Agents.DISCOVERY:
            self.add_chat_in_ws(ChatInfo.user_message, user_query)
            subcategory = self.target.get("subcategory")
            if self.current_phase not in self.all_phases:
                discovery_phase = DiscoveryAgent(subcategory=subcategory)
                self.all_phases[self.current_phase] = discovery_phase
            discovery_phase = self.all_phases.get(self.current_phase)

            # Step 1. Gather specification using Discovery NLU
            d_output = await discovery_phase.run(user_query, self.specification_list, self.specification_Ask)
            self.specification_Ask = False  # Only it will ask for specs once.
            if type(d_output) == str: # AI response
                self.add_chat_in_ws(ChatInfo.ai_message, d_output)
                return d_output
            else:
                # Step 1. Gather specification using Discovery NLU

                pass
        return None