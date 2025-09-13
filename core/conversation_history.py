# conversation_history.py
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid
from core.workstream import Workstream
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
        # pending_decision used earlier for continuity confirm flows
        self.pending_decision: Optional[Dict[str, Any]] = None
        # pending_asks maps workstream_id -> { "slot": str|None, "prompt": str }
        self.pending_asks: Dict[str, Dict[str, Any]] = {}

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
        ws = Workstream(id=str(uuid.uuid4()), type=intent.upper(), status=initial_state(intent), slots=seed_entities or {})
        self.workstreams[ws.id] = ws
        self.focus.active_ws_id = ws.id
        return ws

    # --- Multi-workstream helpers ---
    def list_workstreams(self) -> List[Workstream]:
        return list(self.workstreams.values())

    def list_by_status(self, statuses: List[str]) -> List[Workstream]:
        return [ws for ws in self.workstreams.values() if getattr(ws, "status") in statuses]

    def pause_workstream(self, ws_id: str):
        ws = self.workstreams.get(ws_id)
        if ws:
            ws.status = "paused"
            if self.focus.active_ws_id == ws_id:
                self.focus.active_ws_id = None

    def abandon_workstream(self, ws_id: str):
        ws = self.workstreams.get(ws_id)
        if ws:
            ws.status = "abandoned"
            if self.focus.active_ws_id == ws_id:
                self.focus.active_ws_id = None
            # clear any pending asks for abandoned ws
            self.pending_asks.pop(ws_id, None)

    def resume_workstream(self, ws_id: str) -> Optional[Workstream]:
        ws = self.workstreams.get(ws_id)
        if ws and getattr(ws, "status") == "paused":
            ws.status = "active"
            self.focus.active_ws_id = ws_id
            return ws
        return None

    def find_workstream_by_target(self, type: str, target: Dict[str, Any]) -> Optional[Workstream]:
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

    # --- Pending decision helpers (continuity) ---
    def set_pending_decision(self, decision: Dict[str, Any]):
        self.pending_decision = decision

    def clear_pending_decision(self):
        self.pending_decision = None

    def get_pending_decision(self) -> Optional[Dict[str, Any]]:
        return self.pending_decision

    # --- Pending ask helpers (new) ---
    def set_pending_ask(self, ws_id: str, slot: Optional[str], prompt: str):
        """
        Register that an agent asked the user for `slot` in workstream `ws_id`.
        slot may be None if the Ask is free-form (no explicit slot).
        """
        self.pending_asks[ws_id] = {"slot": slot, "prompt": prompt}

    def get_pending_ask_for_ws(self, ws_id: str) -> Optional[Dict[str, Any]]:
        return self.pending_asks.get(ws_id)

    def find_any_pending_ask(self) -> Optional[tuple]:
        """
        Return (ws_id, ask_dict) for any pending ask, preferring focused ws if present.
        """
        if not self.pending_asks:
            return None
        # prefer focused ws
        focused = self.focus.active_ws_id
        if focused and focused in self.pending_asks:
            return focused, self.pending_asks[focused]
        # else return arbitrary pending ask (first)
        for k, v in self.pending_asks.items():
            return k, v
        return None

    def clear_pending_ask(self, ws_id: str):
        self.pending_asks.pop(ws_id, None)

    # Conversation log helpers
    def append_user_turn(self, content: str, nlu_result: Dict[str, Any]):
        self._conversation_log.append({"role": "user", "content": content, "nlu_result": nlu_result})

    def append_action(self, action: Any):
        # store representation; if Ask, also helpful to store prompt
        entry = {"role": "assistant", "action": repr(action)}
        try:
            entry["text"] = getattr(action, "text", "") or getattr(action, "prompt", "")
        except Exception:
            entry["text"] = ""
        self._conversation_log.append(entry)
