
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid

@dataclass
class Workstream:
    id: str
    type: str  # DISCOVERY|ORDER|RETURN|EXCHANGE|PAYMENT|CHITCHAT
    status: str = "collecting"
    slots: Dict[str, Any] = field(default_factory=dict)
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    compare: Dict[str, Any] = field(default_factory=lambda: {"left": None, "right": None})
    next_needed_slot: Optional[str] = None
    satisfaction: float = 0.0
    history: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class LastPresented:
    ws_id: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    selected_id: Optional[str] = None

@dataclass
class Focus:
    active_ws_id: Optional[str] = None
    stack: List[str] = field(default_factory=list)

class ConversationHistory:
    def __init__(self):
        self.workstreams: Dict[str, Workstream] = {}
        self.focus = Focus()
        self.last_presented = LastPresented()
        self._conversation_log: List[Dict[str, Any]] = []

    def as_nlu_context(self) -> List[Dict[str, Any]]:
        ctx: List[Dict[str, Any]] = []
        user_msgs = [t for t in self._conversation_log if t.get("role") == "user"]
        for m in user_msgs[-3:]:
            ctx.append({"role": "user", "content": m.get("content")})
        if self.focus.active_ws_id:
            ws = self.workstreams[self.focus.active_ws_id]
            ctx.append({
                "role": "assistant",
                "nlu_result": {
                    "current_turn": {"intent": ws.type, "entities": ws.slots}
                }
            })
        return ctx

    def session_snapshot(self) -> Dict[str, Any]:
        return {"workstreams": {wid: ws for wid, ws in self.workstreams.items()},
                "focus": self.focus, "last_presented": self.last_presented}

    def get_focused_ws(self) -> Optional[Workstream]:
        wid = self.focus.active_ws_id
        return self.workstreams.get(wid) if wid else None

    def ensure_workstream(self, intent: str, seed_entities: Dict[str, Any]) -> Workstream:
        ws = Workstream(id=str(uuid.uuid4()), type=intent, slots=seed_entities or {})
        self.workstreams[ws.id] = ws
        self.focus.active_ws_id = ws.id
        return ws

    def append_user_turn(self, content: str, nlu_result: Dict[str, Any]):
        self._conversation_log.append({"role": "user", "content": content, "nlu_result": nlu_result})

    def append_action(self, action: Any):
        self._conversation_log.append({"role": "assistant", "action": repr(action)})

    def apply_continuity(self, intent: str, entities: Dict[str, Any], continuity: Dict[str, Any]):
        ctype = continuity.get("continuity_type", "CONTINUATION")
        options = continuity.get("context_switch_options") or []

        if ctype == "INTENT_SWITCH":
            self.ensure_workstream(intent, seed_entities=entities)
            return

        focused = self.get_focused_ws()
        if not focused:
            self.ensure_workstream(intent, seed_entities=entities)
            return

        if ctype == "CONTINUATION":
            for k, v in (entities or {}).items():
                if v not in (None, "", [], {}):
                    focused.slots[k] = v
            return

        if ctype == "ADDITION":
            self.focus.stack.append(self.focus.active_ws_id)
            self.ensure_workstream(intent, seed_entities=entities)
            return

        if ctype == "CONTEXT_SWITCH":
            if "REPLACE" in options:
                keep_keys = {"preferences", "quantity"}
                new_slots = {k: v for k, v in focused.slots.items() if k in keep_keys}
                for k, v in (entities or {}).items():
                    if v not in (None, "", [], {}):
                        new_slots[k] = v
                focused.slots = new_slots
                focused.status = "collecting"
                return

            if "ADD" in options:
                self.ensure_workstream(focused.type, seed_entities=entities)
                return

            if "COMPARE" in options:
                left = focused.compare.get("left")
                right = focused.compare.get("right")
                cmp_items = (entities or {}).get("comparison_items") or []
                for item in cmp_items:
                    if not left:
                        left = item
                    elif not right:
                        right = item
                focused.compare["left"] = left
                focused.compare["right"] = right
                focused.status = "collecting"
                return

            if "SEPARATE" in options:
                if self.focus.active_ws_id:
                    self.focus.stack.append(self.focus.active_ws_id)
                self.ensure_workstream(intent, seed_entities=entities)
                return

    def apply_agent_output(self, output):
        ws = self.get_focused_ws()
        if not ws:
            return
        for k, v in (output.updated_slots or {}).items():
            if v is not None:
                ws.slots[k] = v
        if output.presented_items is not None:
            ws.candidates = output.presented_items
            self.last_presented.ws_id = ws.id
            self.last_presented.items = output.presented_items
        if output.satisfaction_delta:
            ws.satisfaction = max(0.0, min(1.0, ws.satisfaction + output.satisfaction_delta))
        if output.mark_completed:
            ws.status = "completed"
            if self.focus.stack:
                self.focus.active_ws_id = self.focus.stack.pop()
