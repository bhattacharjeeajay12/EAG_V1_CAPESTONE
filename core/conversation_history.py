
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from core.workstream import Workstream
from core.state_factory import initial_state
from core.states import DiscoveryState, OrderState

@dataclass
class ConversationHistory:
    turns: List[Dict[str, Any]] = field(default_factory=list)
    workstreams: Dict[str, Workstream] = field(default_factory=dict)
    focus_id: Optional[str] = None
    pending_asks: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ws_id -> {"slot": str, "prompt": str}
    pending_decision: Optional[Dict[str, Any]] = None

    def as_nlu_context(self) -> List[Dict[str, str]]:
        ctx = []
        for t in self.turns[-5:]:
            ctx.append({"role": t["role"], "content": t.get("content", "")})
        return ctx

    def append_user_turn(self, content: str, nlu_result: Dict[str, Any]):
        self.turns.append({"role": "user", "content": content, "nlu_result": nlu_result})

    def append_action(self, action: Any):
        # Prefer Ask.question; fallback to common fields; else repr
        if getattr(action, "type", None) == "ask" or action.__class__.__name__ == "Ask":
            text = getattr(action, "question", None) or getattr(action, "text", None) or getattr(action, "prompt", None) or repr(action)
        else:
            text = getattr(action, "text", None) or getattr(action, "message", None) or repr(action)
        self.turns.append({"role": "assistant", "content": text, "action": action})

    def ensure_workstream(self, intent: str, seed_entities: Dict[str, Any]) -> Workstream:
        # Create a new WS id
        ws_id = f"ws_{len(self.workstreams)+1}"
        init_state = initial_state(intent)
        ws = Workstream(id=ws_id, type=intent, status=init_state)
        if seed_entities:
            ws.update_slots(seed_entities)
        self.workstreams[ws_id] = ws
        self.focus_id = ws_id
        return ws

    def get_focused_ws(self) -> Optional[Workstream]:
        return self.workstreams.get(self.focus_id) if self.focus_id else None

    def set_focus(self, ws_id: str) -> None:
        if ws_id in self.workstreams:
            self.focus_id = ws_id

    def pause_workstream(self, ws_id: str) -> None:
        ws = self.workstreams.get(ws_id)
        if ws:
            # keep string 'paused' for backwards compatibility in checks
            ws.status = "paused"

    def resume_workstream(self, ws_id: str) -> None:
        ws = self.workstreams.get(ws_id)
        if ws:
            # best effort: go to COLLECTING state for known enums
            if ws.type == "DISCOVERY":
                ws.status = DiscoveryState.COLLECTING
            elif ws.type == "ORDER":
                ws.status = OrderState.COLLECTING
            else:
                ws.status = "active"
            self.focus_id = ws_id

    # ----- Pending Ask helpers -----
    def set_pending_ask(self, ws_id: str, slot: Optional[str], prompt: str) -> None:
        self.pending_asks[ws_id] = {"slot": slot, "prompt": prompt}

    def clear_pending_ask(self, ws_id: str) -> None:
        if ws_id in self.pending_asks:
            del self.pending_asks[ws_id]

    def find_any_pending_ask(self):
        # returns (ws_id, info) or None
        return next(iter(self.pending_asks.items()), None)

    # ----- Continuity decision helpers -----
    def set_pending_decision(self, payload: Dict[str, Any]) -> None:
        self.pending_decision = payload

    def get_pending_decision(self) -> Optional[Dict[str, Any]]:
        return self.pending_decision

    def clear_pending_decision(self) -> None:
        self.pending_decision = None

    # ----- Snapshot for debugging -----
    def session_snapshot(self) -> Dict[str, Any]:
        return {
            "turns": self.turns[-20:],
            "workstreams": self.workstreams,
            "focus_id": self.focus_id,
            "pending_asks": self.pending_asks,
            "pending_decision": self.pending_decision,
        }
