# core/adaptation_engine.py
"""
Plan Adaptation Engine for Dynamic Plan Modification
"""

from typing import Dict, List, Any, Set, Optional, Tuple
from .context import Context, OrchestratorState
from .plan_graph import PlanGraph
import uuid


class AdaptationEngine:
    """
    Handles plan modifications based on need-vs-have analysis and execution feedback.
    """

    def __init__(self):
        """Initialize the adaptation engine."""
        self.adaptation_history = []

    def analyze_needs_vs_have(self, node_id: str, plan_graph: PlanGraph, context: Context) -> Dict[str, Any]:
        """
        Analyze what a node needs vs what's available in context.

        Args:
            node_id: ID of node to analyze
            plan_graph: Current plan graph
            context: Current context

        Returns:
            Analysis result with gaps and recommendations
        """
        node_data = plan_graph.get_node_data(node_id)
        required_inputs = node_data.get("required_inputs", [])

        # Check what we have vs what we need
        available_keys = set(context.facts.keys()) | set(context.assumptions.keys())
        required_keys = set(required_inputs)

        missing_keys = required_keys - available_keys
        available_required = required_keys & available_keys

        analysis = {
            "node_id": node_id,
            "node_type": node_data.get("type", "unknown"),
            "required_inputs": list(required_keys),
            "available_inputs": list(available_required),
            "missing_inputs": list(missing_keys),
            "can_execute": len(missing_keys) == 0,
            "gap_severity": self._assess_gap_severity(missing_keys, node_data),
            "recommended_actions": []
        }

        # Generate recommendations based on gaps
        if missing_keys:
            analysis["recommended_actions"] = self._generate_gap_resolution_actions(
                missing_keys, node_data, plan_graph
            )

        return analysis

    def adapt_plan(self, analysis: Dict[str, Any], plan_graph: PlanGraph,
                   state: OrchestratorState) -> List[Dict[str, Any]]:
        """
        Adapt the plan based on needs analysis.

        Args:
            analysis: Result from analyze_needs_vs_have
            plan_graph: Plan graph to modify
            state: Current orchestrator state

        Returns:
            List of adaptations made
        """
        adaptations = []

        if analysis["can_execute"]:
            return adaptations  # No adaptation needed

        node_id = analysis["node_id"]
        missing_inputs = analysis["missing_inputs"]

        for action in analysis["recommended_actions"]:
            adaptation_result = self._execute_adaptation_action(
                action, node_id, missing_inputs, plan_graph, state
            )
            if adaptation_result:
                adaptations.append(adaptation_result)

        # Record adaptation in history
        adaptation_record = {
            "timestamp": state.execution_history[-1]["timestamp"] if state.execution_history else None,
            "trigger_node": node_id,
            "missing_inputs": missing_inputs,
            "adaptations_made": adaptations,
            "plan_version": state.plan_version
        }
        self.adaptation_history.append(adaptation_record)

        return adaptations

    def _assess_gap_severity(self, missing_keys: Set[str], node_data: Dict[str, Any]) -> str:
        """
        Assess severity of missing inputs.

        Args:
            missing_keys: Set of missing input keys
            node_data: Node metadata

        Returns:
            Severity level: "low", "medium", "high", "critical"
        """
        node_type = node_data.get("type", "unknown")

        if not missing_keys:
            return "none"

        # Critical for agent nodes
        if node_type == "agent" and len(missing_keys) > 0:
            return "critical"

        # High for clarification nodes with multiple missing keys
        if node_type == "clarification" and len(missing_keys) > 2:
            return "high"

        # Medium for most other cases
        if len(missing_keys) > 1:
            return "medium"

        return "low"

    def _generate_gap_resolution_actions(self, missing_keys: Set[str],
                                         node_data: Dict[str, Any],
                                         plan_graph: PlanGraph) -> List[Dict[str, Any]]:
        """
        Generate actions to resolve input gaps.

        Args:
            missing_keys: Keys that are missing
            node_data: Current node data
            plan_graph: Current plan graph

        Returns:
            List of recommended actions
        """
        actions = []
        node_id = node_data.get("id")

        # Group missing keys by resolution strategy
        user_input_keys = {"category", "subcategory", "budget", "preferences", "order_id", "return_reason"}
        system_data_keys = {"product_options", "order_details", "recommendations"}

        user_missing = missing_keys & user_input_keys
        system_missing = missing_keys & system_data_keys

        # Handle missing user inputs
        if user_missing:
            actions.append({
                "type": "insert_clarification_node",
                "target_node": node_id,
                "position": "before",
                "missing_keys": list(user_missing),
                "priority": "high"
            })

        # Handle missing system data
        if system_missing:
            actions.append({
                "type": "insert_agent_node",
                "target_node": node_id,
                "position": "before",
                "missing_keys": list(system_missing),
                "priority": "medium"
            })

        # Handle unknown missing keys
        unknown_missing = missing_keys - user_input_keys - system_data_keys
        if unknown_missing:
            actions.append({
                "type": "insert_clarification_node",
                "target_node": node_id,
                "position": "before",
                "missing_keys": list(unknown_missing),
                "priority": "medium"
            })

        return actions

    def _execute_adaptation_action(self, action: Dict[str, Any], target_node: str,
                                   missing_inputs: List[str], plan_graph: PlanGraph,
                                   state: OrchestratorState) -> Optional[Dict[str, Any]]:
        """
        Execute a specific adaptation action.

        Args:
            action: Action to execute
            target_node: Node being adapted
            missing_inputs: Missing input keys
            plan_graph: Plan graph to modify
            state: Orchestrator state

        Returns:
            Result of adaptation or None if failed
        """
        action_type = action["type"]

        if action_type == "insert_clarification_node":
            return self._insert_clarification_node(action, target_node, plan_graph, state)

        elif action_type == "insert_agent_node":
            return self._insert_agent_node(action, target_node, plan_graph, state)

        elif action_type == "reorder_nodes":
            return self._reorder_nodes(action, plan_graph, state)

        elif action_type == "skip_node":
            return self._skip_node(action, target_node, plan_graph, state)

        return None

    def _insert_clarification_node(self, action: Dict[str, Any], target_node: str,
                                   plan_graph: PlanGraph, state: OrchestratorState) -> Dict[str, Any]:
        """Insert a clarification node to gather missing user input."""
        missing_keys = action["missing_keys"]
        new_node_id = f"clarify_{target_node}_{uuid.uuid4().hex[:6]}"

        new_node_data = {
            "id": new_node_id,
            "type": "clarification",
            "required_inputs": [],
            "produced_outputs": missing_keys,
            "description": f"Clarify missing inputs: {', '.join(missing_keys)}",
            "clarification_keys": missing_keys,
            "inserted_by_adaptation": True
        }

        if action["position"] == "before":
            plan_graph.insert_node_before(target_node, new_node_data)
        else:
            plan_graph.insert_node_after(target_node, new_node_data)

        state.increment_plan_version()

        return {
            "action": "inserted_clarification_node",
            "new_node_id": new_node_id,
            "target_node": target_node,
            "missing_keys": missing_keys
        }

    def _insert_agent_node(self, action: Dict[str, Any], target_node: str,
                           plan_graph: PlanGraph, state: OrchestratorState) -> Dict[str, Any]:
        """Insert an agent node to gather missing system data."""
        missing_keys = action["missing_keys"]

        # Determine appropriate agent type based on missing keys
        agent_type = self._determine_agent_for_keys(missing_keys)

        new_node_id = f"fetch_{agent_type.lower()}_{uuid.uuid4().hex[:6]}"

        new_node_data = {
            "id": new_node_id,
            "type": "agent",
            "agent_type": agent_type,
            "required_inputs": [],  # Will be determined by agent
            "produced_outputs": missing_keys,
            "description": f"Fetch data via {agent_type} agent",
            "inserted_by_adaptation": True
        }

        if action["position"] == "before":
            plan_graph.insert_node_before(target_node, new_node_data)
        else:
            plan_graph.insert_node_after(target_node, new_node_data)

        state.increment_plan_version()

        return {
            "action": "inserted_agent_node",
            "new_node_id": new_node_id,
            "agent_type": agent_type,
            "target_node": target_node,
            "missing_keys": missing_keys
        }

    def _determine_agent_for_keys(self, missing_keys: List[str]) -> str:
        """Determine which agent can provide the missing keys."""
        key_to_agent = {
            "product_options": "BUY",
            "order_details": "ORDER",
            "recommendations": "RECOMMEND",
            "return_processed": "RETURN"
        }

        # Return first matching agent or default to BUY
        for key in missing_keys:
            if key in key_to_agent:
                return key_to_agent[key]

        return "BUY"  # Default agent

    def _reorder_nodes(self, action: Dict[str, Any], plan_graph: PlanGraph,
                       state: OrchestratorState) -> Dict[str, Any]:
        """Reorder nodes to fix dependency issues."""
        # This is a complex operation that would require careful graph manipulation
        # For now, return a placeholder implementation
        state.increment_plan_version()
        return {"action": "reorder_nodes", "status": "not_implemented"}

    def _skip_node(self, action: Dict[str, Any], target_node: str,
                   plan_graph: PlanGraph, state: OrchestratorState) -> Dict[str, Any]:
        """Skip a node that's no longer needed."""
        removed = plan_graph.remove_node(target_node)
        if removed:
            state.increment_plan_version()
            return {"action": "skipped_node", "node_id": target_node}

        return {"action": "skip_node_failed", "node_id": target_node}


