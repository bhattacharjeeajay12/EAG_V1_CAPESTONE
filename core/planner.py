# core/planner.py
"""
Planner Agent for E-commerce System
Routes user requests to appropriate specialist agents based on NLU analysis and conversation state.
Includes MCP client integration for tool access across all agents.
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.llm_client import LLMClient
from prompts.planner_prompt import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT_TEMPLATE
from core.nlu import NLUModule
from memory import SessionMemory

# MCP client import - adjust path based on your MCP client location
try:
    from mcp_client import MCPClient  # Assuming you have an MCP client class

    MCP_AVAILABLE = True
except ImportError:
    print("[WARN] MCP client not available. Install or check mcp_client module.")
    MCP_AVAILABLE = False
    MCPClient = None


class PlannerAgent:
    """
    Central coordinator that analyzes user input and routes to appropriate agents.

    Responsibilities:
    1. Use NLU to understand user intent
    2. Maintain session state and conversation history in centralized memory
    3. Route requests to specialist agents (BUY, ORDER, RECOMMEND, RETURN)
    4. Coordinate multi-step conversations
    5. Provide MCP client access to all agents for tool usage
    """

    def __init__(self,
                 llm_client: Optional[LLMClient] = None,
                 mcp_server_command: Optional[str] = None):
        """
        Initialize the Planner Agent with MCP client integration.

        Args:
            llm_client (LLMClient, optional): LLM client for decision making
            mcp_server_command (str, optional): Command to start MCP server
        """
        self.llm_client = llm_client or LLMClient()
        self.nlu = NLUModule(self.llm_client)
        self.memory = SessionMemory()

        # Available agents that can be routed to
        self.available_agents = ["BUY", "ORDER", "RECOMMEND", "RETURN"]

        # Current session tracking
        self.current_session_id = None

        # MCP Client Integration
        self.mcp_client = None
        self._initialize_mcp_client(mcp_server_command)

        # Agent instances cache - will be created with MCP client when needed
        self._agent_instances = {}

    def _initialize_mcp_client(self, server_command: Optional[str] = None):
        """
        Initialize the MCP client for tool access.

        Args:
            server_command (str, optional): Command to start MCP server
        """
        if not MCP_AVAILABLE:
            print("[INFO] MCP client not available. Agents will run without tool access.")
            return

        try:
            # Default server command if not provided
            if server_command is None:
                server_command = ["python", "mcp_server.py"]

            # Initialize MCP client
            self.mcp_client = MCPClient(server_command)
            print("[INFO] MCP client initialized successfully.")

            # Test connection
            if hasattr(self.mcp_client, 'connect'):
                self.mcp_client.connect()
                print("[INFO] MCP client connected to server.")

        except Exception as e:
            print(f"[WARN] Failed to initialize MCP client: {e}")
            self.mcp_client = None

    def get_mcp_client(self) -> Optional[Any]:
        """
        Get the MCP client instance for agents to use.

        Returns:
            MCP client instance or None if not available
        """
        return self.mcp_client

    def _get_or_create_agent(self, agent_type: str) -> Optional[Any]:
        """
        Get or create an agent instance with MCP client integration.

        Args:
            agent_type (str): Type of agent (BUY, ORDER, RECOMMEND, RETURN)

        Returns:
            Agent instance or None if failed to create
        """
        # Return cached instance if exists
        if agent_type in self._agent_instances:
            return self._agent_instances[agent_type]

        try:
            # Import and create agent based on type
            if agent_type == "BUY":
                from agents.buy_agent import BuyAgent
                agent = BuyAgent(
                    llm_client=self.llm_client,
                    mcp_client=self.mcp_client
                )
            elif agent_type == "ORDER":
                from agents.order_agent import OrderAgent
                agent = OrderAgent(
                    llm_client=self.llm_client,
                    mcp_client=self.mcp_client
                )
            elif agent_type == "RECOMMEND":
                from agents.recommendation_agent import RecommendationAgent
                agent = RecommendationAgent(
                    llm_client=self.llm_client,
                    mcp_client=self.mcp_client
                )
            elif agent_type == "RETURN":
                from agents.return_agent import ReturnAgent
                agent = ReturnAgent(
                    llm_client=self.llm_client,
                    mcp_client=self.mcp_client
                )
            else:
                print(f"[ERROR] Unknown agent type: {agent_type}")
                return None

            # Cache the instance
            self._agent_instances[agent_type] = agent
            print(f"[INFO] Created {agent_type} agent with MCP client integration.")

            return agent

        except ImportError as e:
            print(f"[ERROR] Failed to import {agent_type} agent: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to create {agent_type} agent: {e}")
            return None

    def execute_agent_task(self, agent_type: str, task_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task using the specified agent with MCP client access.

        Args:
            agent_type (str): Type of agent to use
            task_context (Dict): Context and parameters for the task

        Returns:
            Dict: Agent's response and execution result
        """
        # Get or create agent instance
        agent = self._get_or_create_agent(agent_type)

        if not agent:
            return {
                "success": False,
                "error": f"Failed to create or get {agent_type} agent",
                "response": None
            }

        try:
            # Execute the task with the agent
            # Assuming agents have a standard 'execute' or 'handle' method
            if hasattr(agent, 'execute'):
                result = agent.execute(task_context)
            elif hasattr(agent, 'handle'):
                result = agent.handle(task_context)
            else:
                # Fallback method
                result = agent.process(task_context)

            return {
                "success": True,
                "agent_type": agent_type,
                "response": result,
                "mcp_tools_available": self.mcp_client is not None
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Agent execution failed: {str(e)}",
                "agent_type": agent_type,
                "response": None
            }

    def start_session(self, session_label: Optional[str] = None) -> str:
        """
        Start a new planning session.

        Args:
            session_label (str, optional): Label for the session

        Returns:
            str: Session ID
        """
        # Create new session in memory
        session_id = self.memory.new_session(
            session_label=session_label or f"planner_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            config={
                "planner_version": "1.0",
                "created_by": "PlannerAgent",
                "mcp_available": self.mcp_client is not None
            }
        )

        self.current_session_id = session_id
        return session_id

    def process_user_message(self, user_message: str) -> Dict[str, Any]:
        """
        Process a user message and determine the next action.

        Args:
            user_message (str): The user's message

        Returns:
            Dict containing routing decision and context
        """
        # Start session if not already started
        if not self.current_session_id:
            self.start_session()

        try:
            # Step 1: Load current session data
            session_data = self.memory.load_session() or {}
            conversation_history = session_data.get("conversation_history", [])
            session_state = session_data.get("session_state", {})

            # Step 2: Use NLU to understand user intent
            nlu_result = self.nlu.analyze(user_message, conversation_history)

            # Step 3: Use LLM to make routing decision
            routing_decision = self._make_routing_decision(nlu_result, session_state, conversation_history)

            # Step 4: Update session state
            updated_session_state = self._update_session_state(session_state, nlu_result, routing_decision)

            # Step 5: Save to memory
            self.memory.add_conversation_turn(
                role="user",
                content=user_message,
                nlu_analysis=nlu_result,
                routing_decision=routing_decision
            )

            # Save updated session state
            conversation_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })

            self.memory.save(
                conversation_history=conversation_history,
                session_state=updated_session_state,
                nlu_history=session_data.get("nlu_history", []),
                routing_history=session_data.get("routing_history", []),
                config=session_data.get("config", {})
            )

            # Step 6: Prepare context for agent execution
            agent_context = self._prepare_agent_context(updated_session_state, nlu_result, routing_decision)

            # Step 7: Prepare response
            response = {
                "session_id": self.current_session_id,
                "routing_decision": routing_decision,
                "nlu_analysis": nlu_result,
                "session_state": updated_session_state,
                "agent_context": agent_context,
                "mcp_available": self.mcp_client is not None,
                "success": True
            }

            return response

        except Exception as e:
            # Error handling
            error_response = {
                "session_id": self.current_session_id,
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

            return error_response

    def _prepare_agent_context(self, session_state: Dict, nlu_result: Dict, routing_decision: Dict) -> Dict[str, Any]:
        """
        Prepare context for agent execution including MCP client access.

        Args:
            session_state (Dict): Current session state
            nlu_result (Dict): NLU analysis
            routing_decision (Dict): Routing decision

        Returns:
            Dict: Complete context for agent execution
        """
        return {
            "session_id": self.current_session_id,
            "entities": session_state.get("entities", {}),
            "user_journey": session_state.get("user_journey"),
            "nlu_analysis": nlu_result,
            "priority_actions": routing_decision.get("priority_actions", []),
            "context_transfer": routing_decision.get("context_transfer", {}),
            "conversation_history": self.memory.get_context_for_agent(
                routing_decision.get("next_agent", "BUY")
            ).get("conversation_history", []),
            "mcp_client_available": self.mcp_client is not None
        }

    def get_agent_context(self, agent_type: str) -> Dict[str, Any]:
        """
        Get context for a specific agent to execute, including MCP client.

        Args:
            agent_type (str): Type of agent (BUY, ORDER, RECOMMEND, RETURN)

        Returns:
            Dict: Context data for the agent
        """
        base_context = self.memory.get_context_for_agent(agent_type)
        base_context["mcp_client_available"] = self.mcp_client is not None
        return base_context

    def add_agent_response(self, agent_type: str, response: str) -> None:
        """
        Add agent response to conversation history.

        Args:
            agent_type (str): Type of agent that responded
            response (str): Agent's response
        """
        self.memory.add_conversation_turn(
            role="agent",
            content=f"[{agent_type}] {response}"
        )

    def cleanup(self):
        """
        Clean up resources including MCP client connection.
        """
        if self.mcp_client:
            try:
                if hasattr(self.mcp_client, 'disconnect'):
                    self.mcp_client.disconnect()
                elif hasattr(self.mcp_client, 'close'):
                    self.mcp_client.close()
                print("[INFO] MCP client disconnected.")
            except Exception as e:
                print(f"[WARN] Error disconnecting MCP client: {e}")

    # ... (keeping all the existing methods unchanged)

    def _make_routing_decision(self, nlu_result: Dict[str, Any],
                               session_state: Dict[str, Any],
                               conversation_history: List[Dict]) -> Dict[str, Any]:
        """
        Use LLM to make intelligent routing decisions.

        Args:
            nlu_result (Dict): NLU analysis of user message
            session_state (Dict): Current session state
            conversation_history (List): Conversation history

        Returns:
            Dict: Routing decision with agent choice and reasoning
        """
        # Prepare context for LLM
        recent_conversation = self._format_recent_conversation(conversation_history)
        session_state_summary = self._summarize_session_state(session_state)

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

    def _update_session_state(self, current_state: Dict[str, Any],
                              nlu_result: Dict, routing_decision: Dict) -> Dict[str, Any]:
        """
        Update the session state with new information.

        Args:
            current_state (Dict): Current session state
            nlu_result (Dict): NLU analysis
            routing_decision (Dict): Routing decision made

        Returns:
            Dict: Updated session state
        """
        # Create updated state
        updated_state = current_state.copy()

        # Update current agent
        updated_state["current_agent"] = routing_decision["next_agent"]
        updated_state["last_update"] = datetime.now().isoformat()

        # Merge entities from NLU
        current_entities = updated_state.get("entities", {})
        new_entities = nlu_result.get("entities", {})

        for key, value in new_entities.items():
            if value is not None:
                current_entities[key] = value

        updated_state["entities"] = current_entities

        # Update user journey based on agent
        journey_mapping = {
            "BUY": "product_search",
            "ORDER": "order_management",
            "RECOMMEND": "getting_recommendations",
            "RETURN": "return_process",
            "CLARIFY": "needs_clarification"
        }

        updated_state["user_journey"] = journey_mapping.get(
            routing_decision["next_agent"],
            "unknown"
        )

        return updated_state

    def _format_recent_conversation(self, conversation_history: List[Dict], max_entries: int = 6) -> str:
        """
        Format recent conversation history for LLM context.

        Args:
            conversation_history (List): Complete conversation history
            max_entries (int): Maximum number of conversation entries to include

        Returns:
            str: Formatted conversation history
        """
        if not conversation_history:
            return "No previous conversation in this session."

        recent = conversation_history[-max_entries:]
        formatted = []

        for entry in recent:
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def _summarize_session_state(self, session_state: Dict[str, Any]) -> str:
        """
        Create a concise summary of current session state.

        Args:
            session_state (Dict): Current session state

        Returns:
            str: Session state summary
        """
        summary_parts = [
            f"Session ID: {session_state.get('session_id', 'unknown')}",
            f"Current Agent: {session_state.get('current_agent', 'none')}",
            f"User Journey: {session_state.get('user_journey', 'initial')}",
            f"Status: {session_state.get('completion_status', 'active')}"
        ]

        # Add key entities if present
        entities = session_state.get("entities", {})
        non_null_entities = {k: v for k, v in entities.items() if v is not None}
        if non_null_entities:
            summary_parts.append(f"Key Entities: {json.dumps(non_null_entities)}")

        return "\n".join(summary_parts)

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get current session information.

        Returns:
            Dict: Current session info
        """
        if not self.current_session_id:
            return {"error": "No active session"}

        session_data = self.memory.load_session()
        if not session_data:
            return {"error": "Session data not found"}

        session_state = session_data.get("session_state", {})
        conversation_history = session_data.get("conversation_history", [])

        return {
            "session_id": self.current_session_id,
            "session_state": session_state,
            "conversation_length": len(conversation_history),
            "current_agent": session_state.get("current_agent"),
            "user_journey": session_state.get("user_journey"),
            "mcp_available": self.mcp_client is not None
        }


def test_planner_with_mcp():
    """
    Test the Planner Agent with MCP client integration.
    """
    print("🧪 Testing Planner Agent with MCP Integration")
    print("=" * 50)

    # Initialize planner with MCP client
    planner = PlannerAgent(mcp_server_command=["python", "mcp_server.py"])

    test_messages = [
        "I want to buy a laptop under $1500",
        "What tools do you have available?",  # This could use MCP tools
        "Track my order #12345"
    ]

    try:
        # Start a test session
        session_id = planner.start_session("test_session_with_mcp")
        print(f"Started session: {session_id}")

        for i, message in enumerate(test_messages, 1):
            print(f"\n🔍 Test {i}: {message}")

            result = planner.process_user_message(message)

            if result["success"]:
                routing = result["routing_decision"]
                print(f"   Next Agent: {routing['next_agent']}")
                print(f"   Confidence: {routing['confidence']:.2f}")
                print(f"   MCP Available: {result['mcp_available']}")
                print(f"   Reasoning: {routing['reasoning']}")

                # Test agent execution with MCP access
                if routing["next_agent"] != "CLARIFY":
                    agent_context = result["agent_context"]
                    execution_result = planner.execute_agent_task(
                        routing["next_agent"],
                        agent_context
                    )
                    print(f"   Agent Execution Success: {execution_result['success']}")
                    if execution_result["success"]:
                        print(f"   MCP Tools Available to Agent: {execution_result['mcp_tools_available']}")
            else:
                print(f"   Error: {result['error']}")

        # Show session summary
        session_info = planner.get_session_info()
        print(f"\n📊 Session Summary:")
        print(f"   Current Agent: {session_info['current_agent']}")
        print(f"   User Journey: {session_info['user_journey']}")
        print(f"   MCP Available: {session_info['mcp_available']}")

    finally:
        # Clean up
        planner.cleanup()

    print("\n✅ Planner Agent with MCP Testing Complete!")


if __name__ == "__main__":
    test_planner_with_mcp()