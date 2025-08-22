import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List


def _project_path(*parts: str) -> str:
    """Join paths relative to the project root (this file's directory)."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, *parts))


class SessionMemory:
    """
    Session memory manager for agent conversations.

    - Stores a single JSON file per session under memory\{agent}\{session_id}.json
    - Ensures stable schema and unique session IDs
    - Keeps histories newest-first in the file for easy prompt injection
    """

    def __init__(self, agent_name: str, base_memory_dir: Optional[str] = None) -> None:
        self.agent_name = agent_name
        self.base_memory_dir = base_memory_dir or _project_path("memory")
        self.session_id: Optional[str] = None
        self.label: Optional[str] = None
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None
        # Ensure agent directory exists
        os.makedirs(self._agent_dir(), exist_ok=True)

    # ---------- Paths ----------
    def _agent_dir(self) -> str:
        return os.path.join(self.base_memory_dir, self.agent_name)

    def _session_path(self) -> Optional[str]:
        if not self.session_id:
            return None
        return os.path.join(self._agent_dir(), f"{self.session_id}.json")

    # ---------- Session Lifecycle ----------
    def new_session(
        self,
        label: Optional[str] = None,
        initial_chat_history: Optional[List[Dict[str, str]]] = None,
        initial_perceptions_history: Optional[List[Dict[str, Any]]] = None,
        initial_perceptions: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Start a new session and immediately persist an initial shell document.
        Call save() on each turn to update the memory.
        """
        self.session_id = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        self.label = label
        now = datetime.utcnow().isoformat() + "Z"
        self.created_at = now
        self.updated_at = now
        # Persist an initial shell
        self.save(
            chat_history=initial_chat_history or [],
            perceptions_history=initial_perceptions_history or [],
            perceptions=initial_perceptions or {"specifications": {}, "quantity": 1},
            config=config or {},
        )

    # ---------- Persistence ----------
    def _build_document(
        self,
        chat_history: List[Dict[str, str]],
        perceptions_history: List[Dict[str, Any]],
        perceptions: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Persist NEWEST-first to match prompt input expectations
        newest_first_chat = list(reversed(chat_history))
        newest_first_perc = list(reversed(perceptions_history))
        return {
            "session_id": self.session_id,
            "agent": self.agent_name,
            "label": self.label,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chat_history": newest_first_chat,
            "perceptions_history": newest_first_perc,
            "perceptions": perceptions,
            "config": dict(config or {}),
        }

    def save(
        self,
        chat_history: List[Dict[str, str]],
        perceptions_history: List[Dict[str, Any]],
        perceptions: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        path = self._session_path()
        if not path:
            # No active session; ignore save request
            return
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        doc = self._build_document(
            chat_history, perceptions_history, perceptions, config or {}
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save session memory to {path}: {e}")

    def load_latest(self) -> Optional[Dict[str, Any]]:
        path = self._session_path()
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load session memory from {path}: {e}")
            return None
