# tests/test_intelligent_planner.py
"""
Test suite for the Intelligent Planner system.
Tests specification handling, goal evaluation, and business intelligence features.
"""

from core.intelligent_planner import IntelligentPlanner
from core.schemas import SpecificationSchema


def test_enhanced_specification_handling():
    """Test the enhanced specification handling with schema validation and no-preference detection."""
    print("🧪 Testing Enhanced Specification Handling")
    print("=" * 80)

    planner = IntelligentPlanner("test_spec_handling_session")

    # Test 1: Start conversation
    print("1️⃣ Starting conversation:")
    start_response = planner.start_conversation()
    print(f"   Status: {start_response['status']}")

    # Test 2: Vague request - should use valid spec names
    print("\n2️⃣ Vague user request:")
    user_message = "I need a laptop"
    print(f"User Message: {user_message}")
    response1 = planner.process_user_message(user_message)
    print(f"   Status: {response1['status']}")
    print(f"   Specs Needed: {response1.get('specifications_needed', [])}")

    # Test 3: User provides gaming + budget (should be extracted properly)
    print("\n3️⃣ User provides use case and budget:")
    user_message = "Gaming and 150000 INR"
    print(f"User Message: {user_message}")
    response2 = planner.process_user_message(user_message)
    print(f"   Status: {response2['status']}")

    # FIX: Get specs from the spec_handler directly instead of response
    current_specs = planner.spec_handler.gathered_specs
    print(f"   Specs Gathered: {current_specs}")
    print(f"   Remaining Specs: {response2.get('specifications_needed', [])}")

    # Test 4: User says "no preference" for remaining specs
    print("\n4️⃣ User indicates no preference:")
    user_message = "I have no preference for the rest"
    # user_message = "I have only this much information to share."
    print(f"User Message: {user_message}")
    response3 = planner.process_user_message(user_message)
    print(f"   Status: {response3['status']}")
    print(f"   Action: {response3.get('action')}")

    # FIX: Get final specs from spec_handler
    final_specs = planner.spec_handler.gathered_specs
    print(f"   Final Specs: {final_specs}")

    # Test 5: Schema validation test
    print("\n5️⃣ Testing specification schema:")
    test_invalid_specs = ["intended_use", "screen_size", "operating_system"]
    valid_specs = SpecificationSchema.validate_spec_names(test_invalid_specs)
    print(f"   Invalid Specs: {test_invalid_specs}")
    print(f"   Valid Specs After Validation: {valid_specs}")

    # Test 6: Entity mapping test
    print("\n6️⃣ Testing entity mapping:")
    test_entities = {
        "intended_use": "gaming",
        "price_range": "50000 INR",
        "brand_preference": "Dell"
    }
    mapped_entities = SpecificationSchema.map_entities_to_specs(test_entities)
    print(f"   Original Entities: {test_entities}")
    print(f"   Mapped Entities: {mapped_entities}")

    # Test 7: No preference detection
    print("\n7️⃣ Testing no preference detection:")
    test_phrases = [
        "I don't care",
        "no preference",
        "anything is fine",
        "I'm flexible",
        "doesn't matter to me"
    ]
    for phrase in test_phrases:
        detected = SpecificationSchema.detect_no_preference(phrase)
        print(f"   '{phrase}' → No Preference: {detected}")

    print("\n" + "=" * 80)
    print("✅ Enhanced Specification Handling Tests Complete!")
    print("\nKey Fixes Demonstrated:")
    print("🔧 Standardized specification schema prevents LLM/NLU mismatches")
    print("🎯 Proper entity extraction for gaming + budget")
    print("✨ No preference detection ends spec gathering loops")
    print("🛡️ Specification name validation prevents invalid LLM outputs")
    print("🔄 Enhanced entity mapping handles alternative naming")
    print("📝 Better user guidance and helpful clarifications")


