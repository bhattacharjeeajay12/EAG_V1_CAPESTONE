# core/schema.py
"""
Standard result schemas for the planner system.
Provides consistent data structures for agent results and system responses.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime


def make_result(agent: str, status: str,
                proposed_next: Optional[List[str]] = None,
                changes: Optional[Dict[str, Any]] = None,
                error: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a standardized result dictionary.

    Args:
        agent: Name of the agent/component that generated this result
        status: Status of the operation (SUCCESS, FAILED, NEEDS_INFO, etc.)
        proposed_next: List of proposed next steps/nodes
        changes: Dictionary of changes to merge into world state
        error: Error message if status is FAILED
        metadata: Additional metadata about the result

    Returns:
        Standardized result dictionary
    """
    return {
        "agent": agent,
        "status": status,
        "proposed_next": proposed_next or [],
        "changes": changes or {},
        "error": error,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat()
    }


def validate_result(result: Dict[str, Any]) -> bool:
    """
    Validate that a result dictionary has the expected structure.

    Args:
        result: Result dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["agent", "status", "proposed_next", "changes"]

    for field in required_fields:
        if field not in result:
            return False

    # Validate types
    if not isinstance(result["proposed_next"], list):
        return False

    if not isinstance(result["changes"], dict):
        return False

    return True


class PlannerResult:
    """
    Structured result class for planner operations.
    Provides type safety and validation for planner results.
    """

    def __init__(self, steps: List[Dict[str, Any]],
                 final_state: Dict[str, Any],
                 goal: str,
                 success: bool = True,
                 total_steps: int = 0,
                 error: Optional[str] = None):
        self.steps = steps
        self.final_state = final_state
        self.goal = goal
        self.success = success
        self.total_steps = total_steps
        self.error = error
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "steps": self.steps,
            "final_state": self.final_state,
            "goal": self.goal,
            "success": self.success,
            "total_steps": self.total_steps,
            "error": self.error,
            "created_at": self.created_at
        }

    def get_last_step(self) -> Optional[Dict[str, Any]]:
        """Get the last executed step."""
        return self.steps[-1] if self.steps else None

    def get_agent_steps(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all steps executed by a specific agent."""
        return [step for step in self.steps
                if step.get("result", {}).get("agent") == agent_name]

    def was_successful(self) -> bool:
        """Check if the planning was successful."""
        return self.success and not self.error