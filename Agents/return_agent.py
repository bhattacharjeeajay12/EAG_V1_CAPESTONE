import os, json, re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

import google.generativeai as genai
from return_perception import extract_return_details
from memory import SessionMemory


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


def _load_return_agent_prompt() -> str:
    path = _project_path("Prompts", "return_prompt.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Try to extract triple-quoted string assigned to RETURN_AGENT_PROMPT
        m = re.search(r'RETURN_AGENT_PROMPT\s*=\s*"""(.*?)"""', content, re.S)
        if m:
            return m.group(1).strip()
        return content.strip()
    except Exception as e:
        print(f"[WARN] Could not load return agent prompt from {path}: {e}")
        return "You are a helpful e-commerce return agent. Respond conversationally and then output a JSON state as specified."


def _merge_perceptions(base: Dict[str, Any], latest: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
    # Simple merge rules: last mention wins for most fields
    for k, v in latest.items():
        if v is None or v == "" or v == {}:
            continue
        merged[k] = v
    return merged


def _ready_for_eligibility_check(state: Dict[str, Any]) -> bool:
    # Check if we have enough information to check return eligibility
    return (state.get("product_id") or state.get("product_name")) and state.get("purchase_date")


def _extract_last_json(s: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    # Find last JSON object in the text and return (text_before_json, json_obj)
    last_open = s.rfind("{")
    if last_open == -1:
        return None
    json_text = s[last_open:]
    # Trim trailing non-json characters (e.g., accidental markdown)
    # Try to find a matching closing brace by scanning
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
    if end_index is None:
        return None
    candidate = json_text[:end_index]
    try:
        obj = json.loads(candidate)
        prefix = s[:last_open].rstrip()
        return prefix, obj
    except Exception:
        return None


class ReturnAgent:
    def __init__(self):
        # Conversation state (store oldest-first for convenience internally)
        self.chat_history: List[Dict[str, str]] = []  # {role: 'user'|'agent', content: str}
        self.perceptions_history: List[Dict[str, Any]] = []  # list of {message, perception}
        self.perceptions: Dict[str, Any] = {
            "has_packaging": True,
            "has_receipt": False,
            "image_provided": False
        }

        # Shared session memory manager (reusable across agents)
        self.memory = SessionMemory(agent_name="return")
        self._last_state: Dict[str, Any] = {}

        # LLM setup
        self.prompt_text: str = _load_return_agent_prompt()
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
        # Initialize chat_history and perceptions_history as empty lists
        # We'll insert new messages at position 0 to maintain newest-first internally
        self.chat_history = []
        self.perceptions_history = []
        self.perceptions = {
            "has_packaging": True,
            "has_receipt": False,
            "image_provided": False
        }
        self._last_state = {}
        # Initialize memory session and persist an initial shell
        self.memory.new_session(label=label, config={"model": self.model_name})

    # ---------- Payload for LLM ----------
    def _build_input_payload(self, latest_message: str, latest_perception: Dict[str, Any]) -> Dict[str, Any]:
        # Reverse the chat_history and perceptions_history to get chronological order (oldest first)
        # Since we're now inserting at position 0, we need to reverse for the LLM
        return {
            "chat_history": list(reversed(self.chat_history)),
            "perceptions_history": list(reversed(self.perceptions_history)),
            "perceptions": self.perceptions,
            "latest_message": latest_message,
            "latest_perception": latest_perception,
        }

    def _fallback_response(self, latest_message: str) -> Tuple[str, Dict[str, Any]]:
        # Craft a simple conversational reply based on what is missing
        missing = []
        if not self.perceptions.get("product_name") and not self.perceptions.get("product_id"):
            missing.append("the product you want to return")
        if not self.perceptions.get("order_id"):
            missing.append("your order ID")
        if not self.perceptions.get("purchase_date"):
            missing.append("when you purchased the item")
        if not self.perceptions.get("return_reason"):
            missing.append("why you want to return it")

        if missing:
            ask = "; ".join(missing)
            reply = (
                f"I'd be happy to help with your return request. Could you please provide {ask}? "
                f"This will help me check if your return is eligible."
            )
        else:
            reply = (
                "Thank you for providing the details. I'll check if your return is eligible. "
                "Could you also send a photo of the product so we can verify its condition?"
            )

        state = {
            "product_id": self.perceptions.get("product_id"),
            "product_name": self.perceptions.get("product_name"),
            "order_id": self.perceptions.get("order_id"),
            "purchase_date": self.perceptions.get("purchase_date"),
            "return_reason": self.perceptions.get("return_reason"),
            "condition": self.perceptions.get("condition"),
            "has_packaging": self.perceptions.get("has_packaging", True),
            "has_receipt": self.perceptions.get("has_receipt", False),
            "image_provided": self.perceptions.get("image_provided", False),
            "image_quality": self.perceptions.get("image_quality"),
            "eligibility_checked": False,
            "is_eligible": False,
            "return_window_open": False,
            "customer_exception_granted": False,
            "image_verified": False,
            "return_status": "pending"
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

    def _check_eligibility(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Checks return eligibility based on product information and purchase date.
        This is a simplified example - in a real system, this would query your database.
        """
        # For demonstration purposes only - in a real system, you'd query your actual database
        product_id = state.get("product_id", "unknown")
        product_name = state.get("product_name", "unknown")
        purchase_date_str = state.get("purchase_date", "")

        # Parse purchase date - this is simplistic, real code would handle various formats
        try:
            # Try to parse date in format YYYY-MM-DD
            purchase_date = datetime.strptime(purchase_date_str, "%Y-%m-%d")
        except ValueError:
            try:
                # Try to parse date in format MM/DD/YYYY
                purchase_date = datetime.strptime(purchase_date_str, "%m/%d/%Y")
            except ValueError:
                # Default to 20 days ago if we can't parse the date
                purchase_date = datetime.now() - timedelta(days=20)

        # Calculate days since purchase
        days_since_purchase = (datetime.now() - purchase_date).days

        # Mock product lookup - you'd replace this with database query
        return_window = 15  # Default return window of 15 days

        # In a real implementation, you would look up the actual return window from product data
        # For example:
        # product_data = database.get_product(product_id)
        # return_window = product_data.return_window

        result = {
            "eligibility_checked": True,
            "days_since_purchase": days_since_purchase,
            "return_window": return_window
        }

        if days_since_purchase <= return_window:
            # Return is within window
            result["is_eligible"] = True
            result["return_window_open"] = True
        else:
            # Return window has passed
            result["is_eligible"] = False
            result["return_window_open"] = False

            # Mock customer history check - in a real system, this would query customer database
            # For demonstration, we'll randomly grant exceptions based on product ID
            # In reality, this would be based on customer purchase history, loyalty, etc.
            exception_granted = hash(product_id) % 3 == 0  # Simple pseudo-random decision
            result["customer_exception_granted"] = exception_granted
            if exception_granted:
                result["is_eligible"] = True

        return result

    def handle(self, query: str):
        print("[ReturnAgent] Processing return query...")
        # Update chat with user message
        self.chat_history.append({"role": "user", "content": query})

        # Extract perceptions
        result = extract_return_details(query)
        latest_perception = result.model_dump()
        self.perceptions_history.append({"message": query, "perception": latest_perception})
        # Merge cumulative perceptions
        self.perceptions = _merge_perceptions(self.perceptions, latest_perception)

        # Check if we have enough info to check eligibility
        if _ready_for_eligibility_check(self.perceptions) and not self.perceptions.get("eligibility_checked"):
            eligibility_result = self._check_eligibility(self.perceptions)
            self.perceptions.update(eligibility_result)

        # Build payload for the agent prompt
        payload = self._build_input_payload(query, latest_perception)

        # Get agent response via LLM, fallback if needed
        out = self._llm_response(payload)
        if out is None:
            reply_text, state = self._fallback_response(query)
        else:
            reply_text, state = out

        # Print and record agent reply
        print(f"Agent: {reply_text}")
        print("[ReturnAgent] State:", state)
        self.chat_history.append({"role": "agent", "content": reply_text})
        # Cache last state and persist session memory
        self._last_state = state
        # Save memory with chat history in chronological order (oldest first)
        # No need to reverse as we're already storing it in chronological order
        self.memory.save(
            chat_history=self.chat_history,
            perceptions_history=self.perceptions_history,
            perceptions=self.perceptions,
            last_agent_state=self._last_state,
            config={"model": self.model_name},
        )

        return result


def run_examples(agent: ReturnAgent) -> List[Dict[str, Any]]:
    scenarios = [
        # scenario 1: Return within window
        [
            "I want to return my headphones that I bought last week.",
            "They're not working properly. I have the original packaging."
        ],

        # scenario 2: Return outside window
        [
            "I bought a laptop 3 months ago and it's starting to have issues.",
            "The battery doesn't last more than an hour now. Can I return it?"
        ]
    ]

    print("\n=== Running example scenarios ===")
    perception_list = []
    for i, scenario in enumerate(scenarios, start=1):
        print(f"\n--- Scenario {i} ---")
        # Start a new session per scenario
        agent.new_session(label=f"example-scenario-{i}")
        perception = []
        for query in scenario:
            print(f"User: {query}")
            result = agent.handle(query)
            perception.append({"query": query, "result": result.model_dump()})
        # Ensure final memory save at scenario end
        # Save with chat history in chronological order (oldest first)
        agent.memory.save(
            chat_history=list(reversed(agent.chat_history)),  # Reverse to get oldest first
            perceptions_history=list(reversed(agent.perceptions_history)),  # Reverse to get oldest first
            perceptions=agent.perceptions,
            last_agent_state=agent._last_state,
            config={"model": agent.model_name},
        )
        perception_list.append(perception)
    print("=== Examples complete ===\n")
    return perception_list


def interactive_loop(agent: ReturnAgent) -> None:
    print("Enter your return queries. Type 'exit' to quit.")
    # Lazy-start a session only when the user actually sends a message
    session_started = False
    while True:
        try:
            user_in = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if user_in.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break
        if not user_in:
            continue
        if not session_started:
            agent.new_session(label="interactive")
            session_started = True
        agent.handle(user_in)
    # Save memory on exit only if a session was started (i.e., at least one user message was handled)
    if session_started:
        agent.memory.save(
            chat_history=list(reversed(agent.chat_history)),  # Reverse to get oldest first
            perceptions_history=list(reversed(agent.perceptions_history)),  # Reverse to get oldest first
            perceptions=agent.perceptions,
            last_agent_state=agent._last_state,
            config={"model": agent.model_name},
        )


if __name__ == "__main__":
    agent = ReturnAgent()

    # 1) Run the provided scenarios as examples
    _ = run_examples(agent)

    # 2) Start interactive input loop
    interactive_loop(agent)