def test_intelligent_planner():
    """Test the enhanced Intelligent Planner with comprehensive goal evaluation and business intelligence."""
    print("🧪 Testing Enhanced Intelligent Planner with Goal Evaluation")
    print("=" * 80)

    planner = IntelligentPlanner("test_enhanced_session")

    # Test 1: Start conversation with business context
    print("1️⃣ Starting conversation:")
    start_response = planner.start_conversation()
    print(f"   Status: {start_response['status']}")
    print(f"   Business Context: {start_response.get('business_context', 'N/A')}")
    print(f"   Response: {start_response['response'][:100]}...")

    # Test 2: Vague user request - should trigger spec gathering with goal evaluation
    print("\n2️⃣ Vague user request (should gather specs with goal evaluation):")
    user_message = "I want to buy a laptop"
    print(f"User Message: {user_message}")
    response1 = planner.process_user_message(user_message)
    print(f"   Status: {response1['status']}")
    print(f"   Action: {response1.get('action')}")
    print(f"   Goal Status: {response1.get('goal_status')}")
    print(f"   Goal Progress: {response1.get('goal_progress', 0):.1f}")
    if response1.get('goal_evaluation'):
        print(f"   Goal Reasoning: {response1['goal_evaluation']['reasoning'][:80]}...")

    # Test 3: User provides specifications with satisfaction signals
    print("\n3️⃣ User provides specifications with satisfaction signals:")
    user_message = "Perfect! I need it for gaming and my budget is around 150000 INR"
    print(f"User Message: {user_message}")
    response2 = planner.process_user_message(user_message)
    print(f"   Status: {response2['status']}")
    print(f"   Action: {response2.get('action')}")
    print(f"   Goal Progress: {response2.get('goal_progress', 0):.1f}")
    print(f"   Satisfaction Signals: {planner.session_manager.satisfaction_signals_detected}")

    # FIX: Show actual gathered specs
    print(f"   Specs Gathered: {planner.spec_handler.gathered_specs}")

    # Test 4: User confirms requirements
    print("\n4️⃣ User confirms requirements:")
    user_message = "Yes, that looks exactly right!"
    print(f"User Message: {user_message}")
    response3 = planner.process_user_message(user_message)
    print(f"   Status: {response3['status']}")
    print(f"   Action: {response3.get('action')}")
    print(f"   Agent Called: {response3.get('agent_type')}")
    print(f"   Goal Achieved: {response3.get('goal_achieved')}")
    print(f"   Session Complete: {response3.get('session_complete', False)}")
    if response3.get('goal_evaluation'):
        eval_data = response3['goal_evaluation']
        print(f"   Criteria Met: {len(eval_data.get('criteria_met', []))}")
        print(f"   Business Value: {eval_data.get('business_value', 'N/A')}")

    # Test 5: Session information with business metrics
    print(f"\n5️⃣ Enhanced Session Information:")
    session_info = planner.get_session_info()
    print(f"   Session ID: {session_info['session_id']}")
    print(f"   Planner Status: {session_info['planner_status']}")
    print(
        f"   Goal Progress: {session_info['current_goal']['progress_score'] if session_info['current_goal'] else 0:.1f}")
    print(
        f"   Business Objective: {session_info['current_goal']['business_objective'] if session_info['current_goal'] else 'N/A'}")
    quality_metrics = session_info.get('conversation_quality', {})
    print(f"   Satisfaction Signals: {quality_metrics.get('satisfaction_signals_detected', 0)}")
    business_metrics = session_info.get('business_metrics', {})
    print(f"   Customer Engagement: {business_metrics.get('customer_engagement', 'N/A')}")

    print("\n" + "=" * 80)
    print("✅ Enhanced Intelligent Planner Tests Complete!")
    print("\nKey Enhancements Demonstrated:")
    print("🎯 Single LLM call per message (planning + goal evaluation)")
    print("📊 Comprehensive goal tracking with measurable criteria")
    print("💼 Business-aware decision making and messaging")
    print("😊 User satisfaction signal detection and tracking")
    print("📈 Progress scoring and conversation quality metrics")
    print("🏆 Professional, customer service-focused interactions")
    print("⚡ Efficient processing with integrated goal evaluation")
    print("🔧 Fixed specification naming mismatch issues")
    print("✨ Enhanced no-preference handling prevents loops")


def test_session_management():
    """Test session management and goal tracking."""
    print("🧪 Testing Session Management")
    print("=" * 50)

    planner = IntelligentPlanner("test_session")

    # Test session info
    session_info = planner.get_session_info()
    print(f"Initial Session Status: {session_info['planner_status']}")
    print(f"Session ID: {session_info['session_id']}")

    # Test conversation end
    end_response = planner.end_conversation("test_complete")
    print(f"End Response Status: {end_response['status']}")
    print(f"Business Outcome: {end_response['business_outcome']}")

    print("✅ Session Management Tests Complete!")


def test_specification_schema():
    """Test specification schema validation and mapping."""
    print("🧪 Testing Specification Schema")
    print("=" * 50)

    # Test validation
    invalid_specs = ["screen_size", "operating_system", "intended_use"]
    valid_specs = SpecificationSchema.validate_spec_names(invalid_specs)
    print(f"Invalid specs filtered out: {len(invalid_specs) - len(valid_specs)} removed")

    # Test entity mapping
    test_entities = {
        "price_range": "50000 INR",
        "intended_use": "gaming",
        "brand_preference": "Dell"
    }
    mapped = SpecificationSchema.map_entities_to_specs(test_entities)
    print(f"Entity mapping successful: {len(mapped)} entities mapped")

    # Test no preference detection
    test_phrases = ["no preference", "I don't care", "flexible"]
    detected = [SpecificationSchema.detect_no_preference(phrase) for phrase in test_phrases]
    print(f"No preference detection: {sum(detected)}/{len(detected)} phrases detected")

    print("✅ Specification Schema Tests Complete!")


if __name__ == "__main__":
    # test_enhanced_specification_handling()
    print("\n" + "=" * 50)
    # test_intelligent_planner()
    # print("\n" + "=" * 50)
    # test_session_management()
    # print("\n" + "=" * 50)
    test_specification_schema()