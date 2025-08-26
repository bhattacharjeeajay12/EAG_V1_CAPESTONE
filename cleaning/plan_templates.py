# core/plan_templates.py
"""
Plan Templates for Different User Intents
"""

from typing import Dict, List, Any


class PlanTemplates:
    """
    Defines template plans for different user intents.
    Each template is a blueprint that gets instantiated and adapted during execution.
    """

    @staticmethod
    def get_template(intent: str) -> Dict[str, Any]:
        """
        Get plan template for the given intent.

        Args:
            intent: User intent (BUY, ORDER, RECOMMEND, RETURN)

        Returns:
            Dictionary containing nodes and edges for the plan template
        """
        templates = {
            "BUY": PlanTemplates._buy_template(),
            "ORDER": PlanTemplates._order_template(),
            "RECOMMEND": PlanTemplates._recommend_template(),
            "RETURN": PlanTemplates._return_template()
        }

        return templates.get(intent, PlanTemplates._default_template())

    @staticmethod
    def get_all_templates() -> Dict[str, Dict[str, Any]]:
        """Get all available templates."""
        return {
            "BUY": PlanTemplates._buy_template(),
            "ORDER": PlanTemplates._order_template(),
            "RECOMMEND": PlanTemplates._recommend_template(),
            "RETURN": PlanTemplates._return_template(),
            "DEFAULT": PlanTemplates._default_template()
        }

    @staticmethod
    def _buy_template() -> Dict[str, Any]:
        """Template for purchase flow."""
        return {
            "nodes": [
                {
                    "id": "start",
                    "type": "system",
                    "required_inputs": [],
                    "produced_outputs": [],
                    "description": "Entry point for buy flow"
                },
                {
                    "id": "gather_requirements",
                    "type": "clarification",
                    "required_inputs": ["intent"],
                    "produced_outputs": ["category", "subcategory", "budget"],
                    "description": "Collect product requirements from user"
                },
                {
                    "id": "search_products",
                    "type": "agent",
                    "agent_type": "BUY",
                    "required_inputs": ["category", "subcategory"],
                    "produced_outputs": ["product_options"],
                    "description": "Search for products matching criteria"
                },
                {
                    "id": "select_product",
                    "type": "clarification",
                    "required_inputs": ["product_options"],
                    "produced_outputs": ["selected_product"],
                    "description": "User selects from product options"
                },
                {
                    "id": "confirm_purchase",
                    "type": "agent",
                    "agent_type": "BUY",
                    "required_inputs": ["selected_product"],
                    "produced_outputs": ["purchase_confirmed"],
                    "description": "Confirm purchase details"
                },
                {
                    "id": "end",
                    "type": "terminal",
                    "required_inputs": ["purchase_confirmed"],
                    "produced_outputs": [],
                    "description": "End of buy flow"
                }
            ],
            "edges": [
                {"from": "start", "to": "gather_requirements", "condition": "always"},
                {"from": "gather_requirements", "to": "search_products", "condition": "has_requirements"},
                {"from": "search_products", "to": "select_product", "condition": "products_found"},
                {"from": "select_product", "to": "confirm_purchase", "condition": "product_selected"},
                {"from": "confirm_purchase", "to": "end", "condition": "purchase_confirmed"}
            ]
        }

    @staticmethod
    def _order_template() -> Dict[str, Any]:
        """Template for order management flow."""
        return {
            "nodes": [
                {
                    "id": "start",
                    "type": "system",
                    "required_inputs": [],
                    "produced_outputs": [],
                    "description": "Entry point for order flow"
                },
                {
                    "id": "get_order_id",
                    "type": "clarification",
                    "required_inputs": [],
                    "produced_outputs": ["order_id"],
                    "description": "Get order ID from user"
                },
                {
                    "id": "fetch_order",
                    "type": "agent",
                    "agent_type": "ORDER",
                    "required_inputs": ["order_id"],
                    "produced_outputs": ["order_details"],
                    "description": "Fetch order information"
                },
                {
                    "id": "display_status",
                    "type": "system",
                    "required_inputs": ["order_details"],
                    "produced_outputs": ["status_displayed"],
                    "description": "Display order status to user"
                },
                {
                    "id": "end",
                    "type": "terminal",
                    "required_inputs": ["status_displayed"],
                    "produced_outputs": [],
                    "description": "End of order flow"
                }
            ],
            "edges": [
                {"from": "start", "to": "get_order_id", "condition": "always"},
                {"from": "get_order_id", "to": "fetch_order", "condition": "has_order_id"},
                {"from": "fetch_order", "to": "display_status", "condition": "order_found"},
                {"from": "display_status", "to": "end", "condition": "always"}
            ]
        }

    @staticmethod
    def _recommend_template() -> Dict[str, Any]:
        """Template for recommendation flow."""
        return {
            "nodes": [
                {
                    "id": "start",
                    "type": "system",
                    "required_inputs": [],
                    "produced_outputs": [],
                    "description": "Entry point for recommendation flow"
                },
                {
                    "id": "understand_needs",
                    "type": "clarification",
                    "required_inputs": [],
                    "produced_outputs": ["category", "preferences"],
                    "description": "Understand user needs and preferences"
                },
                {
                    "id": "generate_recommendations",
                    "type": "agent",
                    "agent_type": "RECOMMEND",
                    "required_inputs": ["category", "preferences"],
                    "produced_outputs": ["recommendations"],
                    "description": "Generate product recommendations"
                },
                {
                    "id": "present_options",
                    "type": "system",
                    "required_inputs": ["recommendations"],
                    "produced_outputs": ["options_presented"],
                    "description": "Present recommendations to user"
                },
                {
                    "id": "end",
                    "type": "terminal",
                    "required_inputs": ["options_presented"],
                    "produced_outputs": [],
                    "description": "End of recommendation flow"
                }
            ],
            "edges": [
                {"from": "start", "to": "understand_needs", "condition": "always"},
                {"from": "understand_needs", "to": "generate_recommendations", "condition": "needs_clear"},
                {"from": "generate_recommendations", "to": "present_options", "condition": "recommendations_ready"},
                {"from": "present_options", "to": "end", "condition": "always"}
            ]
        }

    @staticmethod
    def _return_template() -> Dict[str, Any]:
        """Template for return flow."""
        return {
            "nodes": [
                {
                    "id": "start",
                    "type": "system",
                    "required_inputs": [],
                    "produced_outputs": [],
                    "description": "Entry point for return flow"
                },
                {
                    "id": "get_return_details",
                    "type": "clarification",
                    "required_inputs": [],
                    "produced_outputs": ["order_id", "return_reason"],
                    "description": "Get order ID and return reason"
                },
                {
                    "id": "process_return",
                    "type": "agent",
                    "agent_type": "RETURN",
                    "required_inputs": ["order_id", "return_reason"],
                    "produced_outputs": ["return_processed"],
                    "description": "Process the return request"
                },
                {
                    "id": "confirm_return",
                    "type": "system",
                    "required_inputs": ["return_processed"],
                    "produced_outputs": ["return_confirmed"],
                    "description": "Confirm return with user"
                },
                {
                    "id": "end",
                    "type": "terminal",
                    "required_inputs": ["return_confirmed"],
                    "produced_outputs": [],
                    "description": "End of return flow"
                }
            ],
            "edges": [
                {"from": "start", "to": "get_return_details", "condition": "always"},
                {"from": "get_return_details", "to": "process_return", "condition": "details_provided"},
                {"from": "process_return", "to": "confirm_return", "condition": "return_accepted"},
                {"from": "confirm_return", "to": "end", "condition": "always"}
            ]
        }

    @staticmethod
    def _default_template() -> Dict[str, Any]:
        """Default template for unknown intents."""
        return {
            "nodes": [
                {
                    "id": "start",
                    "type": "system",
                    "required_inputs": [],
                    "produced_outputs": [],
                    "description": "Entry point"
                },
                {
                    "id": "clarify_intent",
                    "type": "clarification",
                    "required_inputs": [],
                    "produced_outputs": ["intent"],
                    "description": "Clarify user intent"
                },
                {
                    "id": "end",
                    "type": "terminal",
                    "required_inputs": ["intent"],
                    "produced_outputs": [],
                    "description": "End after clarification"
                }
            ],
            "edges": [
                {"from": "start", "to": "clarify_intent", "condition": "always"},
                {"from": "clarify_intent", "to": "end", "condition": "always"}
            ]
        }


