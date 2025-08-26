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
- Goal-oriented validation after every agent call
- Dynamic re-planning with user explanation
- Intelligent conversation state management
"""

import json
from dataclasses import dataclass
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


@dataclass
class ConversationGoal:
    """Represents the current conversation goal."""
    description: str
    category: str  # "discovery", "order", "return", "general"
    success_criteria: str
    created_at: str
    updated_at: str
    status: str = "active"


@dataclass
class PlannerDecision:
    """Represents a decision made by the planner LLM."""
    action: str  # "gather_specs", "confirm_requirements", "call_agent", "goal_achieved", "re_plan", "clarify"
    agent_type: Optional[str] = None
    agent_params: Optional[Dict[str, Any]] = None
    goal_status: str = "in_progress"  # "in_progress", "achieved", "needs_replanning"
    reasoning: str = ""
    user_message: Optional[str] = None
    confidence: float = 0.8
    specifications_needed: List[str] = None
    confirmation_summary: Optional[str] = None


class IntelligentPlanner:
    """
    LLM-driven intelligent conversation planner with specification gathering
    and Discovery Agent integration.
    """

    def __init__(self, session_id: str = None):
        """Initialize the Intelligent Planner."""
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

        # Specification gathering state
        self.required_specs: Dict[str, Any] = {}
        self.gathered_specs: Dict[str, Any] = {}
        self.specs_confirmed: bool = False

        # # Category specification requirements
        # self.category_requirements = {
        #     "laptop": {
        #         "required": ["category", "subcategory"],
        #         "important": ["use_case", "budget"],
        #         "optional": ["brand", "screen_size", "specifications"]
        #     },
        #     "smartphone": {
        #         "required": ["category", "subcategory"],
        #         "important": ["use_case", "budget"],
        #         "optional": ["brand", "camera_quality", "storage"]
        #     },
        #     "headphones": {
        #         "required": ["category", "subcategory"],
        #         "important": ["use_case", "budget"],
        #         "optional": ["type", "brand", "features"]
        #     }
        # }

    def start_conversation(self) -> Dict[str, Any]:
        """Start a new intelligent conversation."""
        welcome_message = (
            "Hi! I'm your intelligent shopping assistant. I can help you:\n"
            "🔍 Discover and find products\n"
            "📦 Track your orders\n"
            "↩️ Process returns and exchanges\n"
            "💡 Get personalized recommendations\n\n"
            "What would you like to accomplish today?"
        )

        self.context_manager.add_message("system", welcome_message)
        self.status = PlannerStatus.READY

        return {
            "response": welcome_message,
            "status": "ready",
            "session_id": self.context_manager.session_id,
            "goal": None
        }

    def process_user_message(self, user_message: str) -> Dict[str, Any]:
        """
        Main processing pipeline with specification gathering and confirmation.

        Args:
            user_message: User's input message

        Returns:
            Complete response with actions taken
        """
        try:
            # Add user message to context
            self.context_manager.add_message("user", user_message)
            self.conversation_turns += 1

            # Handle different planner states
            if self.status == PlannerStatus.GATHERING_SPECS:
                return self._handle_specification_gathering(user_message)
            elif self.status == PlannerStatus.CONFIRMING_REQUIREMENTS:
                return self._handle_requirement_confirmation(user_message)
            else:
                # Normal flow - analyze and decide
                return self._process_new_user_input(user_message)

        except Exception as e:
            return self._handle_error(f"Processing error: {str(e)}", user_message)

    def _process_new_user_input(self, user_message: str) -> Dict[str, Any]:
        """Process new user input through full analysis pipeline."""

        # Step 1: Analyze user message with NLU
        nlu_result = self._analyze_with_nlu(user_message)

        # Step 2: Update intent tracking
        intent_result = self._analyze_intent_continuity(nlu_result)

        # Step 3: LLM-driven planning decision
        self.status = PlannerStatus.ANALYZING
        planner_decision = self._make_planning_decision(user_message, nlu_result, intent_result)

        # Step 4: Execute the decision
        return self._execute_planner_decision(planner_decision)

    def _make_planning_decision(self, user_message: str, nlu_result: Dict[str, Any],
                                intent_result: Dict[str, Any]) -> PlannerDecision:
        """Use LLM to make intelligent planning decisions."""

        # Create comprehensive prompt for LLM planning
        prompt = self._create_planning_prompt(user_message, nlu_result, intent_result)

        try:
            # Get LLM decision
            llm_response = self.llm_client.generate(prompt)

            # Parse LLM response into structured decision
            decision = self._parse_planner_response(llm_response)

            return decision

        except Exception as e:
            # Fallback decision making
            return self._create_fallback_decision(user_message, nlu_result, str(e))

    def _create_planning_prompt(self, user_message: str, nlu_result: Dict[str, Any],
                                intent_result: Dict[str, Any]) -> str:
        """Create comprehensive LLM prompt for planning decisions."""

        # Get current context
        context_summary = self.context_manager.get_context_summary()
        recent_messages = self.context_manager.get_recent_messages(6)
        current_intent = self.intent_tracker.get_current_intent()

        # Format conversation history
        conversation_context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in recent_messages[-4:]
        ]) if recent_messages else "No previous conversation"

        # Current goal status
        goal_info = "No goal set yet"
        if self.current_goal:
            goal_info = f"Current Goal: {self.current_goal.description} (Status: {self.current_goal.status})"

        # Current facts available
        facts_info = []
        facts = context_summary.get('facts_by_source', {})
        for source, source_facts in facts.items():
            for key, value in source_facts.items():
                facts_info.append(f"{key}: {value}")

        facts_str = ", ".join(facts_info) if facts_info else "No facts gathered yet"

        prompt = f"""
