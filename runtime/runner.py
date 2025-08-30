import asyncio
from runtime.planner import Planner
from core.logging_setup import configure_logging

logger = configure_logging("demo")

async def main():
    planner = Planner()

    turns = [
        "Show me gaming laptops under $1500",
        "(tool returns results)",   # simulate tool callback
        "Compare it with HP laptops",
        "Buy this one",
    ]

    for t in turns:
        action = await planner.handle_user_turn(t)
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
