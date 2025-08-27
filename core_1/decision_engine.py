# core_1/decision_engine.py
"""
Core decision engine for LLM-driven planning and goal evaluation.
Handles comprehensive planning decisions with integrated goal assessment.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from .models import PlannerDecision, ConversationGoal
from .schemas import SpecificationSchema


class DecisionEngine:
    """Handles LLM-driven decision making with comprehensive planning and goal evaluation."""

    def __init__(self, llm_client, context_manager, intent_tracker):
        self.llm_client = llm_client
        self.context_manager = context_manager
        self.intent_tracker = intent_tracker
        self.satisfaction_signals_detected = 0
        self.success_indicators_count = 0
        self.agent_calls_count = 0
        self.conversation_turns = 0

    def make_comprehensive_planning_decision(self, user_message: str, nlu_result: Dict[str, Any],
                                           intent_result: Dict[str, Any], current_goal: Optional[ConversationGoal]) -> PlannerDecision:
        """
        Use single LLM call to make intelligent planning decisions AND evaluate goal achievement.
        This is the core_1 method that combines planning and goal evaluation for efficiency.
        """
        # Create comprehensive prompt that handles both planning and goal evaluation
        prompt = self._create_comprehensive_planning_prompt(user_message, nlu_result, intent_result, current_goal)

        try:
            # Single LLM call for both planning decision and goal evaluation
            llm_response = self.llm_client.generate(prompt)

            # Parse comprehensive LLM response into structured decision with goal evaluation
            decision = self._parse_comprehensive_planner_response(llm_response)

            # Validate and fix specification names to prevent mismatches
            decision = self._validate_and_fix_decision_specs(decision)

            # Update satisfaction tracking based on LLM evaluation
            if decision.satisfaction_indicators_present:
                self.satisfaction_signals_detected += len(decision.satisfaction_indicators_present)
                self.success_indicators_count += len(decision.success_criteria_met)

            return decision

        except Exception as e:
            # Fallback decision making with basic goal evaluation
            return self._create_fallback_decision(user_message, nlu_result, str(e))

    def _create_comprehensive_planning_prompt(self, user_message: str, nlu_result: Dict[str, Any],
                                            intent_result: Dict[str, Any], current_goal: Optional[ConversationGoal]) -> str:
        """Create comprehensive LLM prompt that handles both planning decisions AND goal evaluation with specification schema."""

        # Get current context
        context_summary = self.context_manager.get_context_summary()
        recent_messages = self.context_manager.get_recent_messages(6)
        current_intent = self.intent_tracker.get_current_intent()

        # Format conversation history
        conversation_context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in recent_messages[-4:]
        ]) if recent_messages else "No previous conversation"

        # Current goal information with success criteria
        goal_info = "No goal set yet"
        goal_evaluation_context = ""
        if current_goal:
            goal_info = f"""Current Goal: {current_goal.description}
Category: {current_goal.category}
Status: {current_goal.status}
Progress Score: {current_goal.progress_score:.1f}/1.0
Business Objective: {current_goal.business_objective}

Success Criteria to Evaluate:
{chr(10).join(f"- {criteria}" for criteria in current_goal.success_criteria)}

User Satisfaction Indicators to Look For:
{chr(10).join(f"- {indicator}" for indicator in current_goal.user_satisfaction_indicators)}"""

            goal_evaluation_context = f"""
GOAL EVALUATION REQUIRED:
Evaluate if the current goal is progressing or achieved based on:
1. Success criteria completion
2. User satisfaction indicators detected
3. Business objective fulfillment
4. Overall conversation quality
"""

        # Current facts available
        facts_info = []
        facts = context_summary.get('facts_by_source', {})
        for source, source_facts in facts.items():
            for key, value in source_facts.items():
                facts_info.append(f"{key}: {value}")

        facts_str = ", ".join(facts_info) if facts_info else "No facts gathered yet"

        # Create specification schema documentation for LLM
        spec_schema_info = f"""
