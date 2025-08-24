import os, json, re
from typing import List, Dict, Any, Optional, Tuple

import google.generativeai as genai
from perceptions.recommendation_perception import extract_user_preferences, load_product_data, get_recommendations, UserPreference
from memory import SessionMemory
from utils.logger import get_logger, log_decision


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


def _load_recommendation_agent_prompt() -> str:
    path = _project_path("prompts", "recommendation_prompt.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Try to extract triple-quoted string assigned to RECOMMENDATION_AGENT_PROMPT
        m = re.search(r'RECOMMENDATION_AGENT_PROMPT\s*=\s*"""(.*?)"""', content, re.S)
        if m:
            return m.group(1).strip()
        return content.strip()
    except Exception as e:
        print(f"[WARN] Could not load recommendation agent prompt from {path}: {e}")
        return "You are a helpful e-commerce recommendation agent. Suggest products based on user preferences."


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


class RecommendationAgent:
    def __init__(self, product_data_path: Optional[str] = None):
        # Conversation state (store oldest-first for convenience internally)
        self.chat_history: List[Dict[str, str]] = []  # {role: 'user'|'agent', content: str}
        self.user_preferences: Optional[UserPreference] = None
        self.available_products = load_product_data(product_data_path)
        self.recommendations = []

        # Logging
        self.logger = get_logger("recommendation")

        # Shared session memory manager (reusable across agents)
        self.memory = SessionMemory(agent_name="recommendation")
        self._last_state: Dict[str, Any] = {}

        # LLM setup
        self.prompt_text: str = _load_recommendation_agent_prompt()
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
        self.user_preferences = None
        self.recommendations = []
        self._last_state = {}
        # Initialize memory session and persist an initial shell
        self.memory.new_session(label=label, config={"model": self.model_name})
        log_decision(self.logger, agent="recommendation", event="new_session", why="start conversation", data={"label": label}, session_id=self.memory.session_id)

    # ---------- Payload for LLM ----------
    def _build_input_payload(self, latest_message: str) -> Dict[str, Any]:
        return {
            "chat_history": self.chat_history,  # Already in chronological order (oldest first)
            "preferences": self.user_preferences.dict() if self.user_preferences else None,
            "available_products": [p.dict() for p in self.available_products[:20]],  # Limit to 20 products for token limit
            "recommendations": [r.dict() for r in self.recommendations],
            "latest_message": latest_message,
        }

    def _fallback_response(self, latest_message: str) -> Tuple[str, Dict[str, Any]]:
        # Basic fallback response when LLM is unavailable
        if not self.user_preferences:
            # No preferences extracted yet
            reply = (
                "I'd be happy to recommend some products for you. "
                "Could you tell me more about what you're looking for? "
                "For example, what type of product, any specific features, or your budget range?"
            )
            state = {
                "understood_intent": "unclear",
                "recommendation_count": 0,
                "top_recommendation_id": None,
                "top_recommendation_name": None,
                "query_satisfaction_level": "low",
                "recommended_next_step": "refine_search"
            }
        elif not self.recommendations:
            # We have preferences but no recommendations yet
            reply = (
                f"I understand you're looking for {self.user_preferences.product_type or 'products'}" +
                (f" in the {self.user_preferences.category} category" if self.user_preferences.category else "") +
                ". Unfortunately, I couldn't find any products that match your criteria exactly. "
                "Could you try broadening your search or adjusting your preferences?"
            )
            state = {
                "understood_intent": f"looking for {self.user_preferences.product_type or 'products'}",
                "recommendation_count": 0,
                "top_recommendation_id": None,
                "top_recommendation_name": None,
                "query_satisfaction_level": "low",
                "recommended_next_step": "refine_search"
            }
        else:
            # We have recommendations
            top_rec = self.recommendations[0]
            reply = (
                f"Based on your preferences, I recommend the {top_rec.product.product_name} "
                f"at ${top_rec.product.price:.2f}. {top_rec.reasoning}\n\n"
            )

            # Add a few more recommendations if available
            for i, rec in enumerate(self.recommendations[1:3], 1):
                reply += (
                    f"{i+1}. {rec.product.product_name} - ${rec.product.price:.2f}. "
                    f"{rec.reasoning}\n"
                )

            reply += "\nWould you like more details about any of these products?"

            state = {
                "understood_intent": f"looking for {self.user_preferences.product_type or 'products'}",
                "recommendation_count": len(self.recommendations[:3]),
                "top_recommendation_id": top_rec.product.product_id,
                "top_recommendation_name": top_rec.product.product_name,
                "query_satisfaction_level": "medium",
                "recommended_next_step": "explore_options"
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

    def handle(self, query: str) -> Dict[str, Any]:
        """
        Process a recommendation request.

        Args:
            query: User's request for product recommendations

        Returns:
            Dictionary with recommendation results
        """
        print("[RecommendationAgent] Processing recommendation request...")

        # Update chat with user message
        self.chat_history.append({"role": "user", "content": query})

        # Extract user preferences
        preferences = extract_user_preferences(query)
        self.user_preferences = preferences

        # Get recommendations based on preferences
        recommendation_response = get_recommendations(query)
        self.recommendations = recommendation_response.recommendations

        # Build payload for the agent prompt
        payload = self._build_input_payload(query)

        # Get agent response via LLM, fallback if needed
        out = self._llm_response(payload)
        if out is None:
            reply_text, state = self._fallback_response(query)
        else:
            reply_text, state = out

        # Print and record agent reply
        print(f"RecommendationAgent: {reply_text}")
        print("[RecommendationAgent] State:", state)
        self.chat_history.append({"role": "agent", "content": reply_text})

        # Cache last state and persist session memory
        self._last_state = state

        try:
            # Save directly via shared SessionMemory (handles pathing and ordering)
            self.memory.save(
                chat_history=self.chat_history,
                perceptions_history=[],  # Recommendation agent doesn't use perceptions_history
                perceptions=self.user_preferences.dict() if self.user_preferences else {},
                last_agent_state=self._last_state,
                config={"model": self.model_name},
            )
            print(f"[RecommendationAgent] Saved memory for session {self.memory.session_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save memory: {e}")

        # Return recommendation results
        result = {
            "understood_intent": state.get("understood_intent"),
            "recommendations": [
                {
                    "product_id": rec.product.product_id,
                    "product_name": rec.product.product_name,
                    "price": rec.product.price,
                    "category": rec.product.category,
                    "reasoning": rec.reasoning
                }
                for rec in self.recommendations[:5]  # Top 5 recommendations
            ],
            "recommendation_count": len(self.recommendations[:5]),
            "query_satisfaction_level": state.get("query_satisfaction_level", "low"),
            "recommended_next_step": state.get("recommended_next_step", "refine_search")
        }

        return result


def run_examples(agent: RecommendationAgent) -> List[Dict[str, Any]]:
    scenarios = [
        # scenario 1: Simple product request
        "I'm looking for wireless headphones under $100",

        # scenario 2: More detailed request
        "I need a waterproof sports watch with heart rate monitoring",

        # scenario 3: Brand-specific request
        "Can you recommend some Sony headphones with noise cancellation?"
    ]

    print("\n=== Running example recommendation scenarios ===")
    results_list = []
    for i, query in enumerate(scenarios, start=1):
        print(f"\n--- Recommendation Scenario {i} ---")
        # Start a new session per scenario
        agent.new_session(label=f"example-recommendation-{i}")

        # Process the recommendation request
        print(f"User Query: {query}")
        result = agent.handle(query)
        results_list.append(result)

    print("=== Examples complete ===\n")
    return results_list


def interactive_loop(agent: RecommendationAgent) -> None:
    print("Enter your product recommendation queries. Type 'exit' to quit.")
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


if __name__ == "__main__":
    import sys

    agent = RecommendationAgent()

    # Check if we should skip examples
    skip_examples = "--skip-examples" in sys.argv

    if not skip_examples:
        # Run the provided scenarios as examples
        _ = run_examples(agent)

    # Start interactive input loop
    interactive_loop(agent)
