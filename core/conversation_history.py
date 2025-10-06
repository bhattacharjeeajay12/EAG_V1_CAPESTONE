# core/conversation_history.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

from core.workstream import Workstream
from core.state_factory import initial_state
from config.enums import WorkstreamState
from agents.base import Ask
from config.constants import MAX_TURNS_TO_PULL

@dataclass
class ConversationHistory:
    turns: List[Dict[str, Any]] = field(default_factory=list)
    workstreams: Dict[str, Workstream] = field(default_factory=dict)
    focus_id: Optional[str] = None
    pending_asks: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ws_id -> {"slot": str, "prompt": str}
    pending_decision: Optional[Dict[str, Any]] = None

    # ---- NLU context helpers ----
    def as_nlu_context(self) -> List[Dict[str, str]]:
        """
        Return the last up-to-5 turns as a minimal context list suitable for NLU prompts.
        Preserves order oldest -> newest.
        """
        recent = self.turns[-MAX_TURNS_TO_PULL:]
        return [{"role": t["role"], "content": t.get("content", "")} for t in recent]

    # ---- Turn history helpers ----
    def append_user_turn(self, content: str, nlu_result: Dict[str, Any]) -> None:
        self.turns.append({"role": "user", "content": content, "nlu_result": nlu_result})

    def append_action(self, action: Any) -> None:
        """
        Append an assistant action to the conversation turns.
        Uses Ask.question when available; otherwise falls back to common fields or repr.
        """
        if isinstance(action, Ask):
            text = getattr(action, "question", None) or getattr(action, "text", None) or repr(action)
        else:
            text = getattr(action, "text", None) or getattr(action, "message", None) or repr(action)
        self.turns.append({"role": "assistant", "content": text, "action": action})

    # ---- Workstream lifecycle ----
    def ensure_workstream(self, intent: str, seed_entities: Dict[str, Any]) -> Workstream:
        """
        Create a new workstream for a given intent (or return existing focused one).
        Sets focus to the new workstream.
        """
        ws_id = f"ws_{len(self.workstreams) + 1}"
        init_state = initial_state(intent)
        ws = Workstream(id=ws_id, state=state, phase=init_state, slots={})
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
        if not ws:
            return
        # Use a stable string to indicate paused (keeps compatibility with prior code)
        ws.status = "paused"

    def resume_workstream(self, ws_id: str) -> None:
        ws = self.workstreams.get(ws_id)
        if not ws:
            return
        # Best-effort: set to COLLECTING state for known intents, otherwise active
        if getattr(ws, "type", None) == "DISCOVERY":
            ws.status = WorkstreamState.COLLECTING
        elif getattr(ws, "type", None) == "ORDER":
            ws.status = WorkstreamState.COLLECTING
        else:
            ws.status = "active"
        self.focus_id = ws_id

    # ----- Pending Ask helpers -----
    def set_pending_ask(self, ws_id: str, slot: Optional[str], prompt: str) -> None:
        self.pending_asks[ws_id] = {"slot": slot, "prompt": prompt}

    def clear_pending_ask(self, ws_id: str) -> None:
        if ws_id in self.pending_asks:
            del self.pending_asks[ws_id]

    def find_any_pending_ask(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Return the first pending ask as (ws_id, info) or None.
        (Deterministic but arbitrary order due to dict iteration; OK for single pending ask case.)
        """
        it = iter(self.pending_asks.items())
        try:
            return next(it)
        except StopIteration:
            return None

    # ----- Continuity decision helpers -----
    def set_pending_decision(self, payload: Dict[str, Any]) -> None:
        self.pending_decision = payload

    def get_pending_decision(self) -> Optional[Dict[str, Any]]:
        return self.pending_decision

    def clear_pending_decision(self) -> None:
        self.pending_decision = None

    # ----- Snapshot for debugging / UI -----
    def _serialize_ws(self, ws: Workstream) -> Dict[str, Any]:
        """Return a JSON-serializable summary of a workstream."""
        state = getattr(ws.state, "value", ws.state)
        return {
            "id": ws.id,
            "type": getattr(ws, "type", None),
            "status": state,
            "slots": ws.slots,
            "candidates_count": len(getattr(ws, "candidates", []) or []),
            "has_pending_ask": ws.id in self.pending_asks,
        }

    def session_snapshot(self) -> Dict[str, Any]:
        return {
            "turns": self.turns[-20:],
            "workstreams": {wid: self._serialize_ws(ws) for wid, ws in self.workstreams.items()},
            "focus_id": self.focus_id,
            "pending_asks": self.pending_asks,
            "pending_decision": self.pending_decision,
        }
