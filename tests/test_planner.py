# tests/test_planner.py
"""
Test cases for the graph-based planner system.
"""

import pytest
from core.planner import Planner
from core.world_state import WorldState
from core.schema import make_result


class TestPlanner:
    """Test cases for the Planner class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.planner = Planner()

    def test_graph_structure(self):
        """Test that the conversation graph is built correctly."""
        graph_info = self.planner.get_graph_info()

        assert graph_info["total_nodes"] == 7  # NLU, RECOMMEND, BUY, ORDER, RETURN, CLARIFY, DONE
        assert graph_info["total_edges"] > 0

        # Check that all expected nodes exist
        node_names = [node[0] for node in graph_info["nodes"]]
        expected_nodes = ["NLU", "RECOMMEND", "BUY", "ORDER", "RETURN", "CLARIFY", "DONE"]
        for node in expected_nodes:
            assert node in node_names

    def test_nlu_routing_buy_intent(self):
        """Test routing from NLU with buy intent."""
        world_state = WorldState({
            "intent": "BUY",
            "confidence": 0.9,
            "entities": {"product": "laptop"}
        })

        next_node = self.planner.route_from_nlu(world_state)
        assert next_node == "BUY"

    def test_nlu_routing_unclear_intent(self):
        """Test routing from NLU with unclear intent."""
        world_state = WorldState({
            "intent": "UNCLEAR",
            "confidence": 0.3,
            "entities": {}
        })

        next_node = self.planner.route_from_nlu(world_state)
        assert next_node == "CLARIFY"

    def test_condition_evaluation(self):
        """Test transition condition evaluation."""
        world_state = WorldState({
            "intent": "BUY",
            "confidence": 0.9
        })

        last_result = make_result("BuyAgent", "SUCCESS",
                                  proposed_next=["ORDER"],
                                  changes={"purchase_started": True})

        # Test intent-based condition
        assert self.planner.evaluate_transition_condition(
            "intent_buy", last_result, world_state) == True

        # Test result-based condition
        assert self.planner.evaluate_transition_condition(
            "purchase_initiated", last_result, world_state) == True

    def test_step_execution_nlu(self):
        """Test executing the NLU step."""
        world_state = WorldState({
            "intent": "BUY",
            "confidence": 0.8
        })

        result = self.planner.step("NLU", world_state)

        assert result["status"] == "SUCCESS"
        assert "BUY" in result["proposed_next"]

    def test_step_execution_terminal(self):
        """Test executing the DONE step."""
        world_state = WorldState()

        result = self.planner.step("DONE", world_state)

        assert result["status"] == "SUCCESS"
        assert result["proposed_next"] == ["DONE"]

    def test_next_node_selection(self):
        """Test next node selection logic."""
        world_state = WorldState({
            "intent": "BUY",
            "confidence": 0.9
        })

        last_result = make_result("BuyAgent", "SUCCESS",
                                  proposed_next=["ORDER"])

        next_node = self.planner.next_node("BUY", last_result, world_state)
        assert next_node == "ORDER"

    def test_complete_plan_execution(self):
        """Test complete plan execution from start to finish."""
        user_message = "I want to buy a laptop under $1000"

        result = self.planner.run_plan(user_message)

        assert result["success"] == True
        assert len(result["steps"]) > 0
        assert "final_state" in result
        assert "goal" in result

        # Check that we started with NLU
        first_step = result["steps"][0]
        assert first_step["node"] == "NLU"

    def test_safety_counter(self):
        """Test that safety counter prevents infinite loops."""
        # This would require mocking agents to create a loop
        # For now, just verify the mechanism exists
        user_message = "test message"
        result = self.planner.run_plan(user_message)

        # Should not exceed maximum steps
        assert result["total_steps"] <= 13  # 12 max steps + terminal


def test_buy_flow():
    """Test a typical buy conversation flow."""
    planner = Planner()

    test_cases = [
        "I want to buy a laptop",
        "I need a Dell laptop with 16GB RAM",
        "Show me phones under $500"
    ]

    for message in test_cases:
        result = planner.run_plan(message)

        print(f"\n--- Test: {message} ---")
        print(f"Success: {result['success']}")
        print(f"Goal: {result['goal']}")
        print(f"Steps: {len(result['steps'])}")

        for step in result["steps"]:
            node = step["node"]
            status = step["result"]["status"]
            print(f"  {node}: {status}")


def test_order_flow():
    """Test order tracking flow."""
    planner = Planner()

    test_cases = [
        "Track my order #12345",
        "What's the status of order ORD-789"
    ]

    for message in test_cases:
        result = planner.run_plan(message)

        print(f"\n--- Test: {message} ---")
        print(f"Success: {result['success']}")
        print(f"Goal: {result['goal']}")


if __name__ == "__main__":
    print("🧪 Testing Graph-based Planner")
    print("=" * 50)

    test_buy_flow()
    test_order_flow()

    print("\n✅ Planner tests complete!")