import os, json, re
from typing import List, Dict, Any, Optional, Tuple

import google.generativeai as genai
from perceptions.order_perception import extract_order_details, process_payment, generate_order_id, OrderDetails
from memory import SessionMemory
from utils.logger import get_logger, log_decision


def _project_path(*parts: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", *parts))


def _load_order_agent_prompt() -> str:
    path = _project_path("Prompts", "order_prompt.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Try to extract triple-quoted string assigned to ORDER_AGENT_PROMPT
        m = re.search(r'ORDER_AGENT_PROMPT\s*=\s*"""(.*?)"""', content, re.S)
        if m:
            return m.group(1).strip()
        return content.strip()
    except Exception as e:
        print(f"[WARN] Could not load order agent prompt from {path}: {e}")
        return "You are a helpful e-commerce order agent. Process orders and provide status updates."


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


class OrderAgent:
    def __init__(self):
        # Conversation state (store oldest-first for convenience internally)
        self.chat_history: List[Dict[str, str]] = []  # {role: 'user'|'agent', content: str}
        self.order_details: Optional[OrderDetails] = None
        self.payment_result: Optional[Dict[str, Any]] = None

        # Logging
        self.logger = get_logger("order")

        # Shared session memory manager (reusable across agents)
        self.memory = SessionMemory(agent_name="order")
        self._last_state: Dict[str, Any] = {}

        # LLM setup
        self.prompt_text: str = _load_order_agent_prompt()
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
        self.order_details = None
        self.payment_result = None
        self._last_state = {}
        # Initialize memory session and persist an initial shell
        self.memory.new_session(label=label, config={"model": self.model_name})

    # ---------- Payload for LLM ----------
    def _build_input_payload(self, latest_message: str) -> Dict[str, Any]:
        return {
            "chat_history": self.chat_history,  # Already in chronological order (oldest first)
            "order_details": self.order_details.dict() if self.order_details else None,
            "payment_result": self.payment_result,
            "latest_message": latest_message,
        }

    def _fallback_response(self, latest_message: str) -> Tuple[str, Dict[str, Any]]:
        # Basic fallback response when LLM is unavailable
        if not self.order_details:
            # No order details provided yet
            reply = (
                "I need valid order details to process this order. "
                "Please provide at minimum a product ID and quantity."
            )
            state = {
                "order_status": "pending",
                "payment_status": "pending",
                "message": "Waiting for valid order details"
            }
        elif not self.order_details.order_id:
            # Generate order ID and request payment processing
            order_id = generate_order_id()
            reply = (
                f"Order received with ID: {order_id}. "
                f"Product: {self.order_details.product_id}, Quantity: {self.order_details.quantity}. "
                "Payment processing will begin shortly."
            )
            state = {
                "order_id": order_id,
                "product_id": self.order_details.product_id,
                "quantity": self.order_details.quantity,
                "order_status": "processing",
                "payment_status": "pending",
                "message": "Order received, payment pending"
            }
        elif not self.payment_result:
            # Payment not yet processed
            reply = (
                f"Order {self.order_details.order_id} is being processed. "
                "Payment processing will begin shortly."
            )
            state = {
                "order_id": self.order_details.order_id,
                "product_id": self.order_details.product_id,
                "quantity": self.order_details.quantity,
                "order_status": "processing",
                "payment_status": "pending",
                "message": "Payment processing"
            }
        else:
            # Payment has been processed
            payment_status = self.payment_result.get("status", "unknown")
            if payment_status == "paid":
                reply = (
                    f"Good news! Order {self.order_details.order_id} has been successfully processed. "
                    f"Payment of {self.payment_result.get('amount', 'unknown amount')} was successful. "
                    "Your order will be shipped soon."
                )
                state = {
                    "order_id": self.order_details.order_id,
                    "product_id": self.order_details.product_id,
                    "quantity": self.order_details.quantity,
                    "order_status": "paid",
                    "payment_status": "paid",
                    "payment_id": self.payment_result.get("payment_id"),
                    "transaction_id": self.payment_result.get("transaction_id"),
                    "message": "Payment successful, order confirmed"
                }
            else:
                error_message = self.payment_result.get("message", "Unknown error")
                reply = (
                    f"There was an issue processing payment for order {self.order_details.order_id}. "
                    f"Error: {error_message}. "
                    "Please try again with a different payment method."
                )
                state = {
                    "order_id": self.order_details.order_id,
                    "product_id": self.order_details.product_id,
                    "quantity": self.order_details.quantity,
                    "order_status": "failed",
                    "payment_status": "failed",
                    "payment_id": self.payment_result.get("payment_id"),
                    "payment_message": error_message,
                    "message": "Payment failed"
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

    def _process_payment(self) -> Dict[str, Any]:
        """Process payment for the order using the payment gateway."""
        # In a real implementation, this would connect to an actual payment gateway
        # For now, we're using a simulated payment processor
        if not self.order_details:
            return {
                "status": "failed",
                "message": "No order details available"
            }

        # Make sure we have the minimum required fields
        if not self.order_details.total_price:
            # If total_price is not set, try to calculate it from unit_price and quantity
            if self.order_details.unit_price:
                self.order_details.total_price = self.order_details.unit_price * self.order_details.quantity
            else:
                # Default to a placeholder value for demonstration
                self.order_details.total_price = 99.99 * self.order_details.quantity

        # Call the payment processor
        return process_payment(self.order_details)

    def handle(self, input_data: Any, is_buy_agent: bool = True) -> Dict[str, Any]:
        """
        Process an order request.

        Args:
            input_data: Can be a string message or a dictionary with order details
            is_buy_agent: True if input is from Buy Agent, False if from a user

        Returns:
            Dictionary with order processing results
        """
        print("[OrderAgent] Processing order request...")

        # Extract message content for chat history
        if isinstance(input_data, dict):
            message_content = json.dumps(input_data)
        else:
            message_content = str(input_data)

        # Update chat with user/buy agent message
        self.chat_history.append({
            "role": "buy_agent" if is_buy_agent else "user",
            "content": message_content
        })

        # Extract order details
        order_details = extract_order_details(input_data)

        # Initialize or update order details
        if not self.order_details:
            self.order_details = order_details
        else:
            # Update existing order details with any new information
            for field, value in order_details.dict().items():
                if value is not None:
                    setattr(self.order_details, field, value)

        # If we have valid order details but no order ID, generate one
        if self.order_details and self.order_details.product_id != "unknown" and not self.order_details.order_id:
            self.order_details.order_id = generate_order_id()

        # If we have valid order details with an order ID but no payment result, process payment
        if (self.order_details and 
            self.order_details.order_id and 
            self.order_details.product_id != "unknown" and 
            not self.payment_result):
            self.payment_result = self._process_payment()

            # Update order status based on payment result
            if self.payment_result.get("status") == "paid":
                self.order_details.order_status = "paid"
                self.order_details.payment_status = "paid"
                self.order_details.payment_id = self.payment_result.get("payment_id")
            else:
                self.order_details.order_status = "failed"
                self.order_details.payment_status = "failed"
                self.order_details.payment_id = self.payment_result.get("payment_id")

        # Build payload for the agent prompt
        payload = self._build_input_payload(message_content)

        # Get agent response via LLM, fallback if needed
        out = self._llm_response(payload)
        if out is None:
            reply_text, state = self._fallback_response(message_content)
        else:
            reply_text, state = out

        # Print and record agent reply
        print(f"OrderAgent: {reply_text}")
        print("[OrderAgent] State:", state)
        self.chat_history.append({"role": "agent", "content": reply_text})

        # Cache last state and persist session memory
        self._last_state = state

        # Reverse before saving to get oldest at the top (newest at the bottom) in memory files
        reversed_chat_history = list(reversed(self.chat_history))

        try:
            # Save directly via shared SessionMemory (handles pathing and ordering)
            self.memory.save(
                chat_history=self.chat_history,
                perceptions_history=[],  # Order agent doesn't use perceptions_history
                perceptions={},  # Order agent doesn't use perceptions
                last_agent_state=self._last_state,
                config={"model": self.model_name},
            )
            print(f"[OrderAgent] Saved memory for session {self.memory.session_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save memory: {e}")

        # Return order status information to the Buy Agent
        result = {
            "order_id": self.order_details.order_id if self.order_details else None,
            "product_id": self.order_details.product_id if self.order_details else None,
            "product_name": self.order_details.product_name if self.order_details else None,
            "quantity": self.order_details.quantity if self.order_details else None,
            "order_status": self.order_details.order_status if self.order_details else "pending",
            "payment_status": self.order_details.payment_status if self.order_details else "pending",
        }

        # Add payment details if available
        if self.payment_result:
            result.update({
                "payment_id": self.payment_result.get("payment_id"),
                "payment_message": self.payment_result.get("message"),
                "transaction_id": self.payment_result.get("transaction_id"),
                "timestamp": self.payment_result.get("timestamp")
            })

        return result


def run_examples(agent: OrderAgent) -> List[Dict[str, Any]]:
    scenarios = [
        # scenario 1: Successful order
        {
            "product_id": "123456",
            "product_name": "Wireless Headphones",
            "quantity": 1,
            "unit_price": 99.99,
            "customer_id": "cust_12345",
            "payment_method": "credit_card"
        },

        # scenario 2: Failed payment
        {
            "product_id": "789012",
            "product_name": "Smart Watch",
            "quantity": 1,
            "unit_price": 249.99,
            "customer_id": "cust_67890",
            "payment_method": "credit_card"
        }
    ]

    print("\n=== Running example order scenarios ===")
    results_list = []
    for i, order_data in enumerate(scenarios, start=1):
        print(f"\n--- Order Scenario {i} ---")
        # Start a new session per scenario
        agent.new_session(label=f"example-order-{i}")

        # Process the order
        print(f"Order Request: {json.dumps(order_data, indent=2)}")
        result = agent.handle(order_data)
        results_list.append(result)

        # If you want to simulate a follow-up message
        if i == 2 and result.get("payment_status") == "failed":
            print("\n--- Follow-up for failed payment ---")
            follow_up = "I'd like to try a different payment method. Can I use PayPal instead?"
            result = agent.handle(follow_up, is_buy_agent=False)
            results_list.append(result)

    print("=== Examples complete ===\n")
    return results_list


def interactive_loop(agent: OrderAgent) -> None:
    print("Enter order details or messages. Type 'exit' to quit.")
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

        # Check if input is JSON
        try:
            order_data = json.loads(user_in)
            is_buy_agent = True
        except json.JSONDecodeError:
            order_data = user_in
            is_buy_agent = False

        agent.handle(order_data, is_buy_agent=is_buy_agent)


if __name__ == "__main__":
    import sys

    agent = OrderAgent()

    # Check if we should skip examples
    skip_examples = "--skip-examples" in sys.argv

    if not skip_examples:
        # Run the provided scenarios as examples
        _ = run_examples(agent)

    # Start interactive input loop
    interactive_loop(agent)
