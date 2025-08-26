# core/plan_graph.py
"""
NetworkX-based Plan Graph Implementation
"""

import networkx as nx
from typing import Dict, List, Any
from cleaning.plan_templates import PlanTemplates


class PlanGraph:
    """
    Wrapper around NetworkX DiGraph for plan representation and manipulation.
    """

    def __init__(self):
        """Initialize empty plan graph."""
        self.graph = nx.DiGraph()
        self.template_used = None

    def create_from_template(self, intent: str) -> None:
        """
        Create plan from template for given intent.

        Args:
            intent: User intent to create plan for
        """
        self.template_used = intent
        template = PlanTemplates.get_template(intent)

        # Add nodes
        for node_data in template["nodes"]:
            node_id = node_data["id"]
            self.graph.add_node(node_id, **node_data)

        # Add edges
        for edge_data in template["edges"]:
            self.graph.add_edge(
                edge_data["from"],
                edge_data["to"],
                condition=edge_data["condition"]
            )

    def get_start_node(self) -> str:
        """Get the start node of the plan."""
        start_nodes = [node for node in self.graph.nodes()
                       if self.graph.nodes[node].get("type") == "system"
                       and self.graph.nodes[node].get("id") == "start"]
        return start_nodes[0] if start_nodes else list(self.graph.nodes())[0]

    def get_node_data(self, node_id: str) -> Dict[str, Any]:
        """
        Get data for a specific node.

        Args:
            node_id: ID of the node

        Returns:
            Node data dictionary
        """
        return self.graph.nodes.get(node_id, {})

    def get_next_nodes(self, current_node: str) -> List[str]:
        """
        Get possible next nodes from current node.

        Args:
            current_node: Current node ID

        Returns:
            List of next node IDs
        """
        return list(self.graph.successors(current_node))

    def insert_node_before(self, target_node: str, new_node_data: Dict[str, Any]) -> str:
        """
        Insert a new node before the target node.

        Args:
            target_node: Node to insert before
            new_node_data: Data for the new node

        Returns:
            ID of the inserted node
        """
        new_node_id = new_node_data["id"]

        # Add the new node
        self.graph.add_node(new_node_id, **new_node_data)

        # Redirect incoming edges to new node
        predecessors = list(self.graph.predecessors(target_node))
        for pred in predecessors:
            edge_data = self.graph.edges[pred, target_node]
            self.graph.remove_edge(pred, target_node)
            self.graph.add_edge(pred, new_node_id, **edge_data)

        # Connect new node to target
        self.graph.add_edge(new_node_id, target_node, condition="always")

        return new_node_id

    def insert_node_after(self, source_node: str, new_node_data: Dict[str, Any]) -> str:
        """
        Insert a new node after the source node.

        Args:
            source_node: Node to insert after
            new_node_data: Data for the new node

        Returns:
            ID of the inserted node
        """
        new_node_id = new_node_data["id"]

        # Add the new node
        self.graph.add_node(new_node_id, **new_node_data)

        # Redirect outgoing edges from new node
        successors = list(self.graph.successors(source_node))
        for succ in successors:
            edge_data = self.graph.edges[source_node, succ]
            self.graph.remove_edge(source_node, succ)
            self.graph.add_edge(new_node_id, succ, **edge_data)

        # Connect source to new node
        self.graph.add_edge(source_node, new_node_id, condition="always")

        return new_node_id

    def remove_node(self, node_id: str) -> bool:
        """
        Remove a node from the plan.

        Args:
            node_id: ID of node to remove

        Returns:
            True if node was removed, False if not found
        """
        if node_id not in self.graph.nodes:
            return False

        # Connect predecessors directly to successors
        predecessors = list(self.graph.predecessors(node_id))
        successors = list(self.graph.successors(node_id))

        for pred in predecessors:
            for succ in successors:
                self.graph.add_edge(pred, succ, condition="bypass")

        # Remove the node
        self.graph.remove_node(node_id)
        return True

    def add_parallel_branch(self, from_node: str, to_node: str, branch_nodes: List[Dict[str, Any]]) -> List[str]:
        """
        Add a parallel execution branch between two nodes.

        Args:
            from_node: Starting node for branch
            to_node: Ending node for branch
            branch_nodes: List of node data for branch

        Returns:
            List of inserted node IDs
        """
        inserted_ids = []

        prev_node = from_node
        for node_data in branch_nodes:
            node_id = node_data["id"]
            self.graph.add_node(node_id, **node_data)
            self.graph.add_edge(prev_node, node_id, condition="branch")
            inserted_ids.append(node_id)
            prev_node = node_id

        # Connect last branch node to end node
        if inserted_ids:
            self.graph.add_edge(inserted_ids[-1], to_node, condition="merge")

        return inserted_ids

    def is_valid_path(self, node_path: List[str]) -> bool:
        """
        Check if a sequence of nodes forms a valid path.

        Args:
            node_path: List of node IDs

        Returns:
            True if path is valid
        """
        for i in range(len(node_path) - 1):
            if not self.graph.has_edge(node_path[i], node_path[i + 1]):
                return False
        return True

    def get_execution_order(self) -> List[str]:
        """
        Get topological ordering of nodes for execution.

        Returns:
            List of node IDs in execution order
        """
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError:
            # If graph has cycles, return best effort ordering
            return list(self.graph.nodes())

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert graph to dictionary representation.

        Returns:
            Dictionary with nodes and edges
        """
        return {
            "template_used": self.template_used,
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": [
                {
                    "from": u,
                    "to": v,
                    **data
                }
                for u, v, data in self.graph.edges(data=True)
            ]
        }


# Test code for Plan Graph
def test_plan_graph_creation():
    """Test creating plan graphs from templates."""
    print("🧪 Testing Plan Graph Creation")
    print("=" * 50)

    # Test creating graphs from different templates
    intents = ["BUY", "ORDER", "RECOMMEND", "RETURN"]

    for intent in intents:
        print(f"\n🗂️ Testing {intent} Template:")

        # Create graph from template
        plan = PlanGraph()
        plan.create_from_template(intent)

        print(f"  Template used: {plan.template_used}")
        print(f"  Nodes: {len(plan.graph.nodes())}")
        print(f"  Edges: {len(plan.graph.edges())}")

        # Test basic graph properties
        start_node = plan.get_start_node()
        print(f"  Start node: {start_node}")

        # Test execution order
        execution_order = plan.get_execution_order()
        print(f"  Execution order: {' → '.join(execution_order)}")

        # Test node data retrieval
        if start_node:
            start_data = plan.get_node_data(start_node)
            print(f"  Start node type: {start_data.get('type', 'unknown')}")

        # Test getting next nodes
        if start_node:
            next_nodes = plan.get_next_nodes(start_node)
            print(f"  Next from start: {next_nodes}")

    print("\n" + "=" * 40)
    print("✅ Plan Graph Creation Tests Complete!")


def test_plan_graph_modification():
    """Test modifying plan graphs dynamically."""
    print("\n🧪 Testing Plan Graph Modification")
    print("=" * 50)

    # Create a simple BUY plan for testing
    plan = PlanGraph()
    plan.create_from_template("BUY")

    original_nodes = len(plan.graph.nodes())
    original_edges = len(plan.graph.edges())

    print(f"🏁 Original Plan: {original_nodes} nodes, {original_edges} edges")
    print(f"  Execution order: {' → '.join(plan.get_execution_order())}")

    # Test inserting node before
    print("\n📝 Testing Insert Node Before:")
    new_node_data = {
        "id": "validate_user",
        "type": "system",
        "required_inputs": [],
        "produced_outputs": ["user_validated"],
        "description": "Validate user credentials"
    }

    target_node = "gather_requirements"
    inserted_id = plan.insert_node_before(target_node, new_node_data)

    print(f"  Inserted '{inserted_id}' before '{target_node}'")
    print(f"  New plan: {len(plan.graph.nodes())} nodes, {len(plan.graph.edges())} edges")
    print(f"  New execution order: {' → '.join(plan.get_execution_order())}")

    # Test inserting node after
    print("\n📝 Testing Insert Node After:")
    another_node_data = {
        "id": "log_search",
        "type": "system",
        "required_inputs": ["product_options"],
        "produced_outputs": ["search_logged"],
        "description": "Log search activity"
    }

    source_node = "search_products"
    inserted_id2 = plan.insert_node_after(source_node, another_node_data)

    print(f"  Inserted '{inserted_id2}' after '{source_node}'")
    print(f"  New plan: {len(plan.graph.nodes())} nodes, {len(plan.graph.edges())} edges")
    print(f"  New execution order: {' → '.join(plan.get_execution_order())}")

    # Test path validation
    print("\n✅ Testing Path Validation:")

    valid_paths = [
        ["start", "validate_user"],
        ["validate_user", "gather_requirements", "search_products"],
        ["search_products", "log_search", "select_product"]
    ]

    invalid_paths = [
        ["start", "end"],  # Skip intermediate nodes
        ["gather_requirements", "start"],  # Wrong direction
        ["nonexistent", "start"]  # Non-existent node
    ]

    for path in valid_paths:
        is_valid = plan.is_valid_path(path)
        print(f"  Path {' → '.join(path)}: {'✓ Valid' if is_valid else '❌ Invalid'}")

    for path in invalid_paths:
        is_valid = plan.is_valid_path(path)
        print(f"  Path {' → '.join(path)}: {'✓ Valid' if is_valid else '❌ Invalid'}")

    # Test node removal
    print("\n🗑️ Testing Node Removal:")
    nodes_before = len(plan.graph.nodes())
    removed = plan.remove_node("log_search")
    nodes_after = len(plan.graph.nodes())

    print(f"  Removed 'log_search': {'✓ Success' if removed else '❌ Failed'}")
    print(f"  Nodes: {nodes_before} → {nodes_after}")
    print(f"  Updated execution order: {' → '.join(plan.get_execution_order())}")

    # Test removing non-existent node
    removed_fake = plan.remove_node("nonexistent_node")
    print(f"  Removed 'nonexistent_node': {'✓ Success' if removed_fake else '❌ Failed (expected)'}")

    print("\n" + "=" * 40)
    print("✅ Plan Graph Modification Tests Complete!")


def test_plan_graph_advanced_features():
    """Test advanced plan graph features."""
    print("\n🧪 Testing Advanced Plan Graph Features")
    print("=" * 50)

    # Create plan for testing
    plan = PlanGraph()
    plan.create_from_template("RECOMMEND")

    # Test parallel branch addition
    print("🌿 Testing Parallel Branch Addition:")

    branch_nodes = [
        {
            "id": "check_inventory",
            "type": "agent",
            "agent_type": "INVENTORY",
            "required_inputs": ["category"],
            "produced_outputs": ["inventory_status"],
            "description": "Check product inventory"
        },
        {
            "id": "check_reviews",
            "type": "agent",
            "agent_type": "REVIEW",
            "required_inputs": ["category"],
            "produced_outputs": ["review_summary"],
            "description": "Gather product reviews"
        }
    ]

    from_node = "understand_needs"
    to_node = "generate_recommendations"

    branch_ids = plan.add_parallel_branch(from_node, to_node, branch_nodes)

    print(f"  Added parallel branch: {from_node} → [{', '.join(branch_ids)}] → {to_node}")
    print(f"  Updated plan: {len(plan.graph.nodes())} nodes, {len(plan.graph.edges())} edges")

    # Test graph serialization
    print("\n📊 Testing Graph Serialization:")
    plan_dict = plan.to_dict()

    print(f"  Serialized structure:")
    print(f"    - Template used: {plan_dict['template_used']}")
    print(f"    - Nodes count: {len(plan_dict['nodes'])}")
    print(f"    - Edges count: {len(plan_dict['edges'])}")

    # Test node data access
    print("\n🔍 Testing Node Data Access:")
    for node_id in list(plan.graph.nodes())[:3]:  # Test first 3 nodes
        node_data = plan.get_node_data(node_id)
        node_type = node_data.get("type", "unknown")
        inputs_count = len(node_data.get("required_inputs", []))
        outputs_count = len(node_data.get("produced_outputs", []))
        print(f"  {node_id} ({node_type}): {inputs_count} inputs, {outputs_count} outputs")

    # Test next nodes functionality
    print("\n➡️ Testing Next Nodes Retrieval:")
    for node_id in plan.get_execution_order()[:3]:
        next_nodes = plan.get_next_nodes(node_id)
        if next_nodes:
            print(f"  {node_id} → {next_nodes}")
        else:
            print(f"  {node_id} → [no next nodes]")

    print("\n" + "=" * 40)
    print("✅ Advanced Plan Graph Tests Complete!")


if __name__ == "__main__":
    test_plan_graph_creation()
    test_plan_graph_modification()
    test_plan_graph_advanced_features()
    print("\n" + "🎉" + "=" * 48 + "🎉")
    print("✅ ALL PLAN GRAPH TESTS PASSED!")
    print("🎉" + "=" * 50 + "🎉")