# core/execution_controller.py
"""
Plan Execution Controller with Need-vs-Have Analysis
"""

from typing import Dict, List, Any, Optional, Tuple
from .context import Context, OrchestratorState
from .plan_graph import PlanGraph
from .adaptation_engine import AdaptationEngine
from .agent_contracts import AgentRequest, AgentResponse, AgentInvoker


class ExecutionController:
    """
    Controls plan execution with need-vs-have checks and adaptive behavior.
    """

    def __init__(self, agent_invoker: Optional[AgentInvoker] = None):
        """
        Initialize execution controller.

        Args:
            agent_invoker: Agent invoker instance for calling agents
        """
        self.adaptation_engine = AdaptationEngine()
        self.agent_invoker = agent_invoker or AgentInvoker()
        self.execution_log = []

    def execute_plan(self, plan_graph: PlanGraph, context: Context,
                     state: OrchestratorState) -> Dict[str, Any]:
        """
        Execute the plan with adaptive behavior.

        Args:
            plan_graph: Plan to execute
            context: Current context
            state: Orchestrator state

        Returns:
            Execution result with status and outputs
        """
        current_node = plan_graph.get_start_node()
        state.current_node = current_node

        execution_result = {
            "status": "running",
            "completed_nodes": [],
            "failed_nodes": [],
            "adaptations_made": [],
            "final_context": None,
            "execution_path": []
        }

        safety_counter = 0
        max_iterations = 20

        while current_node and safety_counter < max_iterations:
            safety_counter += 1

            # Execute current node with need-vs-have analysis
            node_result = self.execute_node(current_node, plan_graph, context, state)

            execution_result["execution_path"].append({
                "node_id": current_node,
                "result": node_result
            })

            if node_result["status"] == "success":
                execution_result["completed_nodes"].append(current_node)
                state.mark_completed(current_node)

                # Move to next node
                next_nodes = plan_graph.get_next_nodes(current_node)
                current_node = next_nodes[0] if next_nodes else None

            elif node_result["status"] == "adapted":
                # Plan was adapted, continue with same node
                execution_result["adaptations_made"].extend(node_result.get("adaptations", []))
                continue

            elif node_result["status"] == "failed":
                execution_result["failed_nodes"].append(current_node)
                state.mark_failed(current_node, node_result.get("error", "Unknown error"))
                break

            # Check for terminal nodes
            node_data = plan_graph.get_node_data(current_node) if current_node else {}
            if node_data.get("type") == "terminal":
                break

        execution_result["status"] = "completed" if not execution_result["failed_nodes"] else "failed"
        execution_result["final_context"] = context.to_dict()

        return execution_result

    def execute_node(self, node_id: str, plan_graph: PlanGraph,
                     context: Context, state: OrchestratorState) -> Dict[str, Any]:
        """
        Execute a single node with need-vs-have analysis.

        Args:
            node_id: ID of node to execute
            plan_graph: Current plan graph
            context: Current context
            state: Orchestrator state

        Returns:
            Node execution result
        """
        # Step 1: Analyze needs vs have
        analysis = self.adaptation_engine.analyze_needs_vs_have(node_id, plan_graph, context)

        # Step 2: If gaps exist, attempt adaptation
        if not analysis["can_execute"]:
            adaptations = self.adaptation_engine.adapt_plan(analysis, plan_graph, state)

            if adaptations:
                return {
                    "status": "adapted",
                    "node_id": node_id,
                    "analysis": analysis,
                    "adaptations": adaptations
                }
            else:
                return {
                    "status": "failed",
                    "node_id": node_id,
                    "error": f"Cannot execute node - missing inputs: {analysis['missing_inputs']}"
                }

        # Step 3: Execute the node
        return self._execute_node_action(node_id, plan_graph, context, state)

    def _execute_node_action(self, node_id: str, plan_graph: PlanGraph,
                             context: Context, state: OrchestratorState) -> Dict[str, Any]:
        """
        Execute the actual node action.

        Args:
            node_id: Node to execute
            plan_graph: Plan graph
            context: Current context
            state: Orchestrator state

        Returns:
            Execution result
        """
        node_data = plan_graph.get_node_data(node_id)
        node_type = node_data.get("type", "unknown")

        try:
            if node_type == "system":
                return self._execute_system_node(node_id, node_data, context, state)

            elif node_type == "agent":
                return self._execute_agent_node(node_id, node_data, context, state)

            elif node_type == "clarification":
                return self._execute_clarification_node(node_id, node_data, context, state)

            elif node_type == "terminal":
                return self._execute_terminal_node(node_id, node_data, context, state)

            else:
                return {
                    "status": "failed",
                    "node_id": node_id,
                    "error": f"Unknown node type: {node_type}"
                }

        except Exception as e:
            return {
                "status": "failed",
                "node_id": node_id,
                "error": f"Node execution error: {str(e)}"
            }

    def _execute_system_node(self, node_id: str, node_data: Dict[str, Any],
                             context: Context, state: OrchestratorState) -> Dict[str, Any]:
        """Execute a system node (no external calls)."""
        description = node_data.get("description", "System operation")

        # System nodes typically just mark progress or perform internal operations
        state.add_to_history("system_node_executed", {
            "node_id": node_id,
            "description": description
        })

        return {
            "status": "success",
            "node_id": node_id,
            "node_type": "system",
            "outputs": {},
            "message": f"System node executed: {description}"
        }

    def _execute_agent_node(self, node_id: str, node_data: Dict[str, Any],
                            context: Context, state: OrchestratorState) -> Dict[str, Any]:
        """Execute an agent node by calling the appropriate agent."""
        agent_type = node_data.get("agent_type", "BUY")

        # Prepare agent request
        agent_request = AgentRequest(
            trace_id=f"exec_{node_id}_{state.plan_version}",
            context=context.to_dict(),
            parameters={
                "node_id": node_id,
                "required_outputs": node_data.get("produced_outputs", [])
            },
            timeout=30
        )

        # Call agent
        agent_response = self.agent_invoker.invoke_agent(agent_type, agent_request)

        # Process response
        if agent_response.status == "success":
            # Merge agent outputs into context
            if agent_response.context_updates:
                context.merge(agent_response.context_updates)

            # Store artifacts
            if agent_response.result:
                state.add_artifact(f"{node_id}_result", agent_response.result)

            return {
                "status": "success",
                "node_id": node_id,
                "node_type": "agent",
                "agent_type": agent_type,
                "outputs": agent_response.result,
                "context_updates": agent_response.context_updates
            }
        else:
            return {
                "status": "failed",
                "node_id": node_id,
                "node_type": "agent",
                "agent_type": agent_type,
                "error": agent_response.error or "Agent execution failed"
            }

    def _execute_clarification_node(self, node_id: str, node_data: Dict[str, Any],
                                    context: Context, state: OrchestratorState) -> Dict[str, Any]:
        """Execute a clarification node (would typically prompt user)."""
        clarification_keys = node_data.get("clarification_keys", node_data.get("produced_outputs", []))

        # For now, simulate clarification by checking if we have the data
        # In real implementation, this would trigger user interaction

        missing_keys = []
        for key in clarification_keys:
            if context.get(key) is None:
                missing_keys.append(key)

        if missing_keys:
            # Mark that clarification is needed
            state.add_to_history("clarification_needed", {
                "node_id": node_id,
                "missing_keys": missing_keys
            })

            return {
                "status": "failed",  # Would be "waiting" in real implementation
                "node_id": node_id,
                "node_type": "clarification",
                "error": f"User input needed for: {', '.join(missing_keys)}",
                "clarification_needed": missing_keys
            }
        else:
            return {
                "status": "success",
                "node_id": node_id,
                "node_type": "clarification",
                "outputs": {key: context.get(key) for key in clarification_keys},
                "message": "Clarification completed"
            }

    def _execute_terminal_node(self, node_id: str, node_data: Dict[str, Any],
                               context: Context, state: OrchestratorState) -> Dict[str, Any]:
        """Execute a terminal node (end of flow)."""
        state.conversation_active = False
        state.add_to_history("flow_completed", {
            "node_id": node_id,
            "final_context": context.to_dict()
        })

        return {
            "status": "success",
            "node_id": node_id,
            "node_type": "terminal",
            "outputs": {},
            "message": "Flow completed successfully"
        }


