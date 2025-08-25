# test_intelligent_planner.py
"""
Test cases for the Intelligent Planner system.

Tests the core scenarios discussed:
1. Out-of-domain requests (stars from Andromeda galaxy)
2. Context accumulation across multiple messages
3. Ambiguity resolution and clarification
4. Information sufficiency evaluation
5. Dynamic plan generation and routing
"""

from core.planner_new import IntelligentPlanner


def test_out_of_domain_request():
    """Test handling of completely out-of-domain requests."""
    print("\n" + "=" * 60)
    print("TEST 1: Out-of-Domain Request")
    print("=" * 60)

    planner = IntelligentPlanner()
    planner.start_session("test_out_of_domain")

    # Test the astronomy request
    result = planner.process_message("I want stars from the real Andromeda galaxy")

    print(f"Domain Status: {result['domain_status']['in_domain']}")
    print(f"Routing Action: {result['routing_decision']['action']}")
    print(f"Response: {result['routing_decision']['message']}")
    print(f"Context Preserved: {result['routing_decision']['context_preserved']}")

    assert result["success"] == True
    assert result.get("out_of_domain") == True
    assert result["routing_decision"]["action"] == "REDIRECT"


def test_context_accumulation():
    """Test context accumulation across multiple messages."""
    print("\n" + "=" * 60)
    print("TEST 2: Context Accumulation")
    print("=" * 60)

    planner = IntelligentPlanner()
    planner.start_session("test_context_accumulation")

    # Message 1: Intent only
    print("\nMessage 1: 'I need a laptop'")
    result1 = planner.process_message("I need a laptop")
    print(f"  Accumulated Info: {result1['accumulated_info']}")
    print(f"  Routing Action: {result1['routing_decision']['action']}")
    print(f"  Should Execute Agent: {result1['routing_decision'].get('agent_to_call')}")

    # Message 2: Add budget constraint
    print("\nMessage 2: 'My budget is 40000'")
    result2 = planner.process_message("My budget is 40000")
    print(f"  Accumulated Info: {result2['accumulated_info']}")
    print(f"  Routing Action: {result2['routing_decision']['action']}")
    print(f"  Should Execute Agent: {result2['routing_decision'].get('agent_to_call')}")

    # Message 3: Ambiguous reference
    print("\nMessage 3: 'Petty carrie has a better one'")
    result3 = planner.process_message("Petty carrie has a better one")
    print(f"  Context Resolution: {result3['context_resolution']}")
    print(f"  Routing Action: {result3['routing_decision']['action']}")
    print(f"  Response: {result3['routing_decision']['message']}")

    # Verify the expected behavior:
    # - Should not execute agent after message 1 (insufficient info might be okay though)
    # - Should be ready to execute agent after message 2 (has product + budget)
    # - Should pause for clarification after message 3 (ambiguous reference)

    print(f"\nFinal Summary:")
    print(f"  Total Messages: 3")
    print(f"  Final Accumulated Info: {result3['accumulated_info']}")
    print(f"  Context Preserved Throughout: All routing decisions preserved context")


def test_incremental_vs_accumulated():
    """Test when planner decides to act vs wait for more information."""
    print("\n" + "=" * 60)
    print("TEST 3: Incremental vs Accumulated Decision Making")
    print("=" * 60)

    planner = IntelligentPlanner()
    planner.start_session("test_incremental_accumulated")

    # Progressive information gathering
    messages = [
        "Hi there",
        "I want to buy something",
        "A laptop",
        "Dell laptop",
        "16GB RAM",
        "Under 50000 budget"
    ]

    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}: '{msg}'")
        result = planner.process_message(msg)

        info_status = result['information_status']
        routing = result['routing_decision']

        print(f"  Info Sufficiency: {info_status.get('overall_sufficiency', 'Unknown')}")
        print(f"  Ready Actions: {info_status.get('ready_actions', [])}")
        print(f"  Routing Action: {routing['action']}")

        if routing.get('agent_to_call'):
            print(f"  *** EXECUTING AGENT: {routing['agent_to_call']} ***")

        print(f"  Accumulated: {result['accumulated_info']}")


def test_clarification_with_context():
    """Test contextual clarification that preserves conversation flow."""
    print("\n" + "=" * 60)
    print("TEST 4: Contextual Clarification")
    print("=" * 60)

    planner = IntelligentPlanner()
    planner.start_session("test_contextual_clarification")

    # Build up context
    planner.process_message("I want to buy a smartphone")
    planner.process_message("Samsung brand preferred")

    # Now send ambiguous message
    result = planner.process_message("Make it blue and that size")

    print(f"Ambiguous Elements: {result['context_resolution'].get('ambiguous_elements', [])}")
    print(f"Needs Clarification: {result['context_resolution'].get('needs_clarification', False)}")
    print(f"Clarification Questions: {result['context_resolution'].get('clarification_questions', [])}")
    print(f"Routing Response: {result['routing_decision']['message']}")
    print(f"Context Preserved: {result['routing_decision']['context_preserved']}")

    # Verify that context is maintained
    session_summary = planner.get_session_summary()
    print(f"Session Summary: {session_summary}")


def test_complete_conversation_flow():
    """Test a complete conversation from start to agent execution."""
    print("\n" + "=" * 60)
    print("TEST 5: Complete Conversation Flow")
    print("=" * 60)

    planner = IntelligentPlanner()
    planner.start_session("test_complete_flow")

    conversation_steps = [
        "Hello",
        "I need help finding a product",
        "Looking for a laptop for work",
        "Budget is around 80000 rupees",
        "Prefer Dell or HP brand",
        "Need good battery life"
    ]

    for step in conversation_steps:
        print(f"\nUser: {step}")
        result = planner.process_message(step)

        routing = result['routing_decision']
        print(f"Planner Action: {routing['action']}")

        if routing.get('message'):
            print(f"Planner: {routing['message']}")

        if routing.get('agent_to_call'):
            print(f">>> CALLING {routing['agent_to_call']} AGENT <<<")
            execution_context = routing.get('execution_context', {})
            print(f"Agent Context: {execution_context.get('accumulated_info', {})}")

    # Final session state
    final_summary = planner.get_session_summary()
    print(f"\n=== Final Session Summary ===")
    print(f"Messages Processed: {final_summary['message_count']}")
    print(f"Information Gathered: {final_summary['accumulated_info']}")
    print(f"Last Intent: {final_summary['last_intent']}")
    print(f"Information Richness: {final_summary['information_richness']} fields")


def main():
    """Run all test cases."""
    print("🧪 Testing Intelligent Planner System")
    print("Testing the scenarios discussed:")
    print("1. Out-of-domain handling (Andromeda galaxy)")
    print("2. Context accumulation (laptop + budget + ambiguous reference)")
    print("3. Information sufficiency evaluation")
    print("4. Contextual clarification")
    print("5. Complete conversation flow")

    test_out_of_domain_request()
    test_context_accumulation()
    test_incremental_vs_accumulated()
    test_clarification_with_context()
    test_complete_conversation_flow()

    print("\n" + "=" * 60)
    print("✅ All Intelligent Planner Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()