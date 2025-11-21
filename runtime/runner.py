import asyncio
from runtime.planner import PlannerAgent
from core.logging_setup import configure_logging
from core.conversation_history import ConversationHistory

# todo:
# ConversationHistory should be imported here in runner. Because here the session variable would also be added.
# in future add the session variables here.

logger = configure_logging("demo")


async def main():
    ch = ConversationHistory()
    planner = PlannerAgent(ch)
    turns = [
        "I need a laptop ?",
    ]
    # for t in turns:
    while True:
        t = input("USER: ")
        action = await planner.handle_user_turn(t, ch)
        logger.info(f"USER: {t}")
        logger.info(f"ACTION: {action}")
        logger.info("-" * 60)

    # 🔑 Summary after conversation
    snapshot = planner.history.session_snapshot()
    print("\n=== SUMMARY OF WORKSTREAMS ===")
    for wid, ws in snapshot["workstreams"].items():
        print(f"Workstream {wid} ({ws.type})")
        print(f"  Status: {ws.status}")
        print(f"  Slots: {ws.slots}")
        if ws.candidates:
            print(f"  Candidates: {len(ws.candidates)} items")
        if ws.compare and (ws.compare.get('left') or ws.compare.get('right')):
            print(f"  Compare: {ws.compare}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