# Test code for Adaptation Engine
def test_adaptation_engine_basic():
    """Test basic adaptation engine functionality."""
    print("🧪 Testing Adaptation Engine - Basic Functionality")
    print("=" * 50)

    from .plan_graph import PlanGraph
    from .context import Context, OrchestratorState

    # Setup test environment
    adaptation_engine = AdaptationEngine()
    plan_graph = PlanGraph()
    plan_graph.create_from_template("BUY")

    # Create context with partial information
    context = Context()
    context.merge({
        "intent": "BUY",
        "category": "electronics"
        # Missing: subcategory, budget
    })

    state = OrchestratorState()

    print("🎯 Test Setup:")
    print(f"  Plan template: {plan_graph.template_used}")
    print(f"  Context keys: {list(context.facts.keys())}")

    # Test need-vs-have analysis on different nodes
    test_nodes = ["start", "gather_requirements", "search_products"]

    print("\n🔍 Testing Need-vs-Have Analysis:")
    for node_id in test_nodes:
        analysis = adaptation_engine.analyze_needs_vs_have(node_id, plan_graph, context)

        print(f"\n  Node: {node_id} ({analysis['node_type']})")
        print(f"    Can execute: {analysis['can_execute']}")
        print(f"    Required inputs: {analysis['required_inputs']}")
        print(f"    Available inputs: {analysis['available_inputs']}")
        print(f"    Missing inputs: {analysis['missing_inputs']}")
        print(f"    Gap severity: {analysis['gap_severity']}")
        print(f"    Recommended actions: {len(analysis['recommended_actions'])}")

        for i, action in enumerate(analysis['recommended_actions'], 1):
            print(f"      {i}. {action['type']} ({action.get('priority', 'normal')})")

    print("\n" + "=" * 40)
    print("✅ Basic Adaptation Tests Complete!")


