# core/conversation_history.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Union

from marshmallow.fields import Boolean

from agents.base import Ask
from config.enums import WorkstreamState, MsgTypes, Agents, WorkflowContinuityDecision as WfCDecision
from core import workstream
from core.workstream import Workstream
import uuid

@dataclass
class ConversationHistory:
    workstreams: Dict[str, Workstream] = field(default_factory=dict)
    active_ws_id: Optional[str] = None
    pending_ws_ids: List[str] = field(default_factory=list)
    completed_ws_ids: List[str] = field(default_factory=list)
    session_id = None

    def get_active_workstream(self) -> Workstream | None:
        if self.active_ws_id:
            return self.workstreams[self.active_ws_id]
        return None

    def get_all_workstreams(self) -> Dict[str, Workstream] | None:
        return self.workstreams

    def update_active_ws_id(self, ws_id: str, is_completed: Boolean = False) -> None:
        if is_completed:
            self.workstreams[self.active_ws_id].current_state = WorkstreamState.COMPLETED
            self.completed_ws_ids.append(self.active_ws_id)
        self.active_ws_id = ws_id
        self.pending_ws_ids = self.get_pending_ws_ids()
        return

    def create_ws_id(self):
        """
        Note: We are not using uuid to generate workstream_ids because ws_id will be the part of LLM prompt.
        uuid generates unique ids which are very long. Keeping ws_id in format ws_1, ws_2, ws_3 ...
        short ws_id will be easy for LLM to match (used in planer prompt).
        """
        # ws_id = uuid.uuid4()
        ws_id_int_part_list = [ws_id.split("_")[-1] for ws_id in list(self.workstreams.keys())]
        ws_id_int_part_list.sort()
        if ws_id_int_part_list:
            return "ws_id_" + str(ws_id_int_part_list[-1])
        else:
            # First Workstream
            return "ws_id_1"

    def create_new_workstream(self, phase, target) -> workstream.Workstream:
        ws_id = self.create_ws_id()
        current_state = WorkstreamState.NEW
        ws = Workstream(ws_id, current_state, phase, target)
        self.workstreams[ws_id] = ws
        return ws

    def add_chat_in_ws(self, ws_id: str, msg_type: str, message: str) -> bool:
        """
        A sample chats looks like this:
        chats = {
        ws_id: [{MsgTypes.user: "", MsgTypes.ai_message: ""}]
        }
        """
        if ws_id not in self.workstreams:
            raise Exception(f"Workstream {ws_id} does not exist")

        if msg_type == MsgTypes.user:
            chats = self.workstreams[ws_id].chats
            chats.append({MsgTypes.user: message, MsgTypes.ai_message: None})
            return True

        elif msg_type == MsgTypes.ai_message:
            chats = self.workstreams[ws_id].chats
            if not chats:
                raise Exception("Cannot add AI message before a user message")
            if MsgTypes.user not in chats[-1].keys():
                raise Exception("Cannot add AI message before a user message")
            if MsgTypes.ai_message in chats[-1].keys():
                if chats[-1][MsgTypes.ai_message] is None:
                    chats[-1][MsgTypes.ai_message] = message
                return True
        return False

    def get_pending_ws_ids(self) -> List[str]:
        pending_ws_ids = []
        for ws_id, ws in self.workstreams.items():
            if ws.current_state not in [WorkstreamState.COMPLETED] and ws_id not in [self.active_ws_id]:
                pending_ws_ids.append(ws_id)
        return pending_ws_ids







