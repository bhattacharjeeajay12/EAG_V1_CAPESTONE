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
    Centralized session memory for the Planner Agent.

    - Only the Planner Agent uses this memory system
    - Individual agents (BUY, ORDER, RECOMMEND, RETURN) are stateless
    - Stores complete conversation flow, NLU analyses, and routing decisions
    - One JSON file per session under memory/sessions/{session_id}.json
    """

    def __init__(self, base_memory_dir: Optional[str] = None) -> None:
        """
        Initialize session memory for planner.

        Args:
            base_memory_dir (str, optional): Base directory for memory storage
        """
        self.base_memory_dir = base_memory_dir or _project_path("memory")
        self.sessions_dir = os.path.join(self.base_memory_dir, "sessions")

        # Current session tracking
        self.session_id: Optional[str] = None
        self.session_label: Optional[str] = None
        self.created_at: Optional[str] = None
        self.updated_at: Optional[str] = None

        # Ensure sessions directory exists
        os.makedirs(self.sessions_dir, exist_ok=True)

    def _session_path(self) -> Optional[str]:
        """Get the file path for current session."""
        if not self.session_id:
            return None
        return os.path.join(self.sessions_dir, f"{self.session_id}.json")

    def new_session(self, session_label: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new session and create initial memory file.

        Args:
            session_label (str, optional): Human-readable label for the session
            config (Dict, optional): Initial configuration

        Returns:
            str: Generated session ID
        """
        # Generate unique session ID
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        unique_id = uuid.uuid4().hex[:8]
        self.session_id = f"{timestamp}_{unique_id}"

        self.session_label = session_label
        now = datetime.utcnow().isoformat() + "Z"
        self.created_at = now
        self.updated_at = now

        # Create initial session document
        initial_data = {
            "conversation_history": [],
            "session_state": {
                "session_id": self.session_id,
                "started_at": self.created_at,
                "current_agent": None,
                "user_journey": "initial",
                "entities": {},
                "completion_status": "active"
            },
            "nlu_history": [],
            "routing_history": [],
            "config": config or {}
        }

        self._save_session_data(initial_data)
        return self.session_id

    def save(self,
             conversation_history: List[Dict[str, Any]],
             session_state: Dict[str, Any],
             nlu_history: Optional[List[Dict[str, Any]]] = None,
             routing_history: Optional[List[Dict[str, Any]]] = None,
             config: Optional[Dict[str, Any]] = None) -> None:
        """
        Save complete session data.

        Args:
            conversation_history (List): Complete conversation history
            session_state (Dict): Current session state
            nlu_history (List, optional): NLU analysis history
            routing_history (List, optional): Routing decision history
            config (Dict, optional): Session configuration
        """
        if not self.session_id:
            return

        self.updated_at = datetime.utcnow().isoformat() + "Z"

        session_data = {
            "conversation_history": conversation_history,
            "session_state": session_state,
            "nlu_history": nlu_history or [],
            "routing_history": routing_history or [],
            "config": config or {}
        }

        self._save_session_data(session_data)

    def _save_session_data(self, session_data: Dict[str, Any]) -> None:
        """
        Save session data to file.

        Args:
            session_data (Dict): Complete session data to save
        """
        path = self._session_path()
        if not path:
            return

        # Build complete document
        document = {
            "session_id": self.session_id,
            "label": self.session_label,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            **session_data
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(document, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save session memory to {path}: {e}")

    def load_session(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load session data from file.

        Args:
            session_id (str, optional): Session ID to load. If None, loads current session.

        Returns:
            Dict: Complete session data or None if not found
        """
        target_session_id = session_id or self.session_id
        if not target_session_id:
            return None

        session_path = os.path.join(self.sessions_dir, f"{target_session_id}.json")

        if not os.path.exists(session_path):
            return None

        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # If loading current session, update instance variables
            if session_id is None or session_id == self.session_id:
                self.session_id = data.get("session_id")
                self.session_label = data.get("label")
                self.created_at = data.get("created_at")
                self.updated_at = data.get("updated_at")

            return data
        except Exception as e:
            print(f"[WARN] Failed to load session memory from {session_path}: {e}")
            return None

    def add_conversation_turn(self, role: str, content: str,
                              nlu_analysis: Optional[Dict] = None,
                              routing_decision: Optional[Dict] = None) -> None:
        """
        Add a single conversation turn with associated NLU and routing data.

        Args:
            role (str): Role (user, agent, system)
            content (str): Message content
            nlu_analysis (Dict, optional): NLU analysis for this turn
            routing_decision (Dict, optional): Routing decision for this turn
        """
        if not self.session_id:
            return

        # Load current session data
        current_data = self.load_session() or {
            "conversation_history": [],
            "nlu_history": [],
            "routing_history": [],
            "session_state": {},
            "config": {}
        }

        # Add conversation turn
        conversation_turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        current_data["conversation_history"].append(conversation_turn)

        # Add NLU analysis if provided
        if nlu_analysis:
            nlu_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "user_message": content if role == "user" else "",
                "analysis": nlu_analysis
            }
            current_data["nlu_history"].append(nlu_entry)

        # Add routing decision if provided
        if routing_decision:
            routing_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "decision": routing_decision
            }
            current_data["routing_history"].append(routing_entry)

        # Save updated data
        self._save_session_data(current_data)

    def get_context_for_agent(self, agent_type: str, max_history: int = 10) -> Dict[str, Any]:
        """
        Get relevant context for a specific agent.

        Args:
            agent_type (str): Type of agent (BUY, ORDER, RECOMMEND, RETURN)
            max_history (int): Maximum conversation entries to include

        Returns:
            Dict: Context data for the agent
        """
        session_data = self.load_session()
        if not session_data:
            return {}

        conversation_history = session_data.get("conversation_history", [])
        session_state = session_data.get("session_state", {})

        # Get recent conversation history
        recent_conversation = conversation_history[-max_history:] if conversation_history else []

        # Extract relevant entities for this agent
        entities = session_state.get("entities", {})

        return {
            "session_id": self.session_id,
            "agent_type": agent_type,
            "conversation_history": recent_conversation,
            "entities": entities,
            "user_journey": session_state.get("user_journey"),
            "current_agent": session_state.get("current_agent"),
            "session_state": session_state
        }

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List recent sessions with basic info.

        Args:
            limit (int): Maximum number of sessions to return

        Returns:
            List: Session summaries sorted by creation time (newest first)
        """
        if not os.path.exists(self.sessions_dir):
            return []

        sessions = []

        try:
            # Get all session files
            session_files = [f for f in os.listdir(self.sessions_dir) if f.endswith('.json')]

            for session_file in session_files:
                session_path = os.path.join(self.sessions_dir, session_file)
                try:
                    with open(session_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Extract summary info
                    summary = {
                        "session_id": data.get("session_id"),
                        "label": data.get("label"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "conversation_length": len(data.get("conversation_history", [])),
                        "current_agent": data.get("session_state", {}).get("current_agent"),
                        "user_journey": data.get("session_state", {}).get("user_journey"),
                        "status": data.get("session_state", {}).get("completion_status")
                    }
                    sessions.append(summary)

                except Exception as e:
                    print(f"[WARN] Failed to read session file {session_file}: {e}")
                    continue

            # Sort by creation time (newest first) and limit
            sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return sessions[:limit]

        except Exception as e:
            print(f"[WARN] Failed to list sessions: {e}")
            return []