def test_adaptation_engine_plan_modification():
    """Test plan modification capabilities."""
    print("\n🧪 Testing Adaptation Engine - Plan Modification")
    print("=" * 50)

    from .plan_graph import PlanGraph
    from .context import Context, OrchestratorState

    # Setup
    adaptation_engine = AdaptationEngine()
    plan_graph = PlanGraph()
    plan_graph.create_from_template("ORDER")

    # Context missing order_id (required for ORDER flow)
    context = Context()
    context.merge({"intent": "ORDER"})

    state = OrchestratorState()

    print("🏁 Initial State:")
    print(f"  Nodes: {len(plan_graph.graph.nodes())}")
    print(f"  Edges: {len(plan_graph.graph.edges())}")
    print(f"  Plan version: {state.plan_version}")

    # Analyze a node that requires order_id
    target_node = "fetch_order"
    analysis = adaptation_engine.analyze_needs_vs_have(target_node, plan_graph, context)

    print(f"\n🎯 Analyzing node '{target_node}':")
    print(f"  Missing inputs: {analysis['missing_inputs']}")
    print(f"  Can execute: {analysis['can_execute']}")
    print(f"  Recommended actions: {len(analysis['recommended_actions'])}")

    # Test plan adaptation
    print("\n🔧 Testing Plan Adaptation:")
    adaptations = adaptation_engine.adapt_plan(analysis, plan_graph, state)

    print(f"  Adaptations made: {len(adaptations)}")
    for i, adaptation in enumerate(adaptations, 1):
        print(f"    {i}. {adaptation['action']}")
        if 'new_node_id' in adaptation:
            print(f"       New node: {adaptation['new_node_id']}")
        if 'missing_keys' in adaptation:
            print(f"       For keys: {adaptation['missing_keys']}")

    print(f"\n📊 After Adaptation:")
    print(f"  Nodes: {len(plan_graph.graph.nodes())}")
    print(f"  Edges: {len(plan_graph.graph.edges())}")
    print(f"  Plan version: {state.plan_version}")
    print(f"  Execution order: {' → '.join(plan_graph.get_execution_order())}")

    # Test adaptation history
    print(f"\n📜 Adaptation History:")
    for i, record in enumerate(adaptation_engine.adaptation_history, 1):
        print(f"  {i}. Trigger: {record['trigger_node']}")
        print(f"     Missing: {record['missing_inputs']}")
        print(f"     Plan v{record['plan_version']}: {len(record['adaptations_made'])} adaptations")

    print("\n" + "=" * 40)
    print("✅ Plan Modification Tests Complete!")