SPECIFICATION SCHEMA (CRITICAL - USE EXACTLY THESE NAMES):
You MUST use only these exact specification names in specifications_needed:
{chr(10).join(f'- "{spec}": {desc}' for spec, desc in SpecificationSchema.ALLOWED_SPECS.items())}

NEVER invent new specification names like "intended_use", "screen_size", "operating_system".
ONLY use the exact names listed above: {', '.join(SpecificationSchema.ALLOWED_SPECS.keys())}

Example correct usage: ["category", "subcategory", "use_case", "budget"]
Example incorrect usage: ["intended_use", "screen_size", "operating_system"] ❌
"""

        # Business context and system purpose
        business_context = """
SYSTEM PURPOSE & BUSINESS CONTEXT:
You are an intelligent e-commerce assistant focused on delivering exceptional customer service.
Your primary objectives are:
1. Help customers accomplish their goals efficiently and satisfactorily
2. Provide accurate, helpful information that builds trust
3. Guide conversations toward successful outcomes (purchases, problem resolution, satisfaction)
4. Maintain high conversation quality and user experience
5. Balance customer needs with business objectives (sales, support, retention)

CONVERSATION QUALITY STANDARDS:
- Be methodical in gathering requirements before taking action
- Confirm understanding before proceeding with important steps  
- Provide clear, actionable information
- Detect and respond to user satisfaction signals
- End conversations naturally when goals are achieved
- Always prioritize user satisfaction and successful task completion
"""

        prompt = f"""{business_context}

{spec_schema_info}

CURRENT SITUATION:
User Message: "{user_message}"
Intent Detected: {nlu_result.get('intent', 'Unknown')}
Entities: {nlu_result.get('entities', {})}
Confidence: {nlu_result.get('confidence', 0.5)}

CONVERSATION CONTEXT:
{conversation_context}

CURRENT STATE:
{goal_info}
Available Facts: {facts_str}
Agent Calls Made: {self.agent_calls_count}
Conversation Turns: {self.conversation_turns}
Satisfaction Signals Detected: {self.satisfaction_signals_detected}

{goal_evaluation_context}

AVAILABLE AGENTS:
- DiscoveryAgent: Dual-mode product discovery (search + recommendations)
- OrderAgent: Track orders, check status, handle order queries  
- ReturnAgent: Process returns, exchanges, refunds

DECISION FRAMEWORK:
For Discovery requests (buying, browsing, recommendations):
1. Check if we have REQUIRED info: category + subcategory
2. If missing required info → gather_specs (using ONLY allowed spec names)
3. If have required info but missing important details (budget, use_case) → gather_specs  
4. If have good info but not confirmed → confirm_requirements
5. If confirmed → call_agent (DiscoveryAgent)

For Order/Return requests:
1. If user has order_id → call_agent directly
2. If no order_id → call_agent (agent will show options)

For Goal Achievement Assessment:
- Check if success criteria are met
- Look for user satisfaction indicators in their language
- Evaluate if business objective is being fulfilled
- Consider conversation quality and user experience
- Determine if user seems ready to conclude

DECISION TYPES:
- gather_specs: Need to collect more specifications from user
- confirm_requirements: Have info, need user confirmation before proceeding
- call_agent: Ready to call agent with collected information
- goal_achieved: User's objective is complete and they're satisfied
- re_plan: User changed direction, need new approach  
- clarify: Need clarification from user

GOAL STATUS TYPES:
- in_progress: Goal is being worked on, user engaged
- achieved: All success criteria met, user satisfied
- needs_replanning: User changed direction or requirements
- blocked: Cannot proceed without additional information