# Test code for Plan Templates
def test_plan_templates():
    """Test plan templates functionality."""
    print("🧪 Testing Plan Templates")
    print("=" * 50)

    # Test getting individual templates
    intents = ["BUY", "ORDER", "RECOMMEND", "RETURN", "UNKNOWN"]

    print("🗂️ Testing Individual Template Retrieval:")
    for intent in intents:
        template = PlanTemplates.get_template(intent)
        nodes_count = len(template.get("nodes", []))
        edges_count = len(template.get("edges", []))
        print(f"  {intent}: {nodes_count} nodes, {edges_count} edges")

        # Validate template structure
        if nodes_count > 0:
            start_nodes = [n for n in template["nodes"] if n["id"] == "start"]
            end_nodes = [n for n in template["nodes"] if n["type"] == "terminal"]
            print(f"    ✓ Has start: {len(start_nodes) > 0}, Has end: {len(end_nodes) > 0}")

    print("\n📋 Testing Template Details - BUY Flow:")
    buy_template = PlanTemplates.get_template("BUY")

    print("  Nodes:")
    for i, node in enumerate(buy_template["nodes"], 1):
        node_type = node.get("type", "unknown")
        required = len(node.get("required_inputs", []))
        produced = len(node.get("produced_outputs", []))
        print(f"    {i}. {node['id']} ({node_type}) - Needs: {required}, Produces: {produced}")

    print("\n  Edges:")
    for i, edge in enumerate(buy_template["edges"], 1):
        print(f"    {i}. {edge['from']} → {edge['to']} (when: {edge['condition']})")

    print("\n🔍 Testing Template Validation:")

    # Test node-edge consistency
    def validate_template_consistency(template_name: str, template: Dict[str, Any]) -> List[str]:
        """Validate that all edges reference existing nodes."""
        errors = []
        node_ids = {node["id"] for node in template.get("nodes", [])}

        for edge in template.get("edges", []):
            if edge["from"] not in node_ids:
                errors.append(f"Edge references non-existent 'from' node: {edge['from']}")
            if edge["to"] not in node_ids:
                errors.append(f"Edge references non-existent 'to' node: {edge['to']}")

        return errors

    for intent in ["BUY", "ORDER", "RECOMMEND", "RETURN"]:
        template = PlanTemplates.get_template(intent)
        errors = validate_template_consistency(intent, template)
        if errors:
            print(f"  ❌ {intent}: {len(errors)} errors")
            for error in errors:
                print(f"    - {error}")
        else:
            print(f"  ✅ {intent}: Valid template structure")

    print("\n📊 Testing All Templates Retrieval:")
    all_templates = PlanTemplates.get_all_templates()
    print(f"  Available templates: {list(all_templates.keys())}")

    total_nodes = sum(len(template.get("nodes", [])) for template in all_templates.values())
    total_edges = sum(len(template.get("edges", [])) for template in all_templates.values())
    print(f"  Total nodes across all templates: {total_nodes}")
    print(f"  Total edges across all templates: {total_edges}")

    print("\n🎯 Testing Template Features:")

    # Test node types distribution
    node_types = {}
    for template_name, template in all_templates.items():
        for node in template.get("nodes", []):
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

    print(f"  Node types distribution: {dict(sorted(node_types.items()))}")

    # Test agent types used
    agent_types = set()
    for template_name, template in all_templates.items():
        for node in template.get("nodes", []):
            if node.get("type") == "agent" and node.get("agent_type"):
                agent_types.add(node["agent_type"])

    print(f"  Agent types used: {sorted(agent_types)}")

    print("\n" + "=" * 50)
    print("✅ Plan Templates Tests Complete!")


if __name__ == "__main__":
    test_plan_templates()