import os, json
from typing import List, Dict, Any, Optional
from prompts import buy_prompt

import google.generativeai as genai
from perceptions.buy_perception import extract_buy_details
from memory import SessionMemory
from utils.logger import get_logger, log_decision


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


def _load_buy_agent_prompt() -> str:
    try:
        from prompts.buy_prompt import BUY_AGENT_PROMPT
        return BUY_AGENT_PROMPT
    except Exception as e:
        print(f"[WARN] Could not load buy agent prompt from prompts.buy_prompt: {e}")
        return "You are a helpful e-commerce buy agent. Respond conversationally."


def _merge_perceptions(base: Dict[str, Any], latest: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
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


class BuyAgent:
    def __init__(self, verbose=True):
        self.chat_history: List[Dict[str, str]] = []
        self.perceptions_history: List[Dict[str, Any]] = []
        self.perceptions: Dict[str, Any] = {"specifications": {}, "quantity": 1}
        self.agent_name = "buy"
        self.verbose = verbose
        self.logger = get_logger("buy")
        self.memory = SessionMemory(agent_name=self.agent_name)

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

    def new_session(self, label: Optional[str] = None):
        self.chat_history = []
        self.perceptions_history = []
        self.perceptions = {"specifications": {}, "quantity": 1}
        self.memory.new_session(label=label, config={"model": self.model_name})
        log_decision(
            self.logger, agent="buy", event="new_session",
            why="start conversation", data={"label": label},
            session_id=self.memory.session_id
        )

    def initialize_for_testing(self, test_data: Dict[str, Any]) -> None:
        if "chat_history" in test_data:
            self.chat_history = test_data["chat_history"]
        if "perceptions" in test_data:
            self.perceptions = test_data["perceptions"]
        if "perceptions_history" in test_data:
            self.perceptions_history = test_data["perceptions_history"]
        log_decision(
            self.logger, agent="buy", event="test_initialization",
            why="setting up test state",
            data={"test_scenario": test_data.get("name", "unnamed")},
            session_id=self.memory.session_id
        )

    def _build_input_payload(self, latest_message: str, latest_perception: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chat_history": self.chat_history,
            "perceptions": self.perceptions,
            "latest_message": latest_message,
        }

    def _fallback_response(self, latest_message: str) -> str:
        missing = []
        if not self.perceptions.get("product_name"):
            missing.append("the product name")
        if not self.perceptions.get("specifications"):
            missing.append("key specs like brand, color, or size")
        if not self.perceptions.get("budget"):
            missing.append("your budget or price range (optional)")

        if missing:
            return f"Could you share {missing[0]}? That will help me find the best options."
        return "Great! I have enough details to search for options. Would you like me to pull up some matches now?"

    def _llm_response(self, payload: Dict[str, Any]) -> Optional[str]:
        if not self.model:
            return None
        try:
            input_block = json.dumps(payload, ensure_ascii=False, indent=2)
            full_prompt = (
                self.prompt_text
                + "\n\nINPUT START\n"
                + input_block
                + "\nINPUT END\n\nPlease produce a conversational response."
            )
            resp = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="text/plain"
                ),
            )
            return (resp.text or "").strip()
        except Exception as e:
            print("[WARN] LLM generation failed:", e)
            return None

    def handle(self, query: str):
        print("\n" + "-" * 70)
        print("[BuyAgent] Processing buy query...")
        print("-" * 70)

        self.chat_history.append({"role": "user", "content": query})

        result = extract_buy_details(query)
        latest_perception = result.model_dump()
        self.perceptions_history.append({"message": query, "perception": latest_perception})
        self.perceptions = _merge_perceptions(self.perceptions, latest_perception)

        payload = self._build_input_payload(query, latest_perception)
        reply_text = self._llm_response(payload) or self._fallback_response(query)

        print("\n" + "=" * 50)
        print(f"Agent: {reply_text}")
        print("=" * 50)

        self.chat_history.append({"role": "agent", "content": reply_text})

        self.memory.save(
            chat_history=self.chat_history,
            perceptions_history=self.perceptions_history,
            perceptions=self.perceptions,
            config={"model": self.model_name},
        )
        return result


def run_conversation_flow_examples(agent: BuyAgent) -> None:
    scenarios = [
        {
            "name": "Continue laptop conversation",
            "chat_history": [
                {"role": "user", "content": "I want to buy a laptop."},
                {"role": "agent", "content": "Great! Do you have any specific requirements like brand, screen size, or budget?"}
            ],
            "perceptions": {
                "product_name": "laptop",
                "specifications": {},
                "quantity": 1,
                "category": "electronics"
            },
            "current_query": "I need three laptops actually."
        },
        {
            "name": "Add specifications to laptop",
            "chat_history": [
                {"role": "user", "content": "I want to buy a laptop."},
                {"role": "agent", "content": "Great! Do you have any specific requirements like brand, screen size, or budget?"},
                {"role": "user", "content": "I need three laptops actually."},
                {"role": "agent", "content": "Sure, do you need them with the same specs? Any brand or budget preference?"}
            ],
            "perceptions": {
                "product_name": "laptop",
                "specifications": {},
                "quantity": 3,
                "category": "electronics"
            },
            "current_query": "I want Dell laptops with at least 16GB RAM."
        }
    ]

    print("\n" + "=" * 30 + " CONVERSATION FLOW SCENARIOS " + "=" * 30)
    for i, scenario in enumerate(scenarios, start=1):
        print(f"\n{'=' * 20} Scenario {i}: {scenario['name']} {'=' * 20}")
        agent.new_session(label=f"conversation-flow-{i}")
        agent.initialize_for_testing(scenario)

        print("\n" + "-" * 30 + " CONVERSATION HISTORY " + "-" * 30)
        for msg in agent.chat_history:
            role = msg['role'].capitalize()
            print(f"\n{role}: {msg['content']}")

        query = scenario["current_query"]
        print(f"\nCurrent user query: {query}")
        result = agent.handle(query)

        print("\n" + "=" * 30 + " RESULTS " + "=" * 30)
        perceptions_data = {k: v for k, v in result.model_dump().items() if v not in (None, {}, [])}
        if perceptions_data:
            print("Extracted perceptions:")
            for key, value in perceptions_data.items():
                print(f"  {key}: {value}")
        else:
            print("Extracted perceptions: None")

        final_state = {k: v for k, v in agent.perceptions.items() if v not in (None, {}, [])}
        if final_state:
            print("\nFinal perceptions state:")
            for key, value in final_state.items():
                print(f"  {key}: {value}")
        else:
            print("\nFinal perceptions state: Empty")

        print("=" * 70)

    print("=== Conversation flow examples complete ===\n")


def interactive_loop(agent: BuyAgent) -> None:
    print("\n" + "=" * 30 + " INTERACTIVE MODE " + "=" * 30)
    print("Enter your purchase queries. Type 'exit' to quit.")
    session_started = False
    while True:
        try:
            user_in = input("\nYou: ").strip()
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
    agent = BuyAgent(verbose=True)
    run_conversation_examples = False
    run_interactive = True

    if run_conversation_examples:
        run_conversation_flow_examples(agent)
    if run_interactive:
        interactive_loop(agent)
