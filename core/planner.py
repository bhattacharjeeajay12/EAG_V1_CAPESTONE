# core/planner.py
"""
Planner Agent for E-commerce System
Routes user requests to appropriate specialist agents based on NLU analysis and conversation state.
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.llm_client import LLMClient
from prompts.planner_prompt import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT_TEMPLATE
from core.nlu import NLUModule
from memory import SessionMemory


class PlannerAgent:
    """
    Central coordinator that analyzes user input and routes to appropriate agents.

    Responsibilities:
    1. Use NLU to understand user intent
    2. Maintain session state and conversation history
    3. Route requests to specialist agents (BUY, ORDER, RECOMMEND, RETURN)
    4. Coordinate multi-step conversations
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize the Planner Agent.

        Args:
            llm_client (LLMClient, optional): LLM client for decision making
        """
        self.llm_client = llm_client or LLMClient()
        self.nlu = NLUModule(self.llm_client)
        self.memory = SessionMemory(agent_name="planner")

        # Available agents that can be routed to
        self.available_agents = ["BUY", "ORDER", "RECOMMEND", "RETURN"]

        # Current session tracking
        self.session_id = None
        self.conversation_history = []
        self.session_state = {}

    def start_session(self, session_label: Optional[str] = None) -> str:
        """
        Start a new planning session.

        Args:
            session_label (str, optional): Label for the session

        Returns:
            str: Session ID
        """
        # Generate new session ID
        self.session_id = str(uuid.uuid4())[:8]

        # Reset session state
        self.conversation_history = []
        self.session_state = {
            "session_id": self.session_id,
            "started_at": datetime.now().isoformat(),
            "current_agent": None,
            "user_journey": "initial",
            "entities": {},
            "completion_status": "active"
        }

        # Initialize memory for this session
        self.memory.new_session(
            label=session_label or f"planner_session_{self.session_id}",
            config={"planner_version": "1.0"}
        )

        # Save initial state
        self._save_session_state()

        return self.session_id

    def process_user_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message and determine the next action.

        Args:
            user_message (str): The user's message

        Returns:
            Dict containing routing decision and context
        """
        if not self.session_id:
            self.start_session()

        try:
            # Step 1: Use NLU to understand user intent
            nlu_result = self.nlu.analyze(user_message, self.conversation_history)

            # Step 2: Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })

            # Step 3: Use LLM to make routing decision
            routing_decision = self._make_routing_decision(nlu_result)

            # Step 4: Update session state
            self._update_session_state(nlu_result, routing_decision)

            # Step 5: Save session state with memory
            self._save_session_state()

            # Step 6: Prepare response
            response = {
                "session_id": self.session_id,
                "routing_decision": routing_decision,
                "nlu_analysis": nlu_result,
                "session_state": self.session_state,
                "success": True
            }

            return response

        except Exception as e:
            # Error handling
            error_response = {
                "session_id": self.session_id,
                "error": str(e),
                "routing_decision": {
                    "next_agent": "CLARIFY",
                    "confidence": 0.0,
                    "reasoning": f"Error occurred during processing: {str(e)}",
                    "priority_actions": ["handle_error", "ask_for_clarification"],
                    "context_transfer": {}
                },
                "success": False
            }

            # Still save the error state
            self._save_session_state()

            return error_response

    def _make_routing_decision(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to make intelligent routing decisions.

        Args:
            nlu_result (Dict): NLU analysis of user message

        Returns:
            Dict: Routing decision with agent choice and reasoning
        """
        # Prepare context for LLM
        recent_conversation = self._format_recent_conversation()
        session_state_summary = self._summarize_session_state()

        # Create prompt for LLM
        user_prompt = PLANNER_USER_PROMPT_TEMPLATE.format(
            nlu_result=json.dumps(nlu_result, indent=2),
            session_state=session_state_summary,
            recent_conversation=recent_conversation
        )

        # Combine system and user prompts
        full_prompt = f"{PLANNER_SYSTEM_PROMPT}\n\n{user_prompt}"

        # Get LLM response
        llm_response = self.llm_client.generate(full_prompt)

        # Parse LLM response
        try:
            routing_decision = self._parse_routing_response(llm_response, nlu_result)
        except Exception as e:
            # Fallback to simple intent-based routing
            routing_decision = self._fallback_routing(nlu_result)

        return routing_decision

    def _parse_routing_response(self, llm_response: str, nlu_result: Dict) -> Dict[str, Any]:
        """
        Parse the LLM routing response into structured data.

        Args:
            llm_response (str): Raw LLM response
            nlu_result (Dict): Original NLU result for fallback

        Returns:
            Dict: Parsed routing decision
        """
        # Handle fallback responses
        if llm_response.startswith("[LLM-FALLBACK]"):
            return self._fallback_routing(nlu_result)

        try:
            # Clean response and extract JSON
            response = llm_response.strip()

            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]

            if response.endswith('```'):
                response = response[:-3]

            response = response.strip()

            # Find JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1:
                raise ValueError("No JSON found in response")

            json_str = response[json_start:json_end]
            decision = json.loads(json_str)

            # Validate decision structure
            return self._validate_routing_decision(decision)

        except Exception as e:
            # If parsing fails, use fallback
            return self._fallback_routing(nlu_result)

    def _validate_routing_decision(self, decision: Dict) -> Dict[str, Any]:
        """
        Validate and clean routing decision from LLM.

        Args:
            decision (Dict): Raw decision from LLM

        Returns:
            Dict: Validated routing decision
        """
        # Ensure required fields exist
        validated = {}

        # Validate next_agent
        next_agent = decision.get("next_agent", "CLARIFY")
        valid_agents = self.available_agents + ["CLARIFY"]
        validated["next_agent"] = next_agent if next_agent in valid_agents else "CLARIFY"

        # Validate confidence
        confidence = decision.get("confidence", 0.5)
        try:
            validated["confidence"] = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            validated["confidence"] = 0.5

        # Other fields
        validated["reasoning"] = decision.get("reasoning", "Routing decision made")
        validated["priority_actions"] = decision.get("priority_actions", []) if isinstance(
            decision.get("priority_actions"), list) else []
        validated["context_transfer"] = decision.get("context_transfer", {}) if isinstance(
            decision.get("context_transfer"), dict) else {}

        return validated

    def _fallback_routing(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple fallback routing based on NLU intent when LLM fails.

        Args:
            nlu_result (Dict): NLU analysis result

        Returns:
            Dict: Basic routing decision
        """
        intent = nlu_result.get("intent", "BUY")
        confidence = nlu_result.get("confidence", 0.5)

        # Map intent to agent
        agent_mapping = {
            "BUY": "BUY",
            "ORDER": "ORDER",
            "RECOMMEND": "RECOMMEND",
            "RETURN": "RETURN"
        }

        next_agent = agent_mapping.get(intent, "BUY")

        return {
            "next_agent": next_agent,
            "confidence": confidence * 0.8,  # Lower confidence for fallback
            "reasoning": f"Fallback routing based on NLU intent: {intent}",
            "priority_actions": [f"handle_{intent.lower()}_request"],
            "context_transfer": {
                "key_entities": nlu_result.get("entities", {}),
                "user_state": f"fallback_routing_for_{intent.lower()}"
            }
        }

    def _update_session_state(self, nlu_result: Dict, routing_decision: Dict):
        """
        Update the session state with new information.

        Args:
            nlu_result (Dict): NLU analysis
            routing_decision (Dict): Routing decision made
        """
        # Update current agent
        self.session_state["current_agent"] = routing_decision["next_agent"]
        self.session_state["last_update"] = datetime.now().isoformat()

        # Merge entities from NLU
        current_entities = self.session_state.get("entities", {})
        new_entities = nlu_result.get("entities", {})

        for key, value in new_entities.items():
            if value is not None:
                current_entities[key] = value

        self.session_state["entities"] = current_entities

        # Update user journey based on agent
        journey_mapping = {
            "BUY": "product_search",
            "ORDER": "order_management",
            "RECOMMEND": "getting_recommendations",
            "RETURN": "return_process",
            "CLARIFY": "needs_clarification"
        }

        self.session_state["user_journey"] = journey_mapping.get(
            routing_decision["next_agent"],
            "unknown"
        )

        # Track routing history
        if "routing_history" not in self.session_state:
            self.session_state["routing_history"] = []

        self.session_state["routing_history"].append({
            "timestamp": datetime.now().isoformat(),
            "agent": routing_decision["next_agent"],
            "confidence": routing_decision["confidence"],
            "reasoning": routing_decision["reasoning"]
        })

    def _format_recent_conversation(self, max_entries: int = 6) -> str:
        """
        Format recent conversation history for LLM context.

        Args:
            max_entries (int): Maximum number of conversation entries to include

        Returns:
            str: Formatted conversation history
        """
        if not self.conversation_history:
            return "No previous conversation in this session."

        recent = self.conversation_history[-max_entries:]
        formatted = []

        for entry in recent:
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def _summarize_session_state(self) -> str:
        """
        Create a concise summary of current session state.

        Returns:
            str: Session state summary
        """
        state = self.session_state

        summary_parts = [
            f"Session ID: {state.get('session_id', 'unknown')}",
            f"Current Agent: {state.get('current_agent', 'none')}",
            f"User Journey: {state.get('user_journey', 'initial')}",
            f"Status: {state.get('completion_status', 'active')}"
        ]

        # Add key entities if present
        entities = state.get("entities", {})
        non_null_entities = {k: v for k, v in entities.items() if v is not None}
        if non_null_entities:
            summary_parts.append(f"Key Entities: {json.dumps(non_null_entities)}")

        return "\n".join(summary_parts)

    def _save_session_state(self):
        """
        Save current session state to memory.
        """
        try:
            self.memory.save(
                session_state=self.session_state,
                conversation_history=self.conversation_history,
                config={"last_saved": datetime.now().isoformat()}
            )
        except Exception as e:
            print(f"[WARN] Failed to save session state: {e}")

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get current session information.

        Returns:
            Dict: Current session info
        """
        return {
            "session_id": self.session_id,
            "session_state": self.session_state.copy(),
            "conversation_length": len(self.conversation_history),
            "current_agent": self.session_state.get("current_agent"),
            "user_journey": self.session_state.get("user_journey")
        }


def test_planner():
    """
    Test the Planner Agent with various scenarios.
    """
    print("🧪 Testing Planner Agent")
    print("=" * 50)

    planner = PlannerAgent()

    test_messages = [
        "I want to buy a laptop under $1500",
        "Track my order #12345",
        # "What's the best smartphone for photography?",
        # "I need to return a defective product",
        # "Show me gaming laptops with good graphics cards"
    ]

    # Start a test session
    session_id = planner.start_session("test_session")
    print(f"Started session: {session_id}")

    for i, message in enumerate(test_messages, 1):
        print(f"\n🔍 Test {i}: {message}")

        result = planner.process_user_message(message)

        if result["success"]:
            routing = result["routing_decision"]
            print(f"   Next Agent: {routing['next_agent']}")
            print(f"   Confidence: {routing['confidence']:.2f}")
            print(f"   Reasoning: {routing['reasoning']}")

            if routing["priority_actions"]:
                print(f"   Actions: {routing['priority_actions']}")
        else:
            print(f"   Error: {result['error']}")

    # Show session summary
    session_info = planner.get_session_info()
    print(f"\n📊 Session Summary:")
    print(f"   Current Agent: {session_info['current_agent']}")
    print(f"   User Journey: {session_info['user_journey']}")
    print(f"   Conversation Length: {session_info['conversation_length']}")

    print("\n✅ Planner Agent Testing Complete!")


if __name__ == "__main__":
    test_planner()