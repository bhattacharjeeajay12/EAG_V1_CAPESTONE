# core/graceful_planner.py
"""
Graceful Planner - Central Orchestrator with Intent Management

Purpose: Main orchestrator that coordinates all components to provide smooth
conversation flow with graceful intent transitions, conflict resolution, and
context preservation. This is the "brain" that makes routing decisions and
manages the overall conversation flow.

Key Responsibilities:
- Coordinate user input processing through NLU → Intent Tracker → Action
- Make central routing decisions based on component outputs
- Handle intent conflicts with appropriate clarification
- Manage plan creation and execution based on current facts
- Preserve context across intent transitions and plan changes
- Provide unified response generation

Flow: User Message → NLU → Intent Tracker → Plan Decision → Action Execution
"""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum
from core.enhanced_nlu import EnhancedNLU
from core.intent_tracker import IntentTracker, ContinuityAnalysis, ContinuityType
from core.context_manager import ContextManager

import networkx as nx
from datetime import datetime
import json
from core.llm_client import LLMClient
from prompts.planner_prompt import PLANNER_SYSTEM_PROMPT


class PlannerState(Enum):
    """States of the planner during conversation processing."""
    READY = "ready"  # Ready to process user input
    PROCESSING_NLU = "processing_nlu"  # Analyzing user message
    ANALYZING_INTENT = "analyzing_intent"  # Checking intent continuity
    WAITING_CLARIFICATION = "waiting_clarification"  # Waiting for user clarification
    EXECUTING_PLAN = "executing_plan"  # Executing current plan
    COMPLETED = "completed"  # Conversation completed
    ERROR = "error"  # Error state


@dataclass
class PlanStep:
    """Represents a step in the execution plan."""
    step_id: str
    step_type: str  # "clarify", "agent_call", "system_action"
    description: str
    required_facts: List[str]
    expected_outputs: List[str]
    agent_type: Optional[str] = None
    completed: bool = False

