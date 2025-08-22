import os, json, re
from typing import List, Dict, Any, Optional, Tuple
from prompts import buy_prompt

import google.generativeai as genai
from perceptions.buy_perception import extract_buy_details, BuyDetails
from memory import SessionMemory
from utils.logger import get_logger, log_decision


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


def _load_buy_agent_prompt() -> str:
    try:
        # Import the prompt directly from the Python module
        from prompts.buy_prompt import BUY_AGENT_PROMPT
        return BUY_AGENT_PROMPT
    except Exception as e:
        print(f"[WARN] Could not load buy agent prompt from prompts.buy_prompt: {e}")
        return "You are a helpful e-commerce buy agent. Respond conversationally and then output a JSON state as specified."


def _merge_perceptions(base: Dict[str, Any], latest: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
    # Simple merge rules: last mention wins; merge specifications dict deeply
    for k, v in latest.items():
        if v in (None, "", {}):
            continue
        if k == "specifications":
            spec = dict(merged.get("specifications") or {})
            spec.update(v or {})
            merged["specifications"] = spec
        else:
            merged[k] = v
    return merged


def _ready_check(state: Dict[str, Any]) -> bool:
    if not state.get("product_name"):
        return False
    specs = state.get("specifications") or {}
    has_specs = isinstance(specs, dict) and len(specs) >= 1
    quantity = state.get("quantity", 1)
    budget = state.get("budget")
    return bool(quantity) and (has_specs or budget)


def _extract_last_json(s: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Extract the last JSON object from text, handling incomplete JSON gracefully.
    When incomplete JSON is detected, it attempts to reconstruct a valid state object
    by extracting as much information as possible from the partial JSON.
    """
    # Find last JSON object in the text
    last_open = s.rfind("{")
    if last_open == -1:
        return None

    # Extract text before the JSON part
    prefix = s[:last_open].rstrip()
    json_text = s[last_open:]

    # Try to find a complete JSON object
    depth = 0
    end_index = None
    for i, ch in enumerate(json_text):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end_index = i + 1
                break

    # Create baseline state with default values
    base_state = {
        "product_name": None,
        "specifications": {},
        "quantity": 1,
        "budget": None,
        "category": None,
        "conversation_state": "gathering_requirements",
        "ready_for_tool_call": False,
        "conversation_outcome": "undecided"
    }

    # If we have complete JSON, parse it normally
    if end_index is not None:
        candidate = json_text[:end_index]
        try:
            obj = json.loads(candidate)
            return prefix, obj
        except Exception as e:
            print(f"\n[WARN] Failed to parse JSON response: {e}")
    else:
        print("\n[WARN] Incomplete JSON response detected. Attempting to recover partial state.")

    # For incomplete JSON, try to extract as much information as possible
    # Extract product_name
    product_match = re.search(r'"product_name"\s*:\s*"([^"]+)"', json_text)
    if product_match:
        base_state["product_name"] = product_match.group(1)

    # Extract specifications if they exist
    specs_match = re.search(r'"specifications"\s*:\s*{([^{}]*)}', json_text)
    if specs_match:
        specs_text = specs_match.group(1)
        # Parse individual specs
        spec_pattern = r'"([^"]+)"\s*:\s*"?([^",}]+)"?'
        for spec_match in re.finditer(spec_pattern, specs_text):
            key, value = spec_match.groups()
            base_state["specifications"][key] = value.strip('"')

    # Extract quantity
    quantity_match = re.search(r'"quantity"\s*:\s*(\d+)', json_text)
    if quantity_match:
        try:
            base_state["quantity"] = int(quantity_match.group(1))
        except ValueError:
            pass

    # Extract budget if present
    budget_match = re.search(r'"budget"\s*:\s*"?([^",}]+)"?', json_text)
    if budget_match:
        base_state["budget"] = budget_match.group(1).strip('"')

    # Extract category if present
    category_match = re.search(r'"category"\s*:\s*"?([^",}]+)"?', json_text)
    if category_match:
        base_state["category"] = category_match.group(1).strip('"')

    # Extract conversation_state if present
    state_match = re.search(r'"conversation_state"\s*:\s*"([^"]+)"', json_text)
    if state_match:
        base_state["conversation_state"] = state_match.group(1)

    # Extract ready_for_tool_call if present
    tool_call_match = re.search(r'"ready_for_tool_call"\s*:\s*(true|false)', json_text)
    if tool_call_match:
        base_state["ready_for_tool_call"] = tool_call_match.group(1) == "true"

    # Extract conversation_outcome if present
    outcome_match = re.search(r'"conversation_outcome"\s*:\s*"([^"]+)"', json_text)
    if outcome_match:
        base_state["conversation_outcome"] = outcome_match.group(1)

    return prefix, base_state


class BuyAgent:
    def __init__(self, verbose=True):
        # Conversation state
        self.chat_history: List[Dict[str, str]] = []
        self.perceptions_history: List[Dict[str, Any]] = []
        self.perceptions: Dict[str, Any] = {"specifications": {}, "quantity": 1}
        self.conversation_state: str = "initial_inquiry"

        self.verbose = verbose
        self.logger = get_logger("buy")
        self.memory = SessionMemory(agent_name="buy")
        self._last_state: Dict[str, Any] = {"conversation_state": "initial_inquiry"}

        # LLM setup
        self.prompt_text: str = _load_buy_agent_prompt()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.model = None
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                print("[WARN] Failed to initialize Gemini model:", e)
                self.model = None

    # ---------- Session & Memory Management ----------
    def new_session(self, label: Optional[str] = None):
        """Start a new conversation session and reset state using shared memory manager."""
        self.chat_history = []
        self.perceptions_history = []
        self.perceptions = {"specifications": {}, "quantity": 1}
        self.conversation_state = "initial_inquiry"
        self._last_state = {"conversation_state": "initial_inquiry"}
        self.memory.new_session(label=label, config={"model": self.model_name})
        log_decision(
            self.logger,
            agent="buy",
            event="new_session",
            why="start conversation",
            data={"label": label},
            session_id=self.memory.session_id,
        )

    def initialize_for_testing(self, test_data: Dict[str, Any]) -> None:
        """
        Initialize the agent with a predefined state for testing.

        Args:
            test_data: Dictionary containing any of:
                - chat_history: List of message objects with role and content
                - perceptions: Consolidated perceptions state
                - conversation_state: Current stage in the conversation flow
        """
        # Set chat history if provided
        if "chat_history" in test_data and test_data["chat_history"]:
            self.chat_history = test_data["chat_history"]

        # Set consolidated perceptions if provided
        if "perceptions" in test_data and test_data["perceptions"]:
            self.perceptions = test_data["perceptions"]

        # Set conversation state if provided
        if "conversation_state" in test_data and test_data["conversation_state"]:
            self.conversation_state = test_data["conversation_state"]
            self._last_state["conversation_state"] = test_data["conversation_state"]

        # Optionally set perceptions_history if testing specific history integration
        if "perceptions_history" in test_data and test_data["perceptions_history"]:
            self.perceptions_history = test_data["perceptions_history"]

        # Log the initialization
        log_decision(
            self.logger,
            agent="buy",
            event="test_initialization",
            why="setting up test state",
            data={"test_scenario": test_data.get("name", "unnamed"), "conversation_state": self.conversation_state},
            session_id=self.memory.session_id
        )

    # ---------- Payload for LLM ----------
    def _build_input_payload(self, latest_message: str, latest_perception: Dict[str, Any]) -> Dict[str, Any]:
        """Build a payload for the LLM that includes the conversation state."""
        return {
            "chat_history": self.chat_history,
            "perceptions": self.perceptions,
            "latest_message": latest_message,
            "conversation_state": self.conversation_state
        }

    def _fallback_response(self, latest_message: str) -> Tuple[str, Dict[str, Any]]:
        # Craft a simple conversational reply based on what is missing
        missing = []
        if not self.perceptions.get("product_name"):
            missing.append("the product name")
        specs = self.perceptions.get("specifications") or {}
        if not specs:
            missing.append("key specs like brand, color, or size")
        if not self.perceptions.get("budget"):
            missing.append("your budget or price range (optional)")

        # Determine conversation state based on what we know
        if not self.perceptions.get("product_name"):
            conversation_state = "initial_inquiry"
        elif missing:
            conversation_state = "gathering_requirements"
        elif _ready_check(self.perceptions):
            conversation_state = "suggesting_products"
        else:
            conversation_state = self.conversation_state

        # Update instance conversation state
        self.conversation_state = conversation_state

        # Craft appropriate response based on state
        if missing:
            # Only ask about the first missing item
            first_missing = missing[0]
            reply = (
                f"Thanks! I captured your request. Could you share {first_missing}? "
                f"This will help me find the best options."
            )
        else:
            reply = (
                "Great! I have enough details to search for options. "
                "Would you like me to pull up some matches now?"
            )

        state = {
            "product_name": self.perceptions.get("product_name"),
            "specifications": self.perceptions.get("specifications") or {},
            "quantity": self.perceptions.get("quantity", 1),
            "budget": self.perceptions.get("budget"),
            "category": self.perceptions.get("category"),
            "conversation_state": conversation_state,
            "ready_for_tool_call": _ready_check(self.perceptions),
            "conversation_outcome": "undecided",
        }
        return reply, state

    def _llm_response(self, payload: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
        if not self.model:
            return None
        try:
            input_block = json.dumps(payload, ensure_ascii=False, indent=2)
            full_prompt = (
                    self.prompt_text
                    + "\n\nINPUT START\n"
                    + input_block
                    + "\nINPUT END\n\nPlease produce your response as specified above."
            )
            resp = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="text/plain"
                ),
            )
            text = (resp.text or "").strip()
            extracted = _extract_last_json(text)
            if not extracted:
                return None
            reply_text, state = extracted
            return reply_text.strip(), state
        except Exception as e:
            print("[WARN] LLM generation failed:", e)
            return None

    def delegate_recommendation(self, recommender, query: str):
        """Delegate a recommendation request to RecommendationAgent."""
        return recommender.handle(query)

    def place_order(self, order_agent, payload: Any):
        """Trigger an order via OrderAgent using the Buy agent context."""
        return order_agent.handle(payload, is_buy_agent=True)

    def handle(self, query: str):
        """
        Process a user query in the context of the current conversation.

        This method:
        1. Adds the user message to chat history
        2. Extracts perceptions from the query
        3. Updates the consolidated perceptions
        4. Gets a response from the LLM (or fallback)
        5. Updates the conversation state
        6. Adds the agent's response to chat history
        7. Saves the conversation state

        Returns:
            The extracted perceptions from the query
        """
        print("\n" + "-" * 70)
        print("[BuyAgent] Processing buy query...")
        print("-" * 70)

        # Update chat with user message
        self.chat_history.append({"role": "user", "content": query})

        # Extract perceptions
        result = extract_buy_details(query)
        latest_perception = result.model_dump()
        self.perceptions_history.append({"message": query, "perception": latest_perception})
        # Merge cumulative perceptions
        self.perceptions = _merge_perceptions(self.perceptions, latest_perception)

        # Build payload for the agent prompt
        payload = self._build_input_payload(query, latest_perception)

        # Capture logs to display them in a separate section
        log_info = []

        # Get agent response via LLM, fallback if needed
        out = self._llm_response(payload)
        if out is None:
            log_info.append("Using fallback response (LLM unavailable or parse failed)")
            log_decision(self.logger, agent="buy", event="decision", why="fallback",
                         data={"reason": "llm_unavailable_or_parse_failed"}, session_id=self.memory.session_id)
            reply_text, state = self._fallback_response(query)
        else:
            log_info.append(f"Using LLM response from {self.model_name}")
            log_decision(self.logger, agent="buy", event="decision", why="llm", data={"model": self.model_name},
                         session_id=self.memory.session_id)
            reply_text, state = out

        # Update conversation state based on LLM response
        if "conversation_state" in state:
            self.conversation_state = state["conversation_state"]
            log_decision(self.logger, agent="buy", event="state_transition",
                         why="conversation flow progression",
                         data={"from": self._last_state.get("conversation_state", "unknown"),
                               "to": self.conversation_state},
                         session_id=self.memory.session_id)

        # Print and record agent reply with better formatting
        print("\n" + "=" * 50)
        print(f"Agent: {reply_text}")
        print("-" * 50)
        print(f"[BuyAgent] Current State: {self.conversation_state}")

        # Filter out empty and None values for cleaner display
        filtered_state = {k: v for k, v in state.items() if v is not None and v != {} and v != []}

        if filtered_state:
            print("[BuyAgent] Details:")
            for key, value in filtered_state.items():
                if isinstance(value, dict) and value:  # Only show non-empty dictionaries
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, list) and value:  # Handle lists
                    print(f"  {key}:")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"  {key}: {value}")
        else:
            print("[BuyAgent] Details: No details available")

        print("=" * 50 + "\n")
        self.chat_history.append({"role": "agent", "content": reply_text})

        # Make sure conversation_state is included in the last_state
        self._last_state = state
        if "conversation_state" not in self._last_state:
            self._last_state["conversation_state"] = self.conversation_state

        # Save memory with chat history in chronological order (oldest first)
        self.memory.save(
            chat_history=self.chat_history,
            perceptions_history=self.perceptions_history,
            perceptions=self.perceptions,
            last_agent_state=self._last_state,
            config={"model": self.model_name},
        )

        return result


def run_conversation_flow_examples(agent: BuyAgent) -> None:
    """
    Run test scenarios with predefined conversation flows.
    These scenarios include both user and agent messages to test
    how the agent handles continuing a conversation with context.
    """
    scenarios = [
        # Scenario 1: Basic conversation continuation
        {
            "name": "Continue laptop conversation",
            "chat_history": [
                {"role": "user", "content": "I want to buy a laptop."},
                {"role": "agent",
                 "content": "Great! I can help you find a laptop. Do you have any specific requirements like brand, screen size, or budget?"}
            ],
            "perceptions": {
                "product_name": "laptop",
                "specifications": {},
                "quantity": 1,
                "category": "electronics"
            },
            "conversation_state": "gathering_requirements",
            "current_query": "I need three laptops actually."
        },

        # Scenario 2: Adding specifications to existing product
        {
            "name": "Add specifications to laptop",
            "chat_history": [
                {"role": "user", "content": "I want to buy a laptop."},
                {"role": "agent",
                 "content": "Great! I can help you find a laptop. Do you have any specific requirements like brand, screen size, or budget?"},
                {"role": "user", "content": "I need three laptops actually."},
                {"role": "agent",
                 "content": "Sure, I can help you find three laptops. Do you need them all with the same specifications? And do you have any preferences for brand, size, or budget?"}
            ],
            "perceptions": {
                "product_name": "laptop",
                "specifications": {},
                "quantity": 3,
                "category": "electronics"
            },
            "conversation_state": "gathering_requirements",
            "current_query": "I want Dell laptops with at least 16GB RAM."
        }
    ]

    print("\n" + "=" * 30 + " CONVERSATION FLOW SCENARIOS " + "=" * 30)
    for i, scenario in enumerate(scenarios, start=1):
        print(f"\n{'=' * 20} Scenario {i}: {scenario['name']} {'=' * 20}")

        # Start a new session
        agent.new_session(label=f"conversation-flow-{i}")

        # Initialize with test data
        agent.initialize_for_testing(scenario)

        # Print the conversation so far with better formatting
        print("\n" + "-" * 30 + " CONVERSATION HISTORY " + "-" * 30)
        for msg in agent.chat_history:
            role = msg['role'].capitalize()
            if role == "User":
                print(f"\n{role}: {msg['content']}")
            else:
                print(f"\n{role}:\n{msg['content']}")

        # Print initial conversation state
        print("\n" + "-" * 30 + " INITIAL STATE " + "-" * 30)
        print(f"Conversation state: {agent.conversation_state}")

        # Process the current query
        query = scenario["current_query"]
        print(f"\nCurrent user query: {query}")
        result = agent.handle(query)

        # Show the result with better formatting
        print("\n" + "=" * 30 + " RESULTS " + "=" * 30)

        # Extracted perceptions - only show non-empty values
        perceptions_data = {k: v for k, v in result.model_dump().items() if v is not None and v != {} and v != []}
        if perceptions_data:
            print("Extracted perceptions:")
            for key, value in perceptions_data.items():
                if isinstance(value, dict) and value:
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, list) and value:
                    print(f"  {key}:")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"  {key}: {value}")
        else:
            print("Extracted perceptions: None")

        # Final perceptions - only show non-empty values
        perceptions_state = {k: v for k, v in agent.perceptions.items() if v is not None and v != {} and v != []}
        if perceptions_state:
            print("\nFinal perceptions state:")
            for key, value in perceptions_state.items():
                if isinstance(value, dict) and value:
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                elif isinstance(value, list) and value:
                    print(f"  {key}:")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"  {key}: {value}")
        else:
            print("\nFinal perceptions state: Empty")

        print(f"\nFinal conversation state: {agent.conversation_state}")
        print("=" * 70)

    print("=== Conversation flow examples complete ===\n")


def interactive_loop(agent: BuyAgent) -> None:
    """Start an interactive session for manual testing."""
    print("\n" + "=" * 30 + " INTERACTIVE MODE " + "=" * 30)
    print("Enter your purchase queries. Type 'exit' to quit.")
    session_started = False
    while True:
        try:
            print("\n" + "-" * 70)
            user_in = input("You: ").strip()
            print("-" * 70)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if user_in.lower() in {"exit", "quit", "q"}:
            print("\nGoodbye! Thanks for shopping with us.")
            break
        if not user_in:
            continue
        if not session_started:
            agent.new_session(label="interactive")
            session_started = True
        agent.handle(user_in)


if __name__ == "__main__":
    # Create agent with verbose output enabled
    agent = BuyAgent(verbose=True)

    # Choose which tests to run
    run_conversation_examples = False
    run_interactive = True

    # 2) Run the conversation flow scenarios with context
    if run_conversation_examples:
        run_conversation_flow_examples(agent)

    # 3) Start interactive input loop
    if run_interactive:
        # For interactive mode, enable verbose mode for better visibility
        agent = BuyAgent(verbose=True)
        interactive_loop(agent)
