import os
import json
from typing import Optional

from agents.planner import PlannerAgent
from utils.logger import get_logger, log_decision


def main() -> None:
    logger = get_logger("main")
    planner = PlannerAgent()
    session_label: Optional[str] = os.getenv("SESSION_LABEL", "cli-session")
    planner.new_session(label=session_label)

    print("Enter your request (type 'exit' to quit):")
    while True:
        try:
            user_in = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not user_in:
            continue
        if user_in.lower() in {"exit", "quit", "q"}:
            break

        log_decision(logger, agent="user", event="input", why="user message", data={"text": user_in}, session_id=planner.session_id)
        result = planner.handle(user_in)
        agent = result.get("agent")
        payload = result.get("result")
        print(f"[{agent}] -> {json.dumps(payload, indent=2, default=str)}")

    print("Goodbye!")


if __name__ == "__main__":
    main()