You are an intelligent conversation planner for an e-commerce assistant. Make smart decisions about what to do next.

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

AVAILABLE AGENTS:
- DiscoveryAgent: Dual-mode product discovery (search + recommendations)
- OrderAgent: Track orders, check status, handle order queries  
- ReturnAgent: Process returns, exchanges, refunds

DECISION FRAMEWORK:
For Discovery requests (buying, browsing, recommendations):
1. Check if we have REQUIRED info: category + subcategory
2. If missing required info → gather_specs
3. If have required info but missing important details (budget, use_case) → gather_specs  
4. If have good info but not confirmed → confirm_requirements
5. If confirmed → call_agent (DiscoveryAgent)

For Order/Return requests:
1. If user has order_id → call_agent directly
2. If no order_id → call_agent (agent will show options)

DECISION TYPES:
- gather_specs: Need to collect more specifications from user
- confirm_requirements: Have info, need user confirmation before proceeding
- call_agent: Ready to call agent with collected information
- goal_achieved: User's objective is complete
- re_plan: User changed direction, need new approach  
- clarify: Need clarification from user

Return JSON:
{{
  "action": "gather_specs|confirm_requirements|call_agent|goal_achieved|re_plan|clarify",
  "agent_type": "DiscoveryAgent|OrderAgent|ReturnAgent|null",
  "agent_params": {{"category": "...", "subcategory": "...", "specifications": {{}}}},
  "goal_status": "in_progress|achieved|needs_replanning",
  "goal_description": "natural_language_goal_description",
  "goal_category": "discovery|order|return|general", 
  "reasoning": "why_this_decision_makes_sense",
  "user_message": "what_to_tell_the_user_or_null",
  "confidence": 0.0-1.0,
  "specifications_needed": ["list_of_specs_to_gather"],
  "confirmation_summary": "summary_of_requirements_for_confirmation"
}}

