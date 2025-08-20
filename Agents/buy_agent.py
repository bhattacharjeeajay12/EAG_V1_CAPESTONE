import os, json, re
from typing import List, Dict, Any, Optional, Tuple

import google.generativeai as genai
from buy_perception import extract_buy_details


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


def _load_buy_agent_prompt() -> str:
    path = _project_path("Prompts", "buy_prompt.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Try to extract triple-quoted string assigned to BUY_AGENT_PROMPT
        m = re.search(r'BUY_AGENT_PROMPT\s*=\s*"""(.*?)"""', content, re.S)
        if m:
            return m.group(1).strip()
        return content.strip()
    except Exception as e:
        print(f"[WARN] Could not load buy agent prompt from {path}: {e}")
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


class BuyAgent:
    def __init__(self):
        # Conversation state (store oldest-first for convenience internally)
        self.chat_history: List[Dict[str, str]] = []  # {role: 'user'|'agent', content: str}
        self.perceptions_history: List[Dict[str, Any]] = []  # list of {message, perception}
        self.perceptions: Dict[str, Any] = {"specifications": {}, "quantity": 1}

        # LLM setup
        self.prompt_text: str = _load_buy_agent_prompt()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.model = None
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel(model_name)
            except Exception as e:
                print("[WARN] Failed to initialize Gemini model:", e)
                self.model = None

    def _build_input_payload(self, latest_message: str, latest_perception: Dict[str, Any]) -> Dict[str, Any]:
        # chat_history and perceptions_history must be NEWEST-first per prompt
        newest_first_chat = list(reversed(self.chat_history))
        newest_first_perc = list(reversed(self.perceptions_history))
        return {
            "chat_history": newest_first_chat,
            "perceptions_history": newest_first_perc,
            "perceptions": self.perceptions,
            "latest_message": latest_message,
            "latest_perception": latest_perception,
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
        if missing:
            ask = "; ".join(missing)
            reply = (
                f"Thanks! I captured your request. Could you share {ask}? "
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

    def handle(self, query: str):
        print("[BuyAgent] Processing buy query...")
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

        # Get agent response via LLM, fallback if needed
        out = self._llm_response(payload)
        if out is None:
            reply_text, state = self._fallback_response(query)
        else:
            reply_text, state = out

        # Print and record agent reply
        print(f"Agent: {reply_text}")
        print("[BuyAgent] State:", state)
        self.chat_history.append({"role": "agent", "content": reply_text})

        return result


def run_examples(agent: BuyAgent) -> List[Dict[str, Any]]:
    scenarios = [
        # scenario 1
        [
            "I need headphones.",
            "I need wired earphone"
        ],
        # scenario 2
        [
            "I want shoes.",
            "I want casual shoes"
        ],
    ]

    print("\n=== Running example scenarios ===")
    perception_list = []
    for i, scenario in enumerate(scenarios, start=1):
        print(f"\n--- Scenario {i} ---")
        perception = []
        for query in scenario:
            print(f"User: {query}")
            result = agent.handle(query)
            perception.append({"query": query, "result": result.model_dump()})
        perception_list.append(perception)
    print("=== Examples complete ===\n")
    return perception_list


def interactive_loop(agent: BuyAgent) -> None:
    print("Enter your purchase queries. Type 'exit' to quit.")
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
        agent.handle(user_in)


if __name__ == "__main__":
    agent = BuyAgent()

    # 1) Run the two provided scenarios as examples
    _ = run_examples(agent)

    # 2) Start interactive input loop
    interactive_loop(agent)
