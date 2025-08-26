# core/intelligent_planner.py
"""
Intelligent Planner - LLM-Driven Goal-Oriented Conversational AI with Discovery Agent

Purpose: Dynamic conversational orchestrator that uses LLM intelligence to:
- Gather required specifications through intelligent questioning
- Confirm requirements before agent calls
- Use Discovery Agent for dual-mode product discovery
- Continuously validate goal achievement with re-planning support
- Provide truly adaptive conversation management

Key Features:
- Specification gathering with confirmation gates
- Dual-mode Discovery Agent integration
- Goal-oriented validation with single LLM call per message
- Dynamic re-planning with user explanation
- Intelligent conversation state management
- Business-aware decision making with clear success criteria
- Standardized specification schema to prevent naming mismatches
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime
from core.enhanced_nlu import EnhancedNLU
from core.intent_tracker import IntentTracker
from core.context_manager import ContextManager
from core.llm_client import LLMClient
from core.mock_agents import MockAgentManager


class PlannerStatus(Enum):
    """Status of the intelligent planner."""
    READY = "ready"
    ANALYZING = "analyzing"
    GATHERING_SPECS = "gathering_specifications"
    CONFIRMING_REQUIREMENTS = "confirming_requirements"
    EXECUTING_AGENT = "executing_agent"
    GOAL_ACHIEVED = "goal_achieved"
    RE_PLANNING = "re_planning"
    ERROR = "error"


class SpecificationSchema:
    """Standardized specification schema to prevent LLM/NLU naming mismatches."""

    # Allowed specification names (LLM must use exactly these)
    ALLOWED_SPECS = {
        "category": "Product category (electronics, clothing, etc.)",
        "subcategory": "Specific product type (laptop, smartphone, etc.)",
        "use_case": "What user will use the product for",
        "budget": "Price range or maximum budget",
        "brand": "Brand preference or requirements",
        "specifications": "Technical requirements or features"
    }

    # Entity mapping: NLU entities → Standard spec names
    ENTITY_MAPPING = {
        # Direct mappings
        "category": "category",
        "subcategory": "subcategory",
        "use_case": "use_case",
        "budget": "budget",
        "brand": "brand",
        "specifications": "specifications",

        # Alternative entity names that NLU might use
        "product_category": "category",
        "product_type": "subcategory",
        "intended_use": "use_case",
        "purpose": "use_case",
        "price_range": "budget",
        "max_budget": "budget",
        "brand_preference": "brand",
        "features": "specifications",
        "requirements": "specifications",
        "tech_specs": "specifications"
    }

    # "No preference" keywords that satisfy any specification
    NO_PREFERENCE_KEYWORDS = {
        "no preference", "no preferences", "don't care", "doesn't matter",
        "anything", "any", "flexible", "open", "not important",
        "whatever", "not picky", "no specific", "no particular"
    }

    @classmethod
    def validate_spec_names(cls, spec_list: List[str]) -> List[str]:
        """Validate and filter specification names to only allowed ones."""
        if not spec_list:
            return []

        valid_specs = []
        for spec in spec_list:
            if spec in cls.ALLOWED_SPECS:
                valid_specs.append(spec)
            else:
                # Log warning but don't break - use fallback
                print(f"⚠️ Warning: LLM requested invalid spec '{spec}', skipping")

        return valid_specs

    @classmethod
    def map_entities_to_specs(cls, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Map NLU entities to standardized specification names."""
        mapped_specs = {}

        for entity_name, entity_value in entities.items():
            if entity_value:  # Only map non-empty values
                # Find the standard spec name for this entity
                standard_name = cls.ENTITY_MAPPING.get(entity_name, entity_name)
                if standard_name in cls.ALLOWED_SPECS:
                    mapped_specs[standard_name] = entity_value

        return mapped_specs

    @classmethod
    def detect_no_preference(cls, user_message: str) -> bool:
        """Detect if user is indicating no preference."""
        message_lower = user_message.lower().strip()
        return any(keyword in message_lower for keyword in cls.NO_PREFERENCE_KEYWORDS)

    @classmethod
    def get_spec_description(cls, spec_name: str) -> str:
        """Get human-readable description for a specification."""
        return cls.ALLOWED_SPECS.get(spec_name, spec_name.replace('_', ' ').title())