Be methodical about gathering requirements before calling agents. Ensure user satisfaction.
"""
        return prompt

    def _execute_planner_decision(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute the decision made by the planner LLM."""

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
        """Start gathering specifications from user."""

        self.status = PlannerStatus.GATHERING_SPECS
        self.required_specs = {spec: None for spec in (decision.specifications_needed or [])}

        # Generate specification questions
        spec_questions = self._generate_specification_questions(decision.specifications_needed or [])

        message = decision.user_message or spec_questions
        self.context_manager.add_message("system", message)

        return {
            "response": message,
            "status": "gathering_specifications",
            "action": "gather_specs",
            "specifications_needed": decision.specifications_needed,
            "reasoning": decision.reasoning
        }

    def _handle_specification_gathering(self, user_message: str) -> Dict[str, Any]:
        """Handle user responses during specification gathering."""

        # Extract specifications from user response
        nlu_result = self._analyze_with_nlu(user_message)
        entities = nlu_result.get("entities", {})

        # Update gathered specifications
        for key, value in entities.items():
            if key in self.required_specs:
                self.gathered_specs[key] = value
                self.required_specs[key] = value

        # Store in context
        for key, value in entities.items():
            if value:
                self.context_manager.add_fact(key, value, "user")

        # Check if we have enough specifications
        missing_specs = [spec for spec, value in self.required_specs.items() if not value]

        if missing_specs:
            # Still need more specs
            questions = self._generate_specification_questions(missing_specs)
            self.context_manager.add_message("system", questions)

            return {
                "response": questions,
                "status": "gathering_specifications",
                "action": "continue_gathering",
                "specifications_needed": missing_specs,
                "specifications_gathered": self.gathered_specs
            }
        else:
            # Have all required specs, move to confirmation
            return self._move_to_confirmation()

    def _move_to_confirmation(self) -> Dict[str, Any]:
        """Move from specification gathering to requirement confirmation."""

        self.status = PlannerStatus.CONFIRMING_REQUIREMENTS

        # Create confirmation summary
        summary = self._create_requirement_summary()
        confirmation_message = f"{summary}\n\nIs this correct? Anything else you'd like to specify?"

        self.context_manager.add_message("system", confirmation_message)

        return {
            "response": confirmation_message,
            "status": "confirming_requirements",
            "action": "confirm_requirements",
            "requirement_summary": summary,
            "gathered_specifications": self.gathered_specs
        }

    def _handle_requirement_confirmation(self, user_response: str) -> Dict[str, Any]:
        """Handle user response to requirement confirmation."""

        response_lower = user_response.lower()

        # Check for confirmation signals
        if any(word in response_lower for word in ["yes", "correct", "that's right", "looks good", "perfect"]):
            # User confirmed - proceed to agent call
            self.specs_confirmed = True
            return self._proceed_to_agent_call()

        elif any(word in response_lower for word in ["no", "not quite", "actually", "change", "also"]):
            # User wants to modify - gather additional info
            nlu_result = self._analyze_with_nlu(user_response)
            entities = nlu_result.get("entities", {})

            # Update specifications
            for key, value in entities.items():
                if value:
                    self.gathered_specs[key] = value
                    self.context_manager.add_fact(key, value, "user")

            # Create new confirmation
            return self._move_to_confirmation()

        else:
            # Extract any additional specifications
            nlu_result = self._analyze_with_nlu(user_response)
            entities = nlu_result.get("entities", {})

            if entities:
                # Add new specifications
                for key, value in entities.items():
                    if value:
                        self.gathered_specs[key] = value
                        self.context_manager.add_fact(key, value, "user")

                return self._move_to_confirmation()
            else:
                # Unclear response - ask for clarification
                clarification = "I want to make sure I understand correctly. Should I proceed with these requirements, or would you like to change something?"
                self.context_manager.add_message("system", clarification)

                return {
                    "response": clarification,
                    "status": "confirming_requirements",
                    "action": "clarify_confirmation"
                }

    def _proceed_to_agent_call(self) -> Dict[str, Any]:
        """Proceed to call appropriate agent after confirmation."""

        # Determine agent type and parameters
        current_intent = self.intent_tracker.get_current_intent()

        if current_intent and current_intent.intent_type in ["BUY", "RECOMMEND"]:
            agent_type = "DiscoveryAgent"
            agent_params = {
                "category": self.gathered_specs.get("category", "electronics"),
                "subcategory": self.gathered_specs.get("subcategory", ""),
                "specifications": {k: v for k, v in self.gathered_specs.items()
                                   if k not in ["category", "subcategory", "budget"]},
                "budget": self.gathered_specs.get("budget"),
                "user_message": f"Looking for {self.gathered_specs.get('subcategory', 'products')}",
                "discovery_mode": "auto"
            }
        elif current_intent and current_intent.intent_type == "ORDER":
            agent_type = "OrderAgent"
            agent_params = {
                "order_id": self.gathered_specs.get("order_id"),
                "action": "track"
            }
        elif current_intent and current_intent.intent_type == "RETURN":
            agent_type = "ReturnAgent"
            agent_params = {
                "order_id": self.gathered_specs.get("order_id"),
                "return_reason": self.gathered_specs.get("return_reason", "not_specified")
            }
        else:
            agent_type = "DiscoveryAgent"
            agent_params = self.gathered_specs

        # Create decision to execute agent call
        decision = PlannerDecision(
            action="call_agent",
            agent_type=agent_type,
            agent_params=agent_params,
            reasoning="All requirements confirmed, proceeding with agent call"
        )

        return self._execute_agent_call(decision)

    def _execute_agent_call(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute agent call and check goal achievement."""
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

            # Check if goal is achieved after agent call
            goal_check = self._check_goal_achievement()

            response = {
                "response": agent_result.get("user_message", "I've processed your request successfully."),
                "status": "agent_executed",
                "action": "agent_call",
                "agent_type": decision.agent_type,
                "agent_result": agent_result,
                "goal_status": goal_check["status"],
                "goal_achieved": goal_check["achieved"]
            }

            # Update planner status based on goal check
            if goal_check["achieved"]:
                self.status = PlannerStatus.GOAL_ACHIEVED
                response["session_complete"] = True

            return response

        except Exception as e:
            return self._handle_error(f"Agent execution error: {str(e)}", "agent_call")

    def _generate_specification_questions(self, needed_specs: List[str]) -> str:
        """Generate intelligent questions for needed specifications."""

        if not needed_specs:
            return "I need a bit more information to help you better."

        questions = []

        for spec in needed_specs:
            if spec == "category":
                questions.append("What type of product are you interested in?")
            elif spec == "subcategory":
                questions.append("Could you be more specific about what you're looking for?")
            elif spec == "use_case":
                questions.append("What will you mainly use it for?")
            elif spec == "budget":
                questions.append("What's your budget range?")
            elif spec == "brand":
                questions.append("Do you have any brand preferences?")
            elif spec == "specifications":
                questions.append("Any important features or specifications?")
            else:
                questions.append(f"Could you tell me about your {spec} preference?")

        if len(questions) == 1:
            return questions[0]
        elif len(questions) <= 3:
            return " ".join(questions)
        else:
            return questions[0] + " Let's start with that."

    def _create_requirement_summary(self) -> str:
        """Create a summary of gathered requirements."""

        summary_parts = []

        if self.gathered_specs.get("subcategory"):
            summary_parts.append(f"Looking for: {self.gathered_specs['subcategory']}")

        if self.gathered_specs.get("use_case"):
            summary_parts.append(f"Use case: {self.gathered_specs['use_case']}")

        if self.gathered_specs.get("budget"):
            summary_parts.append(f"Budget: {self.gathered_specs['budget']}")

        # Add other specifications
        other_specs = {k: v for k, v in self.gathered_specs.items()
                       if k not in ["category", "subcategory", "use_case", "budget"] and v}

        if other_specs:
            spec_strs = [f"{k}: {v}" for k, v in other_specs.items()]
            summary_parts.append(f"Specifications: {', '.join(spec_strs)}")

        return "Here's what I understand:\n• " + "\n• ".join(summary_parts)

    def _check_goal_achievement(self) -> Dict[str, Any]:
        """Use LLM to check if current goal is achieved."""

        if not self.current_goal:
            return {"achieved": False, "status": "no_goal", "reasoning": "No goal set"}

        # Create goal achievement check prompt
        context_summary = self.context_manager.get_context_summary()
        recent_messages = self.context_manager.get_recent_messages(4)

        conversation_context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in recent_messages
        ]) if recent_messages else "No conversation"

        prompt = f"""
You are evaluating whether a user's goal has been achieved in a conversation.

GOAL TO EVALUATE:
Description: {self.current_goal.description}
Category: {self.current_goal.category}
Success Criteria: {self.current_goal.success_criteria}

CURRENT SITUATION:
Total Facts Available: {context_summary.get('total_facts', 0)}
Agent Calls Made: {self.agent_calls_count}
Recent Conversation:
{conversation_context}

EVALUATION TASK:
Has the user's goal been genuinely achieved? Consider:
1. Did we provide what the user actually wanted?
2. Is the user satisfied with the outcome?
3. Are there any loose ends or unresolved issues?
4. Does the user seem ready to end the conversation?

Return JSON:
{{
  "achieved": true/false,
  "status": "achieved|in_progress|needs_more_info",
  "reasoning": "detailed_explanation_of_assessment",
  "confidence": 0.0-1.0,
  "next_suggestion": "what_should_happen_next_or_null"
}}

Be honest and thorough in your evaluation.
"""

        try:
            llm_response = self.llm_client.generate(prompt)

            # Parse response
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

            return {
                "achieved": parsed.get("achieved", False),
                "status": parsed.get("status", "in_progress"),
                "reasoning": parsed.get("reasoning", "Goal achievement check completed"),
                "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.8)))),
                "next_suggestion": parsed.get("next_suggestion")
            }

        except Exception as e:
            # Fallback assessment
            return {
                "achieved": False,
                "status": "in_progress",
                "reasoning": f"Could not evaluate goal achievement: {str(e)}",
                "confidence": 0.5
            }

    def _parse_planner_response(self, llm_response: str) -> PlannerDecision:
        """Parse LLM response into structured PlannerDecision."""

        if llm_response.startswith("[LLM-FALLBACK]"):
            return self._create_fallback_decision("", {}, "LLM fallback mode")

        try:
            # Clean and parse JSON
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

            # Create PlannerDecision
            decision = PlannerDecision(
                action=parsed.get("action", "clarify"),
                agent_type=parsed.get("agent_type"),
                agent_params=parsed.get("agent_params", {}),
                goal_status=parsed.get("goal_status", "in_progress"),
                reasoning=parsed.get("reasoning", "LLM planning decision"),
                user_message=parsed.get("user_message"),
                confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.8)))),
                specifications_needed=parsed.get("specifications_needed", []),
                confirmation_summary=parsed.get("confirmation_summary")
            )

            # Update or create goal if needed
            if parsed.get("goal_description"):
                self._update_conversation_goal(
                    parsed["goal_description"],
                    parsed.get("goal_category", "general"),
                    decision.goal_status
                )

            return decision

        except (json.JSONDecodeError, ValueError) as e:
            return self._create_fallback_decision("", {}, f"Parse error: {str(e)}")

    def _handle_goal_achieved(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle goal achievement scenario."""
        self.status = PlannerStatus.GOAL_ACHIEVED

        if self.current_goal:
            self.current_goal.status = "completed"
            self.current_goal.updated_at = datetime.now().isoformat()

        completion_message = decision.user_message or "Great! I've successfully helped you accomplish your goal. Is there anything else you'd like to do?"

        self.context_manager.add_message("system", completion_message)

        return {
            "response": completion_message,
            "status": "goal_achieved",
            "action": "session_complete",
            "goal": self.current_goal.description if self.current_goal else None,
            "session_complete": True
        }

    def _handle_re_planning(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle re-planning scenario with user explanation."""
        self.status = PlannerStatus.RE_PLANNING

        # Create explanation message
        explanation = decision.user_message or (
            "I understand you'd like to change direction. "
            f"Let me help you with this new request. {decision.reasoning}"
        )

        self.context_manager.add_message("system", explanation)

        # Reset specification state for new planning
        self.gathered_specs = {}
        self.specs_confirmed = False

        # Reset relevant state for new planning
        if self.current_goal:
            self.current_goal.status = "replanning"
            self.current_goal.updated_at = datetime.now().isoformat()

        self.status = PlannerStatus.READY

        return {
            "response": explanation,
            "status": "re_planning",
            "action": "re_plan",
            "reasoning": decision.reasoning,
            "new_goal": decision.goal_status
        }

    def _handle_clarification(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle clarification request."""

        clarification_message = decision.user_message or "I need a bit more information to help you better. Could you provide more details about what you're looking for?"

        self.context_manager.add_message("system", clarification_message)

        return {
            "response": clarification_message,
            "status": "clarification_needed",
            "action": "clarify",
            "reasoning": decision.reasoning
        }

    def _update_conversation_goal(self, description: str, category: str, status: str):
        """Update or create conversation goal."""

        if self.current_goal and self.current_goal.description == description:
            # Update existing goal
            self.current_goal.status = status
            self.current_goal.updated_at = datetime.now().isoformat()
        else:
            # Create new goal
            self.current_goal = ConversationGoal(
                description=description,
                category=category,
                success_criteria=f"User successfully completes {category} objective",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                status=status
            )

        # Store goal in context manager
        self.context_manager.add_fact("current_goal", description, "planner")
        self.context_manager.add_fact("goal_category", category, "planner")

    def _analyze_with_nlu(self, user_message: str) -> Dict[str, Any]:
        """Analyze user message with NLU."""
        conversation_context = self.context_manager.get_recent_messages(6)
        nlu_result = self.enhanced_nlu.analyze_message(user_message, conversation_context)
        self.context_manager.merge_facts_from_nlu(nlu_result)
        return nlu_result

    def _analyze_intent_continuity(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze intent continuity."""
        conversation_context = self.context_manager.get_recent_messages(6)
        return self.intent_tracker.track_new_intent(nlu_result, conversation_context)

    def _create_fallback_decision(self, user_message: str, nlu_result: Dict[str, Any],
                                  error_msg: str) -> PlannerDecision:
        """Create fallback decision when LLM fails."""

        # Simple pattern-based fallback
        message_lower = user_message.lower() if user_message else ""

        if any(word in message_lower for word in ["buy", "purchase", "want", "need", "laptop", "phone"]):
            return PlannerDecision(
                action="gather_specs",
                specifications_needed=["category", "subcategory", "budget"],
                reasoning=f"Fallback: Detected product interest. {error_msg}",
                user_message="I'd like to help you find the right product. What are you looking for?"
            )
        elif any(word in message_lower for word in ["order", "track", "delivery"]):
            return PlannerDecision(
                action="call_agent",
                agent_type="OrderAgent",
                agent_params={"action": "track"},
                reasoning=f"Fallback: Detected order inquiry. {error_msg}"
            )
        else:
            return PlannerDecision(
                action="clarify",
                reasoning=f"Fallback: Unclear intent. {error_msg}",
                user_message="I'd like to help you, but I need more information about what you're looking for."
            )

    def _handle_unknown_action(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Handle unknown action type."""

        fallback_message = "I'm not sure how to proceed. Could you help me understand what you'd like to do?"
        self.context_manager.add_message("system", fallback_message)

        return {
            "response": fallback_message,
            "status": "unknown_action",
            "action": "clarify",
            "original_decision": decision.action
        }

    def _handle_error(self, error_message: str, context: str) -> Dict[str, Any]:
        """Handle errors gracefully."""
        self.status = PlannerStatus.ERROR

        user_message = "I apologize, but I encountered an issue. Let me try to help you in a different way."
        self.context_manager.add_message("system", user_message)
        self.context_manager.add_fact("last_error", error_message, "system")

        # Reset to ready state for recovery
        self.status = PlannerStatus.READY
        self.gathered_specs = {}
        self.specs_confirmed = False

        return {
            "response": user_message,
            "status": "error",
            "action": "retry",
            "error_context": context
        }

    def get_session_info(self) -> Dict[str, Any]:
        """Get comprehensive session information."""

        current_intent = self.intent_tracker.get_current_intent()
        context_summary = self.context_manager.get_context_summary()

        return {
            "session_id": self.context_manager.session_id,
            "planner_status": self.status.value,
            "current_goal": {
                "description": self.current_goal.description if self.current_goal else None,
                "category": self.current_goal.category if self.current_goal else None,
                "status": self.current_goal.status if self.current_goal else None
            },
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
            "session_active": self.context_manager.session_active
        }

    def end_conversation(self, reason: str = "user_exit") -> Dict[str, Any]:
        """End conversation gracefully."""

        closing_message = self.context_manager.end_session(reason)
        self.status = PlannerStatus.GOAL_ACHIEVED

        if self.current_goal and self.current_goal.status != "completed":
            self.current_goal.status = f"ended_{reason}"
            self.current_goal.updated_at = datetime.now().isoformat()

        return {
            "response": closing_message,
            "status": "conversation_ended",
            "reason": reason,
            "session_summary": self.get_session_info()
        }


def test_intelligent_planner():
    """Test the Intelligent Planner with specification gathering and Discovery Agent."""
    print("🧪 Testing Intelligent Planner with Discovery Agent")
    print("=" * 80)

    planner = IntelligentPlanner("test_discovery_session")

    # Test 1: Start conversation
    print("1️⃣ Starting conversation:")
    start_response = planner.start_conversation()
    print(f"   Status: {start_response['status']}")
    print(f"   Response: {start_response['response'][:80]}...")

    # Test 2: Vague user request - should trigger spec gathering
    print("\n2️⃣ Vague user request (should gather specs):")
    user_message = "I want to buy a laptop"
    print(f"User Message: {user_message}")
    response1 = planner.process_user_message(user_message)
    print(f"   Status: {response1['status']}")
    print(f"   Action: {response1.get('action')}")
    print(f"   Response: {response1['response'][:100]}...")

    # Test 3: User provides some specifications
    print("\n3️⃣ User provides specifications:")
    user_message = "I need it for gaming and my budget is around $1500"
    print(f"User Message: {user_message}")
    response2 = planner.process_user_message(user_message)
    print(f"   Status: {response2['status']}")
    print(f"   Action: {response2.get('action')}")
    if response2.get('specifications_gathered'):
        print(f"   Specs Gathered: {response2['specifications_gathered']}")

    # Test 4: User confirms requirements
    print("\n4️⃣ User confirms requirements:")
    user_message = "Yes, that sounds right"
    print(f"User Message: {user_message}")
    response3 = planner.process_user_message(user_message)
    print(f"   Status: {response3['status']}")
    print(f"   Action: {response3.get('action')}")
    print(f"   Agent Called: {response3.get('agent_type')}")
    if response3.get('agent_result'):
        result = response3['agent_result']
        print(f"   Discovery Mode: {result.get('discovery_mode')}")
        print(f"   Products Found: {result.get('products_found', 0)}")

    # Test 5: Specific user - should go direct to agent
    print("\n5️⃣ Specific user request (should skip to agent):")
    planner2 = IntelligentPlanner("test_specific_session")
    planner2.start_conversation()

    user_message = "Show me gaming laptops with RTX graphics under $1500"
    print(f"User Message: {user_message}")
    response4 = planner2.process_user_message(user_message)
    print(f"   Status: {response4['status']}")
    print(f"   Action: {response4.get('action')}")
    print(f"   Agent Called: {response4.get('agent_type')}")

    # Test 6: Order tracking request
    print("\n6️⃣ Order tracking request:")
    user_message = "Where is my order 12345?"
    print(f"User Message: {user_message}")
    response5 = planner2.process_user_message(user_message)
    print(f"   Status: {response5['status']}")
    print(f"   Action: {response5.get('action')}")
    print(f"   Agent Called: {response5.get('agent_type')}")

    # Test 7: Return request without order ID
    print("\n7️⃣ Return request (no order ID):")
    user_message = "I want to return something"
    print(f"User Message: {user_message}")
    response6 = planner2.process_user_message(user_message)
    print(f"   Status: {response6['status']}")
    print(f"   Agent Called: {response6.get('agent_type')}")
    if response6.get('agent_result'):
        print(f"   Shows Order Selection: {response6['agent_result'].get('requires_selection', False)}")

    # Test 8: Session information
    print("\n8️⃣ Session information:")
    session_info = planner.get_session_info()
    print(f"   Session ID: {session_info['session_id']}")
    print(f"   Planner Status: {session_info['planner_status']}")
    print(f"   Conversation Turns: {session_info['conversation_turns']}")
    print(f"   Agent Calls: {session_info['agent_calls_made']}")
    print(f"   Specs Confirmed: {session_info['specification_gathering']['confirmed']}")

    print("\n" + "=" * 80)
    print("✅ Intelligent Planner Tests Complete!")
    print("\nKey Features Demonstrated:")
    print("📝 Intelligent specification gathering")
    print("✅ Requirement confirmation before agent calls")
    print("🔍 Dual-mode Discovery Agent integration")
    print("📦 Smart order and return processing")
    print("🎯 Goal-oriented conversation management")
    print("🔄 Adaptive flow based on user specificity")


if __name__ == "__main__":
    test_intelligent_planner()