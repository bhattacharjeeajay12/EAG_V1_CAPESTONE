# conversation_history.py
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.workstream import Workstream
import uuid
from core.states import DiscoveryState
from core.state_factory import initial_state

@dataclass
class Focus:
    active_ws_id: Optional[str] = None
    stack: List[str] = field(default_factory=list)

class ConversationHistory:
    def __init__(self):
        self.workstreams: Dict[str, Workstream] = {}
        self.focus = Focus()
        self._conversation_log: List[Dict[str, Any]] = []
        # pending decision holds continuity/workstream_decision when planner asked for clarification.
        # It should be applied or cleared once the user clarifies.
        self.pending_decision: Optional[Dict[str, Any]] = None

    def as_nlu_context(self) -> List[Dict[str, Any]]:
        ctx: List[Dict[str, Any]] = []
        user_msgs = [t for t in self._conversation_log if t.get("role") == "user"]
        for m in user_msgs[-3:]:
            ctx.append({"role": "user", "content": m.get("content")})
        return ctx

    def session_snapshot(self) -> Dict[str, Any]:
        return {
            "workstreams": {wid: ws for wid, ws in self.workstreams.items()},
            "focus": self.focus,
        }

    def get_focused_ws(self) -> Optional[Workstream]:
        wid = self.focus.active_ws_id
        return self.workstreams.get(wid) if wid else None

    def set_focus(self, ws_id: Optional[str]):
        self.focus.active_ws_id = ws_id

    def ensure_workstream(self, intent: str, seed_entities: Dict[str, Any]) -> Workstream:
        if intent == "DISCOVERY":
            status = DiscoveryState.NEW
        else:
            status = "new"  # fallback if not modeled yet

        ws = Workstream(id=str(uuid.uuid4()), type=intent, status=initial_state(intent), slots=seed_entities or {})
        self.workstreams[ws.id] = ws
        self.focus.active_ws_id = ws.id
        return ws

    # --- New helper methods for multi-workstream management ---
    def list_workstreams(self) -> List[Workstream]:
        return list(self.workstreams.values())

    def list_by_status(self, statuses: List[str]) -> List[Workstream]:
        return [ws for ws in self.workstreams.values() if getattr(ws, "status") in statuses]

    def pause_workstream(self, ws_id: str):
        ws = self.workstreams.get(ws_id)
        if ws:
            ws.status = "paused"
            # if it was focused, clear focus
            if self.focus.active_ws_id == ws_id:
                self.focus.active_ws_id = None

    def abandon_workstream(self, ws_id: str):
        ws = self.workstreams.get(ws_id)
        if ws:
            ws.status = "abandoned"
            if self.focus.active_ws_id == ws_id:
                self.focus.active_ws_id = None

    def resume_workstream(self, ws_id: str) -> Optional[Workstream]:
        ws = self.workstreams.get(ws_id)
        if ws and getattr(ws, "status") == "paused":
            ws.status = "active"
            self.focus.active_ws_id = ws_id
            return ws
        return None

    def find_workstream_by_target(self, type: str, target: Dict[str, Any]) -> Optional[Workstream]:
        """
        Find a workstream with matching type and matching slots (category/subcategory).
        Prefer paused ones first (so we can resume), then active or new.
        """
        def matches(ws: Workstream):
            slots = ws.slots or {}
            return ws.type == type and slots.get("category") == target.get("category") and slots.get("subcategory") == target.get("subcategory")

        # paused first
        for ws in self.workstreams.values():
            if getattr(ws, "status") == "paused" and matches(ws):
                return ws
        # then active/new
        for ws in self.workstreams.values():
            if getattr(ws, "status") in ("active", "new", "collecting", "ready", "presenting") and matches(ws):
                return ws
        return None

    # Pending decision helpers
    def set_pending_decision(self, decision: Dict[str, Any]):
        self.pending_decision = decision

    def clear_pending_decision(self):
        self.pending_decision = None

    def get_pending_decision(self) -> Optional[Dict[str, Any]]:
        return self.pending_decision

    # Conversation log helpers
    def append_user_turn(self, content: str, nlu_result: Dict[str, Any]):
        self._conversation_log.append({"role": "user", "content": content, "nlu_result": nlu_result})

    def append_action(self, action: Any):
        self._conversation_log.append({"role": "assistant", "action": repr(action)})