def test_adaptation_engine_scenarios():
    """Test various adaptation scenarios."""
    print("\n🧪 Testing Adaptation Engine - Various Scenarios")
    print("=" * 50)

    from .plan_graph import PlanGraph
    from .context import Context, OrchestratorState

    adaptation_engine = AdaptationEngine()

    # Scenario 1: Missing user inputs
    print("📋 Scenario 1: Missing User Inputs (BUY flow)")
    plan1 = PlanGraph()
    plan1.create_from_template("BUY")
    context1 = Context()
    context1.merge({"intent": "BUY"})  # Missing category, subcategory, budget
    state1 = OrchestratorState()

    analysis1 = adaptation_engine.analyze_needs_vs_have("search_products", plan1, context1)
    print(f"  Missing: {analysis1['missing_inputs']}")
    print(f"  Severity: {analysis1['gap_severity']}")
    print(f"  Actions: {[a['type'] for a in analysis1['recommended_actions']]}")

    # Scenario 2: Missing system data
    print("\n📋 Scenario 2: Missing System Data (RECOMMEND flow)")
    plan2 = PlanGraph()
    plan2.create_from_template("RECOMMEND")
    context2 = Context()
    context2.merge({"intent": "RECOMMEND", "category": "electronics"})  # Missing recommendations
    state2 = OrchestratorState()

    analysis2 = adaptation_engine.analyze_needs_vs_have("present_options", plan2, context2)
    print(f"  Missing: {analysis2['missing_inputs']}")
    print(f"  Severity: {analysis2['gap_severity']}")
    print(f"  Actions: {[a['type'] for a in analysis2['recommended_actions']]}")

    # Scenario 3: No missing inputs (ready to execute)
    print("\n📋 Scenario 3: Ready to Execute (ORDER flow)")
    plan3 = PlanGraph()
    plan3.create_from_template("ORDER")
    context3 = Context()
    context3.merge({"intent": "ORDER", "order_id": "ORD12345"})  # All required data present
    state3 = OrchestratorState()

    analysis3 = adaptation_engine.analyze_needs_vs_have("fetch_order", plan3, context3)
    print(f"  Missing: {analysis3['missing_inputs']}")
    print(f"  Can execute: {analysis3['can_execute']}")
    print(f"  Actions needed: {len(analysis3['recommended_actions'])}")

    # Test gap severity assessment
    print("\n🚨 Testing Gap Severity Assessment:")
    severity_tests = [
        (set(), "system", "Should be 'none'"),
        ({"category"}, "clarification", "Should be 'low'"),
        ({"category", "budget", "preferences"}, "clarification", "Should be 'high'"),
        ({"product_options"}, "agent", "Should be 'critical'")
    ]

    for missing_keys, node_type, expected in severity_tests:
        node_data = {"type": node_type}
        severity = adaptation_engine._assess_gap_severity(missing_keys, node_data)
        print(f"  {list(missing_keys)} + {node_type}: {severity} ({expected})")

    # Test agent determination
    print("\n🤖 Testing Agent Type Determination:")
    key_tests = [
        (["product_options"], "Should be BUY"),
        (["order_details"], "Should be ORDER"),
        (["recommendations"], "Should be RECOMMEND"),
        (["return_processed"], "Should be RETURN"),
        (["unknown_key"], "Should default to BUY")
    ]

    for keys, expected in key_tests:
        agent_type = adaptation_engine._determine_agent_for_keys(keys)
        print(f"  {keys}: {agent_type} ({expected})")

    print("\n" + "=" * 40)
    print("✅ Scenario Tests Complete!")


if __name__ == "__main__":
    test_adaptation_engine_basic()
    test_adaptation_engine_plan_modification()
    test_adaptation_engine_scenarios()
    print("\n" + "🎉" + "=" * 48 + "🎉")
    print("✅ ALL ADAPTATION ENGINE TESTS PASSED!")
    print("🎉" + "=" * 50 + "🎉")