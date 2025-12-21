import asyncio
from runtime.planner import PlannerAgent
from core.logging_setup import configure_logging
from core.conversation_history import ConversationHistory
import uuid
# todo:
# ConversationHistory should be imported here in runner. Because here the session variable would also be added.
# in future add the session variables here.

logger = configure_logging("demo")


async def main():
    session_id = str(uuid.uuid4())
    ch = ConversationHistory(session_id)
    planner = PlannerAgent(ch)

    # turns = [
    #     "I need a laptop ?",
    # ]
    # for t in turns:
    while True:
        # question = input("USER: ")
        question = await asyncio.to_thread(input, "USER: ")
        answer = await planner.handle_user_turn(question)
        logger.info(f"USER: {question}")
        logger.info(f"AI Response: {answer}")
        logger.info("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