@dataclass
class ConversationGoal:
    """Represents the current conversation goal with measurable success criteria."""
    description: str
    category: str  # "discovery", "order", "return", "general"
    success_criteria: List[str] = field(default_factory=list)  # Specific measurable criteria
    business_objective: str = ""  # What business value this achieves
    user_satisfaction_indicators: List[str] = field(default_factory=list)  # Signs of user satisfaction
    created_at: str = ""
    updated_at: str = ""
    status: str = "active"
    progress_score: float = 0.0  # 0.0 to 1.0 indicating progress toward completion

    def __post_init__(self):
        """Initialize timestamps and default criteria based on category."""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

        # Set default success criteria based on category
        if not self.success_criteria:
            self.success_criteria = self._get_default_success_criteria()
        if not self.business_objective:
            self.business_objective = self._get_default_business_objective()
        if not self.user_satisfaction_indicators:
            self.user_satisfaction_indicators = self._get_default_satisfaction_indicators()

    def _get_default_success_criteria(self) -> List[str]:
        """Get default success criteria based on goal category."""
        criteria_map = {
            "discovery": [
                "User receives relevant product recommendations",
                "Products match user's specified requirements",
                "User expresses satisfaction with options presented",
                "Budget and preferences are respected"
            ],
            "order": [
                "Order status information is provided",
                "User receives clear tracking information",
                "Any order issues are identified and addressed",
                "User understands next steps"
            ],
            "return": [
                "Return process is clearly explained",
                "User receives return authorization if needed",
                "Return timeline and method are communicated",
                "User confirms understanding of process"
            ],
            "general": [
                "User's question is answered accurately",
                "User receives helpful information",
                "User expresses satisfaction or understanding"
            ]
        }
        return criteria_map.get(self.category, criteria_map["general"])

    def _get_default_business_objective(self) -> str:
        """Get default business objective based on goal category."""
        objective_map = {
            "discovery": "Help customer find and purchase suitable products",
            "order": "Provide excellent post-purchase customer service",
            "return": "Handle returns efficiently while maintaining customer satisfaction",
            "general": "Provide helpful customer support and build brand loyalty"
        }
        return objective_map.get(self.category, objective_map["general"])

    def _get_default_satisfaction_indicators(self) -> List[str]:
        """Get default user satisfaction indicators based on goal category."""
        indicators_map = {
            "discovery": [
                "User shows interest in recommended products",
                "User asks follow-up questions about products",
                "User expresses thanks or satisfaction",
                "User indicates readiness to purchase"
            ],
            "order": [
                "User expresses understanding of order status",
                "User thanks for the information",
                "User indicates their concern is resolved"
            ],
            "return": [
                "User understands the return process",
                "User expresses satisfaction with the solution",
                "User confirms they have what they need"
            ],
            "general": [
                "User thanks for the help",
                "User indicates their question is answered",
                "User expresses satisfaction"
            ]
        }
        return indicators_map.get(self.category, indicators_map["general"])


@dataclass
class PlannerDecision:
    """Represents a comprehensive decision made by the planner LLM including goal evaluation."""
    # Core action decision
    action: str  # "gather_specs", "confirm_requirements", "call_agent", "goal_achieved", "re_plan", "clarify"
    agent_type: Optional[str] = None
    agent_params: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    user_message: Optional[str] = None
    confidence: float = 0.8
    specifications_needed: List[str] = None
    confirmation_summary: Optional[str] = None

    # Goal evaluation (combined in single LLM call)
    goal_status: str = "in_progress"  # "in_progress", "achieved", "needs_replanning", "blocked"
    goal_progress_score: float = 0.0  # 0.0 to 1.0
    goal_achievement_reasoning: str = ""
    success_criteria_met: List[str] = field(default_factory=list)  # Which criteria are satisfied
    satisfaction_indicators_present: List[str] = field(default_factory=list)  # Detected satisfaction signs
    next_steps_recommendation: Optional[str] = None

    # Goal management
    goal_description: Optional[str] = None
    goal_category: Optional[str] = None
    should_update_goal: bool = False


