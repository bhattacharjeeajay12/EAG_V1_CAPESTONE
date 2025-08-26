# core/intelligent_planner.py
"""
Intelligent Planner - LLM-Driven Goal-Oriented Conversational AI

Purpose: Dynamic conversational orchestrator that uses LLM intelligence to:
- Set and track natural language goals
- Dynamically select and call agents based on context
- Continuously validate goal achievement
- Re-plan when user scope changes
- Provide truly adaptive conversation management

Key Features:
- No fixed templates - pure LLM-driven decisions
- Goal-oriented validation after every agent call
- Dynamic re-planning with user explanation
- Intelligent agent orchestration
- Natural conversation flow management
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
    EXECUTING_AGENT = "executing_agent"
    GOAL_ACHIEVED = "goal_achieved"
    RE_PLANNING = "re_planning"
    ERROR = "error"


@dataclass
class ConversationGoal:
    """Represents the current conversation goal."""
    description: str
    category: str  # "buy", "return", "browse", "order_tracking", "recommend"
    success_criteria: str
    created_at: str
    updated_at: str
    status: str = "active"


@dataclass
class PlannerDecision:
    """Represents a decision made by the planner LLM."""
    action: str  # "call_agent", "goal_achieved", "re_plan", "clarify"
    agent_type: Optional[str] = None
    agent_params: Optional[Dict[str, Any]] = None
    goal_status: str = "in_progress"  # "in_progress", "achieved", "needs_replanning"
    reasoning: str = ""
    user_message: Optional[str] = None
    confidence: float = 0.8


class IntelligentPlanner:
    """
    LLM-driven intelligent conversation planner that adapts dynamically
    to user needs without fixed templates.
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

    def start_conversation(self) -> Dict[str, Any]:
        """Start a new intelligent conversation."""
        welcome_message = (
            "Hi! I'm your intelligent assistant. I can help you with:\n"
            "🛒 Finding and buying products\n"
            "📦 Tracking your orders\n"
            "💡 Getting recommendations\n"
            "↩️ Returns and exchanges\n"
            "🔍 Just browsing and exploring\n\n"
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
        Main processing pipeline - LLM-driven intelligent orchestration.

        Args:
            user_message: User's input message

        Returns:
            Complete response with actions taken
        """
        try:
            # Add user message to context
            self.context_manager.add_message("user", user_message)
            self.conversation_turns += 1

            # Step 1: Analyze user message with NLU
            nlu_result = self._analyze_with_nlu(user_message)

            # Step 2: Update intent tracking
            intent_result = self._analyze_intent_continuity(nlu_result)

            # Step 3: LLM-driven planning decision
            self.status = PlannerStatus.ANALYZING
            planner_decision = self._make_planning_decision(user_message, nlu_result, intent_result)

            # Step 4: Execute the decision
            return self._execute_planner_decision(planner_decision)

        except Exception as e:
            return self._handle_error(f"Processing error: {str(e)}", user_message)

    def _make_planning_decision(self, user_message: str, nlu_result: Dict[str, Any],
                                intent_result: Dict[str, Any]) -> PlannerDecision:
        """
        Use LLM to make intelligent planning decisions.

        Args:
            user_message: Original user message
            nlu_result: NLU analysis result
            intent_result: Intent tracking result

        Returns:
            PlannerDecision object with next actions
        """
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
Total Facts Available: {context_summary.get('total_facts', 0)}
Agent Calls Made: {self.agent_calls_count}
Conversation Turns: {self.conversation_turns}

AVAILABLE AGENTS:
- BuyAgent: Search products, get recommendations, handle purchases
- RecommendAgent: Provide personalized product suggestions  
- OrderAgent: Track orders, check status, handle order queries
- ReturnAgent: Process returns, exchanges, refunds

YOUR TASK:
Analyze the situation and decide the next best action. Consider:
1. What does the user want to accomplish overall?
2. Do we have enough information to help them?
3. Which agent (if any) should be called?
4. Is the user's goal achieved?
5. Has the user changed direction (re-planning needed)?

DECISION TYPES:
- call_agent: Call a specific agent to help user
- goal_achieved: User's objective is complete, wrap up
- re_plan: User changed direction, need new approach
- clarify: Need more information from user

Return JSON:
{{
  "action": "call_agent|goal_achieved|re_plan|clarify",
  "agent_type": "BuyAgent|RecommendAgent|OrderAgent|ReturnAgent|null",
  "agent_params": {{"key": "value"}},
  "goal_status": "in_progress|achieved|needs_replanning",
  "goal_description": "natural_language_goal_description",
  "goal_category": "buy|recommend|order|return|browse",
  "reasoning": "why_this_decision_makes_sense",
  "user_message": "what_to_tell_the_user_or_null",
  "confidence": 0.0-1.0
}}

Be intelligent, adaptive, and focused on actually solving the user's needs.
"""
        return prompt

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
                confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.8))))
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

    def _execute_planner_decision(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute the decision made by the planner LLM."""

        if decision.action == "call_agent":
            return self._execute_agent_call(decision)

        elif decision.action == "goal_achieved":
            return self._handle_goal_achieved(decision)

        elif decision.action == "re_plan":
            return self._handle_re_planning(decision)

        elif decision.action == "clarify":
            return self._handle_clarification(decision)

        else:
            return self._handle_unknown_action(decision)

    def _execute_agent_call(self, decision: PlannerDecision) -> Dict[str, Any]:
        """Execute agent call and check goal achievement."""
        self.status = PlannerStatus.EXECUTING_AGENT

        try:
            # Call the appropriate mock agent
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

            # Check if goal is achieved after agent call
            goal_check = self._check_goal_achievement()

            response = {
                "response": agent_result.get("user_message", "Agent completed successfully."),
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
            else:
                self.status = PlannerStatus.READY

            return response

        except Exception as e:
            return self._handle_error(f"Agent execution error: {str(e)}", "agent_call")

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

        if any(word in message_lower for word in ["buy", "purchase", "want", "need"]):
            return PlannerDecision(
                action="call_agent",
                agent_type="BuyAgent",
                agent_params={"query": user_message},
                reasoning=f"Fallback: Detected purchase intent. {error_msg}",
                user_message="I'll help you find what you're looking for."
            )
        elif any(word in message_lower for word in ["recommend", "suggest", "best"]):
            return PlannerDecision(
                action="call_agent",
                agent_type="RecommendAgent",
                agent_params={"category": "general"},
                reasoning=f"Fallback: Detected recommendation request. {error_msg}"
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
    """Test the Intelligent Planner with various scenarios."""
    print("🧪 Testing Intelligent Planner")
    print("=" * 70)

    planner = IntelligentPlanner("test_intelligent_session")

    # Test 1: Start conversation
    print("1️⃣ Starting intelligent conversation:")
    start_response = planner.start_conversation()
    print(f"   Status: {start_response['status']}")
    print(f"   Response: {start_response['response'][:80]}...")

    # Test 2: Happy path - Buy request
    print("\n2️⃣ User wants to buy a laptop:")
    response1 = planner.process_user_message("I want to buy a gaming laptop for under $1500")
    print(f"   Status: {response1['status']}")
    print(f"   Action: {response1.get('action')}")
    print(f"   Agent Called: {response1.get('agent_type', 'None')}")
    print(f"   Goal Achieved: {response1.get('goal_achieved', False)}")
    print(f"   Response: {response1['response'][:100]}...")

    # Test 3: Follow up with more info
    print("\n3️⃣ User provides more details:")
    response2 = planner.process_user_message("I prefer NVIDIA graphics and good battery life")
    print(f"   Status: {response2['status']}")
    print(f"   Action: {response2.get('action')}")
    print(f"   Agent Called: {response2.get('agent_type', 'None')}")
    print(f"   Goal Achieved: {response2.get('goal_achieved', False)}")

    # Test 4: Scope change - user switches to return
    print("\n4️⃣ User suddenly switches to return:")
    response3 = planner.process_user_message("Actually, I need to return a defective phone I bought last week")
    print(f"   Status: {response3['status']}")
    print(f"   Action: {response3.get('action')}")
    print(f"   Agent Called: {response3.get('agent_type', 'None')}")
    print(f"   Re-planning: {'Yes' if response3.get('action') == 're_plan' else 'No'}")
    print(f"   Response: {response3['response'][:100]}...")

    # Test 5: Goal completion scenario
    print("\n5️⃣ User completes return process:")
    response4 = planner.process_user_message("Yes, please process the return for order #12345")
    print(f"   Status: {response4['status']}")
    print(f"   Action: {response4.get('action')}")
    print(f"   Agent Called: {response4.get('agent_type', 'None')}")
    print(f"   Goal Achieved: {response4.get('goal_achieved', False)}")
    print(f"   Session Complete: {response4.get('session_complete', False)}")

    # Test 6: Complex journey - recommendations
    print("\n6️⃣ New user - wants recommendations:")
    planner2 = IntelligentPlanner("test_recommend_session")
    planner2.start_conversation()

    rec_response1 = planner2.process_user_message("What's the best smartphone for photography?")
    print(f"   Status: {rec_response1['status']}")
    print(f"   Agent Called: {rec_response1.get('agent_type', 'None')}")

    rec_response2 = planner2.process_user_message("I also want good battery life and under $800")
    print(f"   Follow-up Status: {rec_response2['status']}")
    print(f"   Goal Achieved: {rec_response2.get('goal_achieved', False)}")

    # Test 7: Session information
    print("\n7️⃣ Session information:")
    session_info = planner.get_session_info()
    print(f"   Session ID: {session_info['session_id']}")
    print(f"   Planner Status: {session_info['planner_status']}")
    print(f"   Current Goal: {session_info['current_goal']['description']}")
    print(f"   Conversation Turns: {session_info['conversation_turns']}")
    print(f"   Agent Calls Made: {session_info['agent_calls_made']}")
    print(f"   Total Facts: {session_info['context_summary']['total_facts']}")

    # Test 8: Error handling
    print("\n8️⃣ Testing error recovery:")
    error_response = planner.process_user_message("")
    print(f"   Status: {error_response['status']}")
    print(f"   Error handled gracefully: {error_response['status'] == 'error'}")

    print("\n" + "=" * 70)
    print("✅ Intelligent Planner Tests Complete!")
    print("\nKey Features Demonstrated:")
    print("🎯 LLM-driven decision making")
    print("🔄 Dynamic agent orchestration")
    print("🎪 Goal-oriented conversation management")
    print("🔀 Smart re-planning and scope changes")
    print("⚡ Intelligent error recovery")


if __name__ == "__main__":
    test_intelligent_planner()