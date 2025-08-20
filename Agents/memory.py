import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


class SessionMemory:
    """
    A reusable session memory manager for agent conversations.

    Responsibilities:
    - Manage session identity (session_id), labels, and timestamps.
    - Persist conversation state in JSON under DB\memory\{agent_name}\{session_id}.json.
    - Keep the JSON schema stable and consistent with prompts:
      {
        "session_id": str,
        "agent": str,
        "label": Optional[str],
        "created_at": ISO-8601 UTC string,
        "updated_at": ISO-8601 UTC string,
        "chat_history": List[Dict[str, str]] (NEWEST-first),
        "perceptions_history": List[Dict[str, Any]] (NEWEST-first),
        "perceptions": Dict[str, Any],
        "last_agent_state": Dict[str, Any],
        "config": Dict[str, Any]
      }
    """
import os
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


class SessionMemory:
    """
    Manages session-based memory storage for agents.
    Creates and updates JSON files that store conversation state and other metadata.
    """

    def __init__(self, agent_name: str, base_dir: Optional[str] = None):
        """
        Initialize the session memory manager.

        :param agent_name: Name of the agent (used for directory structure)
        :param base_dir: Base directory for memory storage (default: "../Memory")
        """
        self.agent_name = agent_name
        if base_dir is None:
            # Default to a Memory directory at the project root
            # Assume this file is in Agents/ subdirectory
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            base_dir = os.path.join(base, "Memory")
        self.base_dir = base_dir
        self.agent_dir = os.path.join(self.base_dir, self.agent_name)
        os.makedirs(self.agent_dir, exist_ok=True)
        self.session_id = None
        self.session_path = None

    def new_session(self, label: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new session with a unique ID.

        :param label: Optional human-readable label for the session
        :param config: Optional configuration parameters to store
        :return: The new session ID
        """
        # Generate a timestamp-based session ID
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        uuid_part = uuid.uuid4().hex[:8]  # Use 8 chars from a UUID for uniqueness
        self.session_id = f"{timestamp}_{uuid_part}"

        # Create the session directory
        self.session_path = os.path.join(self.agent_dir, self.session_id)
        os.makedirs(self.session_path, exist_ok=True)

        # Initialize the session with minimal metadata
        session_data = {
            "session_id": self.session_id,
            "agent": self.agent_name,
            "label": label,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "config": config or {},
        }

        # Write the initial session file
        with open(os.path.join(self.session_path, "session.json"), "w", encoding="utf-8") as f:
            json.dump(session_data, indent=2, ensure_ascii=False, sort_keys=True, f=f)

        return self.session_id

    def save(self, 
             chat_history: List[Dict[str, str]], 
             perceptions_history: List[Dict[str, Any]], 
             perceptions: Dict[str, Any],
             last_agent_state: Dict[str, Any],
             config: Optional[Dict[str, Any]] = None) -> str:
        """
        Save the current state of the conversation.

        :param chat_history: List of chat messages (oldest first)
        :param perceptions_history: List of perception results (oldest first)
        :param perceptions: Current merged perceptions state
        :param last_agent_state: State from the last agent response
        :param config: Optional configuration updates
        :return: Path to the saved file
        """
        if self.session_id is None:
            self.new_session(config=config)

        # Update timestamp
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%dT%H%M%SZ")

        # Prepare the data to save
        session_data = {
            "session_id": self.session_id,
            "agent": self.agent_name,
            "created_at": None,  # Will be filled from existing file
            "updated_at": now.isoformat(),
            "chat_history": chat_history,  # Keep chronological order (oldest first)
            "perceptions_history": perceptions_history,  # Keep chronological order (oldest first)
            "perceptions": perceptions,
            "last_agent_state": last_agent_state,
            "config": config or {},
        }

        # Try to read existing file to preserve creation time
        session_file = os.path.join(self.session_path, "session.json")
        try:
            if os.path.exists(session_file):
                with open(session_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    session_data["created_at"] = existing.get("created_at")
                    session_data["label"] = existing.get("label")
        except Exception as e:
            print(f"[WARN] Error reading existing session file: {e}")
            session_data["created_at"] = now.isoformat()

        # If still missing creation time, use current time
        if not session_data["created_at"]:
            session_data["created_at"] = now.isoformat()

        # Write the updated session file
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, indent=2, ensure_ascii=False, sort_keys=True, f=f)

        # Also create a timestamped snapshot for history
        snapshot_file = os.path.join(self.session_path, f"{timestamp}.json")
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(session_data, indent=2, ensure_ascii=False, sort_keys=True, f=f)

        return snapshot_file

    def load_latest(self) -> Optional[Dict[str, Any]]:
        """
        Load the latest state for the current session.

        :return: Dictionary with the latest session state, or None if no session exists
        """
        if self.session_id is None:
            return None

        session_file = os.path.join(self.session_path, "session.json")
        if not os.path.exists(session_file):
            return None

        try:
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Error loading session file: {e}")
            return None
    def __init__(self, agent_name: str, base_memory_dir: Optional[str] = None) -> None:
        self.agent_name = agent_name
        self.base_memory_dir = base_memory_dir or _project_path("DB", "memory")
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
    def new_session(self, label: Optional[str] = None,
                    initial_chat_history: Optional[List[Dict[str, str]]] = None,
                    initial_perceptions_history: Optional[List[Dict[str, Any]]] = None,
                    initial_perceptions: Optional[Dict[str, Any]] = None,
                    initial_last_agent_state: Optional[Dict[str, Any]] = None,
                    config: Optional[Dict[str, Any]] = None) -> None:
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
            last_agent_state=initial_last_agent_state or {},
            config=config or {},
        )

    # ---------- Persistence ----------
    def _build_document(self,
                        chat_history: List[Dict[str, str]],
                        perceptions_history: List[Dict[str, Any]],
                        perceptions: Dict[str, Any],
                        last_agent_state: Dict[str, Any],
                        config: Dict[str, Any]) -> Dict[str, Any]:
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
            "last_agent_state": last_agent_state,
            "config": dict(config or {}),
        }

    def save(self,
             chat_history: List[Dict[str, str]],
             perceptions_history: List[Dict[str, Any]],
             perceptions: Dict[str, Any],
             last_agent_state: Dict[str, Any],
             config: Optional[Dict[str, Any]] = None) -> None:
        path = self._session_path()
        if not path:
            # No active session; ignore save request
            return
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        doc = self._build_document(chat_history, perceptions_history, perceptions, last_agent_state, config or {})
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save session memory to {path}: {e}")