# Test code for ExecutionController
def test_execution_controller():
    """Test the execution controller with a simple plan."""
    print("🧪 Testing Execution Controller")
    print("=" * 50)

    from .plan_templates import PlanTemplates

    # Create a simple test plan
    plan_graph = PlanGraph()
    plan_graph.create_from_template("BUY")

    # Create test context with some data
    context = Context()
    context.merge({
        "intent": "BUY",
        "category": "electronics",
        "subcategory": "laptop"
    })

    # Create orchestrator state
    state = OrchestratorState()

    # Create execution controller
    controller = ExecutionController()

    print("📋 Initial Plan:")
    execution_order = plan_graph.get_execution_order()
    for node_id in execution_order:
        node_data = plan_graph.get_node_data(node_id)
        print(f"  - {node_id} ({node_data.get('type', 'unknown')})")

    print(f"\n🎯 Initial Context: {list(context.facts.keys())}")

    # Test need-vs-have analysis on first few nodes
    print("\n🔍 Need-vs-Have Analysis:")
    for node_id in execution_order[:3]:
        analysis = controller.adaptation_engine.analyze_needs_vs_have(node_id, plan_graph, context)
        print(f"  Node '{node_id}':")
        print(f"    - Can execute: {analysis['can_execute']}")
        print(f"    - Missing: {analysis['missing_inputs']}")
        print(f"    - Severity: {analysis['gap_severity']}")
        if analysis['recommended_actions']:
            print(f"    - Actions: {len(analysis['recommended_actions'])} recommended")

    print("\n" + "=" * 50)
    print("✅ Execution Controller Test Complete!")


if __name__ == "__main__":
    test_execution_controller()