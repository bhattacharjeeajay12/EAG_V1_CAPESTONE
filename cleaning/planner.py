# core/planner.py
"""
Graph-based Planner Agent for E-commerce System
Uses NetworkX to create and manage conversation flow graphs.
Routes user requests based on state transitions and agent outcomes.
"""

import networkx as nx
from typing import Dict, Optional, Any

from cleaning.world_state import WorldState
from cleaning.schema import make_result
from cleaning.nlu import NLUModule
from core.llm_client import LLMClient


class Planner:
    """
    Graph-based planner that orchestrates conversation flow using NetworkX.

    Creates a directed graph where:
    - Nodes represent conversation states/agents
    - Edges represent valid transitions with conditions
    - Flow is determined by current state + agent results
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.nlu = NLUModule(self.llm_client)
        self.graph = nx.DiGraph()
        self.world_state = WorldState()

        # Agent instances cache
        self._agents = {}

        # Build the conversation flow graph
        self._build_conversation_graph()

    def _build_conversation_graph(self):
        """
        Build the conversation flow graph with nodes and edges.

        Nodes represent conversation states:
        - NLU: Initial intent analysis
        - RECOMMEND: Product recommendation flow
        - BUY: Purchase/search flow
        - ORDER: Order management flow
        - RETURN: Return/exchange flow
        - CLARIFY: Clarification needed
        - DONE: Conversation complete
        """
        # Add nodes with their properties
        nodes = [
            ("NLU", {"kind": "system", "description": "Intent analysis"}),
            ("RECOMMEND", {"agent": "RecommendationAgent", "description": "Product recommendations"}),
            ("BUY", {"agent": "BuyAgent", "description": "Product search and purchase"}),
            ("ORDER", {"agent": "OrderAgent", "description": "Order tracking and management"}),
            ("RETURN", {"agent": "ReturnAgent", "description": "Returns and exchanges"}),
            ("CLARIFY", {"kind": "system", "description": "Request clarification"}),
            ("DONE", {"kind": "terminal", "description": "Conversation complete"})
        ]

        for node_id, attrs in nodes:
            self.graph.add_node(node_id, **attrs)

        # Add edges with transition conditions
        edges = [
            # From NLU - initial routing based on intent
            ("NLU", "RECOMMEND", {"condition": "intent_recommend", "priority": 1}),
            ("NLU", "BUY", {"condition": "intent_buy", "priority": 1}),
            ("NLU", "ORDER", {"condition": "intent_order", "priority": 1}),
            ("NLU", "RETURN", {"condition": "intent_return", "priority": 1}),
            ("NLU", "CLARIFY", {"condition": "intent_unclear", "priority": 0}),

            # From RECOMMEND
            ("RECOMMEND", "BUY", {"condition": "wants_to_buy", "priority": 2}),
            ("RECOMMEND", "CLARIFY", {"condition": "needs_more_info", "priority": 1}),
            ("RECOMMEND", "DONE", {"condition": "satisfied_with_recommendations", "priority": 1}),

            # From BUY
            ("BUY", "ORDER", {"condition": "purchase_initiated", "priority": 2}),
            ("BUY", "RECOMMEND", {"condition": "needs_recommendations", "priority": 1}),
            ("BUY", "CLARIFY", {"condition": "missing_requirements", "priority": 1}),
            ("BUY", "DONE", {"condition": "purchase_complete", "priority": 2}),

            # From ORDER
            ("ORDER", "RETURN", {"condition": "wants_return", "priority": 2}),
            ("ORDER", "BUY", {"condition": "wants_more_items", "priority": 1}),
            ("ORDER", "CLARIFY", {"condition": "missing_order_info", "priority": 1}),
            ("ORDER", "DONE", {"condition": "order_resolved", "priority": 2}),

            # From RETURN
            ("RETURN", "BUY", {"condition": "wants_replacement", "priority": 1}),
            ("RETURN", "CLARIFY", {"condition": "missing_return_info", "priority": 1}),
            ("RETURN", "DONE", {"condition": "return_complete", "priority": 2}),

            # From CLARIFY - can go anywhere based on clarification
            ("CLARIFY", "BUY", {"condition": "clarified_buy", "priority": 1}),
            ("CLARIFY", "ORDER", {"condition": "clarified_order", "priority": 1}),
            ("CLARIFY", "RETURN", {"condition": "clarified_return", "priority": 1}),
            ("CLARIFY", "RECOMMEND", {"condition": "clarified_recommend", "priority": 1}),
            ("CLARIFY", "DONE", {"condition": "user_done", "priority": 1})
        ]

        for src, dst, attrs in edges:
            self.graph.add_edge(src, dst, **attrs)

    def _get_or_create_agent(self, agent_type: str):
        """Get or create agent instance."""
        if agent_type in self._agents:
            return self._agents[agent_type]

        try:
            if agent_type == "BuyAgent":
                from agents.buy_agent import BuyAgent
                agent = BuyAgent(verbose=True)
            elif agent_type == "OrderAgent":
                from agents.order_agent import OrderAgent
                agent = OrderAgent(llm_client=self.llm_client)
            elif agent_type == "RecommendationAgent":
                from agents.recommendation_agent import RecommendationAgent
                agent = RecommendationAgent(llm_client=self.llm_client)
            elif agent_type == "ReturnAgent":
                from agents.return_agent import ReturnAgent
                agent = ReturnAgent(llm_client=self.llm_client)
            else:
                return None

            self._agents[agent_type] = agent
            return agent

        except ImportError:
            print(f"[WARN] Could not import {agent_type}")
            return None

    def route_from_nlu(self, world_state: WorldState) -> str:
        """
        Determine initial routing based on NLU intent.

        Args:
            world_state: Current world state with NLU analysis

        Returns:
            Next node to transition to
        """
        intent = world_state.get("intent", "").upper()
        confidence = world_state.get("confidence", 0.0)

        # Low confidence means unclear intent
        if confidence < 0.6:
            return "CLARIFY"

        # Map intents to nodes
        intent_mapping = {
            "BUY": "BUY",
            "PURCHASE": "BUY",
            "SEARCH": "BUY",
            "ORDER": "ORDER",
            "TRACK": "ORDER",
            "STATUS": "ORDER",
            "RECOMMEND": "RECOMMEND",
            "SUGGESTION": "RECOMMEND",
            "RETURN": "RETURN",
            "EXCHANGE": "RETURN",
            "REFUND": "RETURN"
        }

        return intent_mapping.get(intent, "CLARIFY")

    def evaluate_transition_condition(self, condition: str,
                                      last_result: Dict[str, Any],
                                      world_state: WorldState) -> bool:
        """
        Evaluate whether a transition condition is met.

        Args:
            condition: Condition string to evaluate
            last_result: Result from last agent execution
            world_state: Current world state

        Returns:
            True if condition is met
        """
        agent_status = last_result.get("status", "UNKNOWN")
        proposed_next = last_result.get("proposed_next", [])

        # Map conditions to boolean logic
        condition_map = {
            # Intent-based conditions (from NLU)
            "intent_buy": world_state.get("intent", "").upper() in ["BUY", "PURCHASE", "SEARCH"],
            "intent_order": world_state.get("intent", "").upper() in ["ORDER", "TRACK", "STATUS"],
            "intent_return": world_state.get("intent", "").upper() in ["RETURN", "EXCHANGE", "REFUND"],
            "intent_recommend": world_state.get("intent", "").upper() in ["RECOMMEND", "SUGGESTION"],
            "intent_unclear": world_state.get("confidence", 1.0) < 0.6,

            # Agent result-based conditions
            "wants_to_buy": "BUY" in proposed_next,
            "needs_more_info": "CLARIFY" in proposed_next or agent_status == "NEEDS_INFO",
            "satisfied_with_recommendations": "DONE" in proposed_next,
            "purchase_initiated": "ORDER" in proposed_next or world_state.get("purchase_started", False),
            "needs_recommendations": "RECOMMEND" in proposed_next,
            "missing_requirements": "CLARIFY" in proposed_next,
            "purchase_complete": "DONE" in proposed_next or world_state.get("purchase_complete", False),
            "wants_return": "RETURN" in proposed_next,
            "wants_more_items": "BUY" in proposed_next,
            "missing_order_info": "CLARIFY" in proposed_next,
            "order_resolved": "DONE" in proposed_next,
            "wants_replacement": "BUY" in proposed_next,
            "missing_return_info": "CLARIFY" in proposed_next,
            "return_complete": "DONE" in proposed_next,
            "user_done": "DONE" in proposed_next,

            # Clarification conditions
            "clarified_buy": "BUY" in proposed_next,
            "clarified_order": "ORDER" in proposed_next,
            "clarified_return": "RETURN" in proposed_next,
            "clarified_recommend": "RECOMMEND" in proposed_next,
        }

        return condition_map.get(condition, False)

    def step(self, node_name: str, world_state: WorldState) -> Dict[str, Any]:
        """
        Execute a single step in the conversation graph.

        Args:
            node_name: Current node to execute
            world_state: Current world state

        Returns:
            Result dictionary with status and proposed next steps
        """
        node_attrs = self.graph.nodes[node_name]

        # Terminal node
        if node_name == "DONE":
            return make_result("Planner", "SUCCESS", proposed_next=["DONE"], changes={})

        # System nodes
        if node_attrs.get("kind") == "system":
            if node_name == "NLU":
                next_node = self.route_from_nlu(world_state)
                return make_result("Planner", "SUCCESS",
                                   proposed_next=[next_node], changes={})
            elif node_name == "CLARIFY":
                return make_result("Planner", "NEEDS_INFO",
                                   proposed_next=["CLARIFY"],
                                   changes={"message": "Could you please clarify what you'd like to do?"})

        # Agent nodes
        agent_type = node_attrs.get("agent")
        if agent_type:
            agent = self._get_or_create_agent(agent_type)
            if agent:
                try:
                    # Execute agent with world state
                    if hasattr(agent, 'execute'):
                        result = agent.execute(world_state.to_dict())
                    elif hasattr(agent, 'handle'):
                        # For BuyAgent compatibility
                        user_message = world_state.get("user_message", "")
                        result = agent.handle(user_message)
                        # Convert to standard format
                        result = make_result(agent_type, "SUCCESS",
                                             proposed_next=["DONE"], changes={})
                    else:
                        result = make_result(agent_type, "ERROR",
                                             proposed_next=["CLARIFY"],
                                             changes={},
                                             error="Agent has no execute/handle method")
                    return result
                except Exception as e:
                    return make_result(agent_type, "FAILED",
                                       proposed_next=["CLARIFY"],
                                       changes={},
                                       error=str(e))
            else:
                return make_result("Planner", "FAILED",
                                   proposed_next=["CLARIFY"],
                                   changes={},
                                   error=f"Could not create {agent_type}")

        # Fallback
        return make_result("Planner", "ERROR",
                           proposed_next=["CLARIFY"],
                           changes={},
                           error=f"Unknown node type: {node_name}")

    def next_node(self, current_node: str, last_result: Dict[str, Any],
                  world_state: WorldState) -> str:
        """
        Determine the next node based on current state and last result.

        Args:
            current_node: Current node name
            last_result: Result from executing current node
            world_state: Current world state

        Returns:
            Next node name to transition to
        """
        # Get all possible transitions from current node
        possible_transitions = []

        for _, dst_node, edge_attrs in self.graph.out_edges(current_node, data=True):
            condition = edge_attrs.get("condition", "")
            priority = edge_attrs.get("priority", 0)

            if self.evaluate_transition_condition(condition, last_result, world_state):
                possible_transitions.append((dst_node, priority))

        # Choose highest priority transition
        if possible_transitions:
            possible_transitions.sort(key=lambda x: x[1], reverse=True)
            return possible_transitions[0][0]

        # Fallback to DONE if no valid transitions
        return "DONE"

    def run_plan(self, user_message: str) -> Dict[str, Any]:
        """
        Execute a complete planning cycle for a user message.

        Args:
            user_message: User's input message

        Returns:
            Complete execution result with steps and final state
        """
        # Reset world state for new conversation
        self.world_state = WorldState()
        self.world_state.set("user_message", user_message)

        # Step 1: NLU Analysis
        try:
            nlu_result = self.nlu.analyze(user_message, [])
            self.world_state.merge({
                "intent": nlu_result.get("intent", ""),
                "confidence": nlu_result.get("confidence", 0.0),
                "entities": nlu_result.get("entities", {}),
                "nlu_analysis": nlu_result
            })
        except Exception as e:
            print(f"[WARN] NLU analysis failed: {e}")
            self.world_state.merge({
                "intent": "CLARIFY",
                "confidence": 0.0,
                "entities": {},
                "nlu_analysis": {"error": str(e)}
            })

        # Step 2: Execute graph traversal
        current_node = "NLU"
        steps = []
        safety_counter = 0

        while current_node != "DONE" and safety_counter < 12:
            safety_counter += 1

            # Execute current node
            result = self.step(current_node, self.world_state)

            # Merge changes into world state
            changes = result.get("changes", {})
            self.world_state.merge(changes)

            # Record step
            steps.append({
                "node": current_node,
                "result": result,
                "world_state_snapshot": dict(self.world_state)
            })

            # Check for failure
            if result.get("status") == "FAILED":
                print(f"[ERROR] Step failed at {current_node}: {result.get('error', 'Unknown error')}")
                break

            # Determine next node
            current_node = self.next_node(current_node, result, self.world_state)

        # Add terminal step
        if current_node == "DONE":
            terminal_result = make_result("Planner", "SUCCESS",
                                          proposed_next=["DONE"], changes={})
            steps.append({
                "node": "DONE",
                "result": terminal_result,
                "world_state_snapshot": dict(self.world_state)
            })

        # Determine final goal/outcome
        goal = self._infer_conversation_goal(self.world_state, safety_counter >= 12)

        return {
            "steps": steps,
            "final_state": dict(self.world_state),
            "goal": goal,
            "success": safety_counter < 12,
            "total_steps": len(steps)
        }

    def _infer_conversation_goal(self, world_state: WorldState, aborted: bool) -> str:
        """Infer the final conversation goal based on world state."""
        if aborted:
            return "aborted_max_steps"

        if world_state.get("purchase_complete"):
            return "purchase_completed"
        elif world_state.get("order_resolved"):
            return "order_resolved"
        elif world_state.get("return_complete"):
            return "return_completed"
        elif world_state.get("recommendations_provided"):
            return "recommendations_provided"
        else:
            return "conversation_ended"

    def get_graph_info(self) -> Dict[str, Any]:
        """Get information about the conversation graph."""
        return {
            "total_nodes": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "nodes": list(self.graph.nodes(data=True)),
            "edges": list(self.graph.edges(data=True))
        }