class IntelligentPlanner:
    """
    LLM-driven intelligent conversation planner with specification gathering,
    goal achievement validation, and business-aware decision making.
    Features standardized specification schema to prevent LLM/NLU mismatches.
    """

    def __init__(self, session_id: str = None):
        """Initialize the Intelligent Planner with enhanced goal tracking and specification schema."""
        # Core components
        self.enhanced_nlu = EnhancedNLU()
        self.intent_tracker = IntentTracker()
        self.context_manager = ContextManager(session_id)
        self.llm_client = LLMClient()
        self.mock_agents = MockAgentManager()

        # Planner state
        self.status = PlannerStatus.READY
        self.current_goal: Optional[ConversationGoal] = None
        self.conversation_turns = 0
        self.agent_calls_count = 0

        # Specification gathering state with schema validation
        self.required_specs: Dict[str, Any] = {}
        self.gathered_specs: Dict[str, Any] = {}
        self.specs_confirmed: bool = False

        # Conversation quality tracking
        self.satisfaction_signals_detected = 0
        self.success_indicators_count = 0

    def start_conversation(self) -> Dict[str, Any]:
        """Start a new intelligent conversation with clear business context."""
        welcome_message = (
            "Hi! I'm your intelligent shopping assistant. My goal is to provide you with "
            "excellent service and help you accomplish exactly what you need. I can help you:\n\n"
            "🔍 **Discover and find products** - Get personalized recommendations that match your needs and budget\n"
            "📦 **Track your orders** - Get real-time updates and resolve any delivery concerns\n"
            "↩️ **Process returns and exchanges** - Handle returns quickly and fairly\n"
            "💡 **Get expert recommendations** - Receive tailored advice based on your preferences\n\n"
            "What would you like to accomplish today? I'll make sure we find the perfect solution for you."
        )

        self.context_manager.add_message("system", welcome_message)
        self.status = PlannerStatus.READY

        return {
            "response": welcome_message,
            "status": "ready",
            "session_id": self.context_manager.session_id,
            "goal": None,
            "business_context": "Customer service excellence and satisfaction"
        }

    def process_user_message(self, user_message: str) -> Dict[str, Any]:
        """
        Main processing pipeline with specification gathering, confirmation, and goal evaluation.
        Uses single LLM call per message for efficiency with standardized specification handling.

        Args:
            user_message: User's input message

        Returns:
            Complete response with actions taken and goal evaluation
        """
        try:
            # Add user message to context
            self.context_manager.add_message("user", user_message)
            self.conversation_turns += 1

            # Handle different planner states with enhanced specification processing
            if self.status == PlannerStatus.GATHERING_SPECS:
                return self._handle_specification_gathering(user_message)
            elif self.status == PlannerStatus.CONFIRMING_REQUIREMENTS:
                return self._handle_requirement_confirmation(user_message)
            else:
                # Normal flow - analyze and decide with goal evaluation
                return self._process_new_user_input(user_message)

        except Exception as e:
            return self._handle_error(f"Processing error: {str(e)}", user_message)

    def _process_new_user_input(self, user_message: str) -> Dict[str, Any]:
        """Process new user input through full analysis pipeline with goal evaluation."""

        # Step 1: Analyze user message with NLU
        nlu_result = self._analyze_with_nlu(user_message)

        # Step 2: Update intent tracking
        intent_result = self._analyze_intent_continuity(nlu_result)

        # Step 3: Comprehensive LLM-driven planning decision WITH goal evaluation
        self.status = PlannerStatus.ANALYZING
        planner_decision = self._make_comprehensive_planning_decision(user_message, nlu_result, intent_result)

        # Step 4: Execute the decision and handle goal updates
        return self._execute_planner_decision(planner_decision)

    def _make_comprehensive_planning_decision(self, user_message: str, nlu_result: Dict[str, Any],
                                              intent_result: Dict[str, Any]) -> PlannerDecision:
        """
        Use single LLM call to make intelligent planning decisions AND evaluate goal achievement.
        This is the core method that combines planning and goal evaluation for efficiency.
        """

        # Create comprehensive prompt that handles both planning and goal evaluation
        prompt = self._create_comprehensive_planning_prompt(user_message, nlu_result, intent_result)

        try:
            # Single LLM call for both planning decision and goal evaluation
            llm_response = self.llm_client.generate(prompt)

            # Parse comprehensive LLM response into structured decision with goal evaluation
            decision = self._parse_comprehensive_planner_response(llm_response)

            # Validate and fix specification names to prevent mismatches
            decision = self._validate_and_fix_decision_specs(decision)

            # Update goal based on LLM evaluation (if needed)
            if decision.should_update_goal and decision.goal_description:
                self._update_conversation_goal(
                    decision.goal_description,
                    decision.goal_category or "general",
                    decision.goal_status,
                    decision.goal_progress_score
                )

            return decision

        except Exception as e:
            # Fallback decision making with basic goal evaluation
            return self._create_fallback_decision(user_message, nlu_result, str(e))

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

    def _create_comprehensive_planning_prompt(self, user_message: str, nlu_result: Dict[str, Any],
                                              intent_result: Dict[str, Any]) -> str:
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
        if self.current_goal:
            goal_info = f"""Current Goal: {self.current_goal.description}
Category: {self.current_goal.category}
Status: {self.current_goal.status}
Progress Score: {self.current_goal.progress_score:.1f}/1.0
Business Objective: {self.current_goal.business_objective}

Success Criteria to Evaluate:
{chr(10).join(f"- {criteria}" for criteria in self.current_goal.success_criteria)}

User Satisfaction Indicators to Look For:
{chr(10).join(f"- {indicator}" for indicator in self.current_goal.user_satisfaction_indicators)}"""

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

            # Update satisfaction tracking based on LLM evaluation
            if decision.satisfaction_indicators_present:
                self.satisfaction_signals_detected += len(decision.satisfaction_indicators_present)
                self.success_indicators_count += len(decision.success_criteria_met)

            return decision

        except (json.JSONDecodeError, ValueError) as e:
            return self._create_fallback_decision("", {}, f"Parse error: {str(e)}")

    def _execute_planner_decision(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute the decision made by the planner LLM with integrated goal evaluation."""

        # Update current goal progress based on LLM evaluation
        if self.current_goal and decision.goal_progress_score > 0:
            self.current_goal.progress_score = decision.goal_progress_score
            self.current_goal.updated_at = datetime.now().isoformat()

        # Execute the planning decision
        if decision.action == "gather_specs":
            return self._start_specification_gathering(decision)

        elif decision.action == "confirm_requirements":
            return self._request_requirement_confirmation(decision)

        elif decision.action == "call_agent":
            return self._execute_agent_call(decision)

        elif decision.action == "goal_achieved":
            return self._handle_goal_achieved(decision)

        elif decision.action == "re_plan":
            return self._handle_re_planning(decision)

        elif decision.action == "clarify":
            return self._handle_clarification(decision)

        else:
            return self._handle_unknown_action(decision)

    def _start_specification_gathering(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Start gathering specifications from user with validated specification schema."""

        self.status = PlannerStatus.GATHERING_SPECS

        # Use validated specification names
        validated_specs = SpecificationSchema.validate_spec_names(decision.specifications_needed or [])
        self.required_specs = {spec: None for spec in validated_specs}

        # Generate specification questions using schema
        spec_questions = self._generate_specification_questions(validated_specs)

        message = decision.user_message or spec_questions
        self.context_manager.add_message("system", message)

        return {
            "response": message,
            "status": "gathering_specifications",
            "action": "gather_specs",
            "specifications_needed": validated_specs,
            "reasoning": decision.reasoning,
            "goal_status": decision.goal_status,
            "goal_progress": decision.goal_progress_score,
            "goal_evaluation": {
                "reasoning": decision.goal_achievement_reasoning,
                "criteria_met": decision.success_criteria_met,
                "satisfaction_signals": decision.satisfaction_indicators_present
            }
        }

    def _handle_specification_gathering(self, user_message: str) -> Dict[str, Any]:
        """Handle user responses during specification gathering with enhanced entity mapping and no-preference detection."""

        # Check if user is indicating no preference for all remaining specs
        if SpecificationSchema.detect_no_preference(user_message):
            # Mark all remaining specs as flexible/no_preference
            for spec_name in self.required_specs:
                if not self.required_specs[spec_name]:
                    self.required_specs[spec_name] = "flexible"
                    self.gathered_specs[spec_name] = "flexible"
                    self.context_manager.add_fact(spec_name, "flexible", "user")

            # Move to confirmation since user indicated no preference
            return self._move_to_confirmation()

        # Extract specifications from user response with enhanced mapping
        nlu_result = self._analyze_with_nlu(user_message)
        raw_entities = nlu_result.get("entities", {})

        # Map NLU entities to standard specification names
        mapped_entities = SpecificationSchema.map_entities_to_specs(raw_entities)

        # Manual entity extraction for common cases NLU might miss
        additional_entities = self._extract_additional_entities(user_message)
        mapped_entities.update(additional_entities)

        # Update gathered specifications using mapped entities
        specs_updated = False
        for spec_name, value in mapped_entities.items():
            if spec_name in self.required_specs and value:
                self.required_specs[spec_name] = value
                self.gathered_specs[spec_name] = value
                self.context_manager.add_fact(spec_name, value, "user")
                specs_updated = True

        # Check if we have enough specifications
        missing_specs = [spec for spec, value in self.required_specs.items() if not value]

        if not missing_specs:
            # Have all required specs, move to confirmation
            return self._move_to_confirmation()
        elif specs_updated:
            # Made progress, ask for remaining specs
            questions = self._generate_specification_questions(missing_specs)
            self.context_manager.add_message("system", questions)

            return {
                "response": questions,
                "status": "gathering_specifications",
                "action": "continue_gathering",
                "specifications_needed": missing_specs,
                "specifications_gathered": self.gathered_specs,
                "goal_progress": min(0.7,
                                     len([s for s in self.required_specs.values() if s]) / len(self.required_specs))
            }
        else:
            # No progress made, provide helpful guidance
            helpful_response = self._generate_helpful_clarification(missing_specs, user_message)
            self.context_manager.add_message("system", helpful_response)

            return {
                "response": helpful_response,
                "status": "gathering_specifications",
                "action": "clarify_specs",
                "specifications_needed": missing_specs,
                "specifications_gathered": self.gathered_specs
            }

    def _extract_additional_entities(self, user_message: str) -> Dict[str, Any]:
        """Extract additional entities that NLU might miss using pattern matching."""
        message_lower = user_message.lower()
        additional_entities = {}

        # Extract use case patterns
        gaming_keywords = ["gaming", "games", "game", "esports", "streaming"]
        work_keywords = ["work", "office", "business", "professional", "productivity"]
        study_keywords = ["study", "studies", "education", "student", "school", "college"]

        if any(keyword in message_lower for keyword in gaming_keywords):
            additional_entities["use_case"] = "gaming"
        elif any(keyword in message_lower for keyword in work_keywords):
            additional_entities["use_case"] = "work"
        elif any(keyword in message_lower for keyword in study_keywords):
            additional_entities["use_case"] = "study"

        # Extract budget patterns (INR, USD, etc.)
        import re
        budget_patterns = [
            r'(\d+(?:,\d+)*)\s*(?:inr|rupees|rs\.?)',
            r'(?:inr|rs\.?)\s*(\d+(?:,\d+)*)',
            r'(\d+(?:,\d+)*)\s*(?:usd|dollars?|\$)',
            r'(?:\$|usd)\s*(\d+(?:,\d+)*)',
            r'budget.*?(\d+(?:,\d+)*)',
            r'around\s+(\d+(?:,\d+)*)',
            r'up\s+to\s+(\d+(?:,\d+)*)'
        ]

        for pattern in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                budget_amount = match.group(1).replace(',', '')
                if 'inr' in message_lower or 'rupee' in message_lower or 'rs' in message_lower:
                    additional_entities["budget"] = f"{budget_amount} INR"
                elif 'usd' in message_lower or '$' in message_lower:
                    additional_entities["budget"] = f"{budget_amount} USD"
                else:
                    additional_entities["budget"] = budget_amount
                break

        # Extract brand patterns
        common_brands = ["apple", "dell", "hp", "lenovo", "asus", "acer", "msi", "samsung", "sony", "lg"]
        for brand in common_brands:
            if brand in message_lower:
                additional_entities["brand"] = brand.title()
                break

        return additional_entities

    def _generate_helpful_clarification(self, missing_specs: List[str], user_message: str) -> str:
        """Generate helpful clarification when no progress is made in spec gathering."""

        if len(missing_specs) == 1:
            spec_name = missing_specs[0]
            spec_desc = SpecificationSchema.get_spec_description(spec_name)

            if spec_name == "category":
                return "I'd like to help you find the right product. Are you looking for electronics, clothing, home goods, or something else?"
            elif spec_name == "subcategory":
                return "Could you tell me specifically what type of product you need? For example: laptop, smartphone, headphones, etc.?"
            elif spec_name == "use_case":
                return "What will you mainly use this for? For example: gaming, work, study, entertainment, or general use?"
            elif spec_name == "budget":
                return "What's your budget range? You can say something like '50,000 INR' or 'around $800' or even 'flexible budget'."
            else:
                return f"Could you help me understand your {spec_desc.lower()}? If you don't have a preference, just say 'no preference'."
        else:
            return (
                "I want to find the perfect option for you. Could you help me with a few details? "
                f"I still need to know about: {', '.join(SpecificationSchema.get_spec_description(spec) for spec in missing_specs[:2])}. "
                "If you don't have preferences for any of these, just let me know!"
            )

    def _move_to_confirmation(self) -> Dict[str, Any]:
        """Move from specification gathering to requirement confirmation with quality assurance."""

        self.status = PlannerStatus.CONFIRMING_REQUIREMENTS

        # Create comprehensive confirmation summary
        summary = self._create_requirement_summary()
        confirmation_message = (
            f"{summary}\n\n"
            "I want to make sure I have everything right before finding the perfect options for you. "
            "Does this look correct? Is there anything else you'd like me to consider?"
        )

        self.context_manager.add_message("system", confirmation_message)

        return {
            "response": confirmation_message,
            "status": "confirming_requirements",
            "action": "confirm_requirements",
            "requirement_summary": summary,
            "gathered_specifications": self.gathered_specs,
            "goal_progress": 0.8  # High progress when ready for confirmation
        }

    def _handle_requirement_confirmation(self, user_response: str) -> Dict[str, Any]:
        """Handle user response to requirement confirmation with satisfaction detection."""

        response_lower = user_response.lower()

        # Enhanced confirmation detection with satisfaction signals
        confirmation_signals = ["yes", "correct", "that's right", "looks good", "perfect", "exactly", "right"]
        modification_signals = ["no", "not quite", "actually", "change", "also", "but", "except", "add"]
        satisfaction_signals = ["perfect", "exactly", "great", "wonderful", "excellent"]

        if any(signal in response_lower for signal in confirmation_signals):
            # User confirmed - detect satisfaction level
            if any(signal in response_lower for signal in satisfaction_signals):
                self.satisfaction_signals_detected += 1

            self.specs_confirmed = True
            return self._proceed_to_agent_call()

        elif any(signal in response_lower for signal in modification_signals):
            # User wants to modify - gather additional info with enhanced entity extraction
            additional_entities = self._extract_additional_entities(user_response)

            # Update specifications
            for key, value in additional_entities.items():
                if value:
                    self.gathered_specs[key] = value
                    self.context_manager.add_fact(key, value, "user")

            # Create new confirmation with updated info
            return self._move_to_confirmation()

        else:
            # Try to extract any additional specifications or handle ambiguity
            additional_entities = self._extract_additional_entities(user_response)

            if additional_entities:
                # Add new specifications
                for key, value in additional_entities.items():
                    if value:
                        self.gathered_specs[key] = value
                        self.context_manager.add_fact(key, value, "user")

                return self._move_to_confirmation()
            else:
                # Unclear response - ask for clarification with helpful context
                clarification = (
                    "I want to make sure I understand correctly so I can find the best options for you. "
                    "Should I proceed with the requirements I've listed, or would you like to change something specific? "
                    "You can say 'yes, proceed' or tell me what you'd like to modify."
                )
                self.context_manager.add_message("system", clarification)

                return {
                    "response": clarification,
                    "status": "confirming_requirements",
                    "action": "clarify_confirmation"
                }

    def _proceed_to_agent_call(self) -> Dict[str, Any]:
        """Proceed to call appropriate agent after confirmation with business intelligence."""

        # Determine agent type and parameters with enhanced logic
        current_intent = self.intent_tracker.get_current_intent()

        if current_intent and current_intent.intent_type in ["BUY", "RECOMMEND"]:
            agent_type = "DiscoveryAgent"
            agent_params = {
                "category": self.gathered_specs.get("category", "electronics"),
                "subcategory": self.gathered_specs.get("subcategory", ""),
                "specifications": {k: v for k, v in self.gathered_specs.items()
                                   if k not in ["category", "subcategory", "budget"]},
                "budget": self.gathered_specs.get("budget"),
                "user_message": f"Looking for {self.gathered_specs.get('subcategory', 'products')} based on confirmed requirements",
                "discovery_mode": "auto",
                "quality_focus": True  # Indicate this is a well-qualified lead
            }
        elif current_intent and current_intent.intent_type == "ORDER":
            agent_type = "OrderAgent"
            agent_params = {
                "order_id": self.gathered_specs.get("order_id"),
                "action": "track",
                "priority": "high"  # User went through confirmation process
            }
        elif current_intent and current_intent.intent_type == "RETURN":
            agent_type = "ReturnAgent"
            agent_params = {
                "order_id": self.gathered_specs.get("order_id"),
                "return_reason": self.gathered_specs.get("return_reason", "not_specified"),
                "priority": "high"
            }
        else:
            agent_type = "DiscoveryAgent"
            agent_params = self.gathered_specs

        # Create decision to execute agent call
        decision = PlannerDecision(
            action="call_agent",
            agent_type=agent_type,
            agent_params=agent_params,
            reasoning="All requirements confirmed, proceeding with high-quality agent call",
            goal_progress_score=0.9  # High progress when calling agent with confirmed specs
        )

        return self._execute_agent_call(decision)

    def _execute_agent_call(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute agent call with integrated goal achievement evaluation."""
        self.status = PlannerStatus.EXECUTING_AGENT

        try:
            # Call the appropriate agent
            agent_result = self.mock_agents.call_agent(
                decision.agent_type,
                decision.agent_params,
                self.context_manager.get_context_summary()
            )

            # Store agent result in context
            self.context_manager.store_agent_result(decision.agent_type, agent_result)
            self.agent_calls_count += 1

            # Add agent response to conversation
            if agent_result.get("user_message"):
                self.context_manager.add_message("system", agent_result["user_message"])

            # Reset specification gathering state
            self.status = PlannerStatus.READY
            self.gathered_specs = {}
            self.specs_confirmed = False

            # Evaluate goal achievement based on agent result and conversation context
            goal_evaluation = self._evaluate_post_agent_goal_status(agent_result, decision)

            response = {
                "response": agent_result.get("user_message",
                                             "I've processed your request successfully and found great options for you."),
                "status": "agent_executed",
                "action": "agent_call",
                "agent_type": decision.agent_type,
                "agent_result": agent_result,
                "goal_status": goal_evaluation["status"],
                "goal_achieved": goal_evaluation["achieved"],
                "goal_progress": goal_evaluation["progress_score"],
                "goal_evaluation": {
                    "reasoning": goal_evaluation["reasoning"],
                    "criteria_met": goal_evaluation["criteria_met"],
                    "satisfaction_signals": goal_evaluation["satisfaction_signals"],
                    "business_value": goal_evaluation["business_value"]
                }
            }

            # Update planner status based on goal evaluation
            if goal_evaluation["achieved"]:
                self.status = PlannerStatus.GOAL_ACHIEVED
                response["session_complete"] = True
                if self.current_goal:
                    self.current_goal.status = "completed"
                    self.current_goal.progress_score = 1.0
                    self.current_goal.updated_at = datetime.now().isoformat()

            return response

        except Exception as e:
            return self._handle_error(f"Agent execution error: {str(e)}", "agent_call")

    def _evaluate_post_agent_goal_status(self, agent_result: Dict[str, Any], decision: PlannerDecision) -> Dict[
        str, Any]:
        """Evaluate goal achievement after agent execution based on results and context."""

        if not self.current_goal:
            return {
                "achieved": False,
                "status": "no_goal",
                "progress_score": 0.0,
                "reasoning": "No goal defined",
                "criteria_met": [],
                "satisfaction_signals": [],
                "business_value": "none"
            }

        # Determine goal achievement based on agent results and goal type
        achieved = False
        progress_score = decision.goal_progress_score or 0.8  # Start with previous progress
        criteria_met = []
        satisfaction_signals = []
        business_value = "moderate"

        if self.current_goal.category == "discovery":
            # Discovery goal evaluation
            if agent_result.get("products_found", 0) > 0:
                criteria_met.append("User receives relevant product recommendations")
                progress_score = max(progress_score, 0.9)
                business_value = "high"

                if agent_result.get("products_found", 0) >= 3:
                    criteria_met.append("Products match user's specified requirements")
                    achieved = True  # Good product results typically indicate goal achievement
                    progress_score = 1.0

        elif self.current_goal.category == "order":
            # Order tracking goal evaluation
            if agent_result.get("order_found"):
                criteria_met.append("Order status information is provided")
                criteria_met.append("User receives clear tracking information")
                achieved = True
                progress_score = 1.0
                business_value = "high"

        elif self.current_goal.category == "return":
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
        if self.specs_confirmed:
            satisfaction_signals.append("User confirmed requirements indicating engagement")
        if achieved:
            satisfaction_signals.append("Successful task completion indicates satisfaction")

        return {
            "achieved": achieved,
            "status": "achieved" if achieved else "in_progress",
            "progress_score": progress_score,
            "reasoning": f"Agent {decision.agent_type} executed successfully. Criteria met: {len(criteria_met)}/{len(self.current_goal.success_criteria)}",
            "criteria_met": criteria_met,
            "satisfaction_signals": satisfaction_signals,
            "business_value": business_value
        }

    def _generate_specification_questions(self, needed_specs: List[str]) -> str:
        """Generate intelligent, business-aware questions for needed specifications using schema."""

        if not needed_specs:
            return "I need a bit more information to find the perfect solution for you."

        questions = []

        for spec in needed_specs:
            if spec == "category":
                questions.append(
                    "What type of product are you interested in? (For example: electronics, clothing, home goods)")
            elif spec == "subcategory":
                questions.append(
                    "Could you be more specific about what you need? (For example: laptop, smartphone, headphones)")
            elif spec == "use_case":
                questions.append(
                    "What will you mainly use this for? (For example: gaming, work, study, or general use)")
            elif spec == "budget":
                questions.append(
                    "What's your budget range? (For example: '50,000 INR' or 'around $800', or say 'flexible' if you're open)")
            elif spec == "brand":
                questions.append(
                    "Do you have any brand preferences or ones you'd like me to avoid? (Say 'no preference' if you're flexible)")
            elif spec == "specifications":
                questions.append(
                    "Are there any specific features or requirements that are important to you? (Or say 'no specific requirements')")
            else:
                questions.append(
                    f"Could you tell me about your {SpecificationSchema.get_spec_description(spec).lower()}? (Say 'no preference' if you're flexible)")

        if len(questions) == 1:
            return questions[0]
        elif len(questions) <= 2:
            return " ".join(questions)
        else:
            return questions[0] + " Let's start with that, and then I'll ask about the other details."

    def _create_requirement_summary(self) -> str:
        """Create a comprehensive, professional summary of gathered requirements."""

        summary_parts = []

        if self.gathered_specs.get("subcategory"):
            subcategory = self.gathered_specs["subcategory"]
            if subcategory == "flexible":
                summary_parts.append(f"**Product**: Flexible - open to recommendations")
            else:
                summary_parts.append(f"**Product**: {subcategory}")

        if self.gathered_specs.get("use_case"):
            use_case = self.gathered_specs["use_case"]
            if use_case == "flexible":
                summary_parts.append(f"**Primary Use**: Flexible - general purpose")
            else:
                summary_parts.append(f"**Primary Use**: {use_case}")

        if self.gathered_specs.get("budget"):
            budget = self.gathered_specs["budget"]
            if budget == "flexible":
                summary_parts.append(f"**Budget**: Flexible - open to various price points")
            else:
                summary_parts.append(f"**Budget**: {budget}")

        # Add other specifications with professional formatting
        other_specs = {k: v for k, v in self.gathered_specs.items()
                       if k not in ["category", "subcategory", "use_case", "budget"] and v}

        if other_specs:
            for spec_name, spec_value in other_specs.items():
                spec_display_name = SpecificationSchema.get_spec_description(spec_name)
                if spec_value == "flexible":
                    spec_strs = f"**{spec_display_name}**: Flexible - no specific preference"
                else:
                    spec_strs = f"**{spec_display_name}**: {spec_value}"
                summary_parts.append(spec_strs)

        return "Here's what I understand about your requirements:\n\n" + "\n".join(
            [f"• {part}" for part in summary_parts])

    def _handle_goal_achieved(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle goal achievement scenario with comprehensive completion logic."""
        self.status = PlannerStatus.GOAL_ACHIEVED

        if self.current_goal:
            self.current_goal.status = "completed"
            self.current_goal.progress_score = 1.0
            self.current_goal.updated_at = datetime.now().isoformat()

        # Create a satisfying completion message based on goal type and context
        if self.current_goal:
            if self.current_goal.category == "discovery":
                completion_message = (
                        decision.user_message or
                        "Excellent! I've found some great options that match your requirements perfectly. "
                        "I'm confident these recommendations will meet your needs. Is there anything else I can help you with today?"
                )
            elif self.current_goal.category == "order":
                completion_message = (
                        decision.user_message or
                        "Great! I've provided you with complete information about your order. "
                        "Everything looks good and you're all set. Is there anything else I can help you with?"
                )
            elif self.current_goal.category == "return":
                completion_message = (
                        decision.user_message or
                        "Perfect! I've set up your return process and you have everything you need. "
                        "The return is all arranged. Is there anything else I can assist you with today?"
                )
            else:
                completion_message = (
                        decision.user_message or
                        "Wonderful! I've successfully helped you accomplish what you needed. "
                        "I'm glad I could assist you today. Is there anything else I can help you with?"
                )
        else:
            completion_message = decision.user_message or "Great! I've successfully helped you accomplish your goal. Is there anything else you'd like to do?"

        self.context_manager.add_message("system", completion_message)

        return {
            "response": completion_message,
            "status": "goal_achieved",
            "action": "session_complete",
            "goal": self.current_goal.description if self.current_goal else None,
            "goal_category": self.current_goal.category if self.current_goal else None,
            "session_complete": True,
            "business_outcome": "successful_completion",
            "satisfaction_level": "high" if self.satisfaction_signals_detected > 0 else "good"
        }

    def _handle_re_planning(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle re-planning scenario with user explanation and goal transition."""
        self.status = PlannerStatus.RE_PLANNING

        # Create explanation message that acknowledges the change
        explanation = decision.user_message or (
            "I understand you'd like to focus on something different now. "
            f"That's perfectly fine! Let me help you with this new request. {decision.reasoning}"
        )

        self.context_manager.add_message("system", explanation)

        # Reset specification state for new planning
        self.gathered_specs = {}
        self.specs_confirmed = False

        # Handle goal transition
        if self.current_goal:
            self.current_goal.status = "replanning"
            self.current_goal.updated_at = datetime.now().isoformat()

        self.status = PlannerStatus.READY

        return {
            "response": explanation,
            "status": "re_planning",
            "action": "re_plan",
            "reasoning": decision.reasoning,
            "new_goal_direction": decision.goal_description,
            "goal_transition": "acknowledged_and_adapting"
        }

    def _handle_clarification(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle clarification request with helpful, business-focused messaging."""

        clarification_message = decision.user_message or (
            "I want to make sure I give you exactly what you need. "
            "Could you provide a bit more detail about what you're looking for? "
            "The more specific you can be, the better I can help you."
        )

        self.context_manager.add_message("system", clarification_message)

        return {
            "response": clarification_message,
            "status": "clarification_needed",
            "action": "clarify",
            "reasoning": decision.reasoning,
            "goal_status": decision.goal_status,
            "business_intent": "ensuring_accurate_assistance"
        }

    def _update_conversation_goal(self, description: str, category: str, status: str, progress_score: float = 0.0):
        """Update or create conversation goal with comprehensive tracking."""

        if self.current_goal and self.current_goal.description == description:
            # Update existing goal
            self.current_goal.status = status
            self.current_goal.progress_score = max(self.current_goal.progress_score, progress_score)
            self.current_goal.updated_at = datetime.now().isoformat()
        else:
            # Create new goal with enhanced initialization
            self.current_goal = ConversationGoal(
                description=description,
                category=category,
                status=status,
                progress_score=progress_score
            )

        # Store goal information in context manager for persistence
        self.context_manager.add_fact("current_goal", description, "planner")
        self.context_manager.add_fact("goal_category", category, "planner")
        self.context_manager.add_fact("goal_progress", str(progress_score), "planner")

    def _analyze_with_nlu(self, user_message: str) -> Dict[str, Any]:
        """Analyze user message with NLU and track satisfaction signals."""
        conversation_context = self.context_manager.get_recent_messages(6)
        nlu_result = self.enhanced_nlu.analyze_message(user_message, conversation_context)

        # Detect satisfaction signals in user message
        satisfaction_keywords = ["thanks", "perfect", "great", "excellent", "wonderful", "amazing", "helpful",
                                 "exactly"]
        if any(keyword in user_message.lower() for keyword in satisfaction_keywords):
            self.satisfaction_signals_detected += 1

        self.context_manager.merge_facts_from_nlu(nlu_result)
        return nlu_result

    def _analyze_intent_continuity(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze intent continuity with enhanced goal awareness."""
        conversation_context = self.context_manager.get_recent_messages(6)
        return self.intent_tracker.track_new_intent(nlu_result, conversation_context)

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

    def _handle_unknown_action(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle unknown action type with business-appropriate messaging."""

        fallback_message = "I want to make sure I help you in the best way possible. Could you help me understand what you'd like to accomplish?"
        self.context_manager.add_message("system", fallback_message)

        return {
            "response": fallback_message,
            "status": "unknown_action",
            "action": "clarify",
            "original_decision": decision.action,
            "business_recovery": "attempting_clarification"
        }

    def _handle_error(self, error_message: str, context: str) -> Dict[str, Any]:
        """Handle errors gracefully with customer service focus."""
        self.status = PlannerStatus.ERROR

        user_message = "I apologize for the brief delay. Let me make sure I give you the best possible assistance. How can I help you today?"
        self.context_manager.add_message("system", user_message)
        self.context_manager.add_fact("last_error", error_message, "system")

        # Reset to ready state for recovery
        self.status = PlannerStatus.READY
        self.gathered_specs = {}
        self.specs_confirmed = False

        return {
            "response": user_message,
            "status": "error_recovered",
            "action": "retry",
            "error_context": context,
            "business_response": "graceful_error_recovery"
        }

    def get_session_info(self) -> Dict[str, Any]:
        """Get comprehensive session information with enhanced goal tracking."""

        current_intent = self.intent_tracker.get_current_intent()
        context_summary = self.context_manager.get_context_summary()

        goal_info = None
        if self.current_goal:
            goal_info = {
                "description": self.current_goal.description,
                "category": self.current_goal.category,
                "status": self.current_goal.status,
                "progress_score": self.current_goal.progress_score,
                "business_objective": self.current_goal.business_objective,
                "success_criteria": self.current_goal.success_criteria,
                "satisfaction_indicators": self.current_goal.user_satisfaction_indicators,
                "created_at": self.current_goal.created_at,
                "updated_at": self.current_goal.updated_at
            }

        return {
            "session_id": self.context_manager.session_id,
            "planner_status": self.status.value,
            "current_goal": goal_info,
            "current_intent": {
                "type": current_intent.intent_type if current_intent else None,
                "summary": current_intent.get_summary() if current_intent else None
            },
            "context_summary": context_summary,
            "conversation_turns": self.conversation_turns,
            "agent_calls_made": self.agent_calls_count,
            "specification_gathering": {
                "required_specs": self.required_specs,
                "gathered_specs": self.gathered_specs,
                "confirmed": self.specs_confirmed
            },
            "conversation_quality": {
                "satisfaction_signals_detected": self.satisfaction_signals_detected,
                "success_indicators_count": self.success_indicators_count
            },
            "session_active": self.context_manager.session_active,
            "business_metrics": {
                "goal_completion_rate": self.current_goal.progress_score if self.current_goal else 0.0,
                "customer_engagement": "high" if self.satisfaction_signals_detected > 0 else "moderate"
            }
        }

    def end_conversation(self, reason: str = "user_exit") -> Dict[str, Any]:
        """End conversation gracefully with business outcome tracking."""

        closing_message = self.context_manager.end_session(reason)
        self.status = PlannerStatus.GOAL_ACHIEVED

        if self.current_goal and self.current_goal.status != "completed":
            self.current_goal.status = f"ended_{reason}"
            self.current_goal.updated_at = datetime.now().isoformat()

        # Determine business outcome
        business_outcome = "natural_completion"
        if self.current_goal and self.current_goal.progress_score >= 0.8:
            business_outcome = "successful_completion"
        elif reason == "user_exit" and self.current_goal and self.current_goal.progress_score < 0.5:
            business_outcome = "early_exit"

        return {
            "response": closing_message,
            "status": "conversation_ended",
            "reason": reason,
            "business_outcome": business_outcome,
            "session_summary": self.get_session_info(),
            "final_satisfaction_level": "high" if self.satisfaction_signals_detected > 1 else "moderate"
        }


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
    print(f"   Specs Gathered: {response2.get('specifications_gathered', {})}")
    print(f"   Remaining Specs: {response2.get('specifications_needed', [])}")

    # Test 4: User says "no preference" for remaining specs
    print("\n4️⃣ User indicates no preference:")
    user_message = "I have no preference for the rest"
    print(f"User Message: {user_message}")
    response3 = planner.process_user_message(user_message)
    print(f"   Status: {response3['status']}")
    print(f"   Action: {response3.get('action')}")
    if response3.get('gathered_specifications'):
        print(f"   Final Specs: {response3['gathered_specifications']}")

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
    print(f"   Satisfaction Signals: {planner.satisfaction_signals_detected}")

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


if __name__ == "__main__":
    test_enhanced_specification_handling()
    print("\n" + "=" * 50)
    test_intelligent_planner()