Return JSON with both planning decision AND goal evaluation:
{{
  "action": "gather_specs|confirm_requirements|call_agent|goal_achieved|re_plan|clarify",
  "agent_type": "DiscoveryAgent|OrderAgent|ReturnAgent|null",
  "agent_params": {{"category": "...", "subcategory": "...", "specifications": {{}}}},
  "reasoning": "why_this_decision_makes_sense",
  "user_message": "what_to_tell_the_user_or_null",
  "confidence": 0.0-1.0,
  "specifications_needed": ["only_allowed_spec_names_from_schema"],
  "confirmation_summary": "summary_of_requirements_for_confirmation",

  "goal_status": "in_progress|achieved|needs_replanning|blocked",
  "goal_progress_score": 0.0-1.0,
  "goal_achievement_reasoning": "detailed_explanation_of_goal_evaluation",
  "success_criteria_met": ["list_of_criteria_that_are_satisfied"],
  "satisfaction_indicators_present": ["detected_user_satisfaction_signals"],
  "next_steps_recommendation": "what_should_happen_next_or_null",

  "goal_description": "natural_language_goal_description_if_new_or_updated",
  "goal_category": "discovery|order|return|general",
  "should_update_goal": true/false
}}

CRITICAL: Only use specification names from the allowed schema. Be thorough in both planning decisions and goal evaluation. Focus on user satisfaction and successful outcomes.
"""
        return prompt

    def _parse_comprehensive_planner_response(self, llm_response: str) -> PlannerDecision:
        """Parse comprehensive LLM response into structured PlannerDecision with goal evaluation."""

        if llm_response.startswith("[LLM-FALLBACK]"):
            return self._create_fallback_decision("", {}, "LLM fallback mode")

        try:
            # Clean and parse JSON response
            response = llm_response.strip()
            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]

            response = response.strip()
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = response[json_start:json_end]
            parsed = json.loads(json_str)

            # Create comprehensive PlannerDecision with goal evaluation
            decision = PlannerDecision(
                # Planning decision fields
                action=parsed.get("action", "clarify"),
                agent_type=parsed.get("agent_type"),
                agent_params=parsed.get("agent_params", {}),
                reasoning=parsed.get("reasoning", "LLM planning decision"),
                user_message=parsed.get("user_message"),
                confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.8)))),
                specifications_needed=parsed.get("specifications_needed", []),
                confirmation_summary=parsed.get("confirmation_summary"),

                # Goal evaluation fields (new)
                goal_status=parsed.get("goal_status", "in_progress"),
                goal_progress_score=max(0.0, min(1.0, float(parsed.get("goal_progress_score", 0.0)))),
                goal_achievement_reasoning=parsed.get("goal_achievement_reasoning", "Goal evaluation completed"),
                success_criteria_met=parsed.get("success_criteria_met", []),
                satisfaction_indicators_present=parsed.get("satisfaction_indicators_present", []),
                next_steps_recommendation=parsed.get("next_steps_recommendation"),

                # Goal management fields
                goal_description=parsed.get("goal_description"),
                goal_category=parsed.get("goal_category"),
                should_update_goal=parsed.get("should_update_goal", False)
            )

            return decision

        except (json.JSONDecodeError, ValueError) as e:
            return self._create_fallback_decision("", {}, f"Parse error: {str(e)}")

    def _validate_and_fix_decision_specs(self, decision: PlannerDecision) -> PlannerDecision:
        """Validate and fix specification names in LLM decision to prevent naming mismatches."""

        if decision.specifications_needed:
            # Validate specification names using schema
            valid_specs = SpecificationSchema.validate_spec_names(decision.specifications_needed)

            if len(valid_specs) != len(decision.specifications_needed):
                # LLM used invalid spec names - fix them
                original_count = len(decision.specifications_needed)
                decision.specifications_needed = valid_specs

                # Add fallback specs if we lost too many
                if len(valid_specs) == 0 and original_count > 0:
                    # LLM used all invalid names - provide sensible defaults
                    decision.specifications_needed = ["category", "subcategory", "use_case"]
                    print(f"⚠️ Warning: LLM used invalid spec names, using default specs")

        return decision

    def _create_fallback_decision(self, user_message: str, nlu_result: Dict[str, Any],
                                error_msg: str) -> PlannerDecision:
        """Create fallback decision when LLM fails with basic goal evaluation and valid spec names."""

        # Simple pattern-based fallback with goal awareness
        message_lower = user_message.lower() if user_message else ""

        if any(word in message_lower for word in ["buy", "purchase", "want", "need", "laptop", "phone"]):
            return PlannerDecision(
                action="gather_specs",
                specifications_needed=["category", "subcategory", "use_case", "budget"],  # Use valid spec names
                reasoning=f"Fallback: Detected product interest. {error_msg}",
                user_message="I'd like to help you find the perfect product. What type of product are you looking for?",
                goal_status="in_progress",
                goal_progress_score=0.2,
                goal_achievement_reasoning="Fallback mode: Basic product interest detected",
                should_update_goal=True,
                goal_description="Help user find and purchase suitable products",
                goal_category="discovery"
            )
        elif any(word in message_lower for word in ["order", "track", "delivery"]):
            return PlannerDecision(
                action="call_agent",
                agent_type="OrderAgent",
                agent_params={"action": "track"},
                reasoning=f"Fallback: Detected order inquiry. {error_msg}",
                goal_status="in_progress",
                goal_progress_score=0.7,
                goal_achievement_reasoning="Fallback mode: Order tracking request detected",
                should_update_goal=True,
                goal_description="Help user track order status",
                goal_category="order"
            )
        else:
            return PlannerDecision(
                action="clarify",
                reasoning=f"Fallback: Unclear intent. {error_msg}",
                user_message="I'd like to help you, but I need more information about what you're looking for.",
                goal_status="in_progress",
                goal_progress_score=0.1,
                goal_achievement_reasoning="Fallback mode: Need clarification to establish goal"
            )

    def evaluate_post_agent_goal_status(self, agent_result: Dict[str, Any], decision: PlannerDecision,
                                        current_goal: Optional[ConversationGoal]) -> Dict[str, Any]:
        """Evaluate goal achievement after agent execution based on results and context."""

        if not current_goal:
            return {
                "achieved": False,
                "status": "no_goal",
                "progress_score": 0.0,
                "reasoning": "No goal defined",
                "criteria_met": [],
                "satisfaction_signals": [],
                "business_value": "none"
            }

        # Start with previous progress score, never go backwards
        progress_score = max(decision.goal_progress_score or 0.0, current_goal.progress_score)
        achieved = False
        criteria_met = []
        satisfaction_signals = []
        business_value = "moderate"

        if current_goal.category == "discovery":
            # Discovery goal evaluation - check agent results
            products_found = agent_result.get("products_found", 0)
            if products_found > 0:
                criteria_met.append("User receives relevant product recommendations")
                progress_score = max(progress_score, 0.9)
                business_value = "high"

                if products_found >= 3:
                    criteria_met.append("Products match user's specified requirements")
                    criteria_met.append("Budget and preferences are respected")
                    achieved = True
                    progress_score = 1.0
                    business_value = "high"

            # Even if no products found, agent was called successfully
            elif agent_result.get("status") == "success":
                criteria_met.append("Search was executed based on user requirements")
                progress_score = max(progress_score, 0.85)

        elif current_goal.category == "order":
            # Order tracking goal evaluation
            if agent_result.get("order_found"):
                criteria_met.append("Order status information is provided")
                criteria_met.append("User receives clear tracking information")
                achieved = True
                progress_score = 1.0
                business_value = "high"

        elif current_goal.category == "return":
            # Return processing goal evaluation
            if agent_result.get("return_process_initiated"):
                criteria_met.append("Return process is clearly explained")
                if agent_result.get("return_authorization"):
                    criteria_met.append("User receives return authorization if needed")
                achieved = True
                progress_score = 1.0
                business_value = "high"

        # Check for satisfaction signals based on conversation quality
        if self.satisfaction_signals_detected > 0:
            satisfaction_signals.append("User expressed satisfaction during conversation")
        if achieved:
            satisfaction_signals.append("Successful task completion indicates satisfaction")

        return {
            "achieved": achieved,
            "status": "achieved" if achieved else "in_progress",
            "progress_score": progress_score,  # Never goes backwards
            "reasoning": f"Agent {decision.agent_type} executed. Products found: {agent_result.get('products_found', 0)}. Criteria met: {len(criteria_met)}/{len(current_goal.success_criteria)}",
            "criteria_met": criteria_met,
            "satisfaction_signals": satisfaction_signals,
            "business_value": business_value
        }
