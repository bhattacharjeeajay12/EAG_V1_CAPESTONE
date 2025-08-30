
import asyncio
from runtime.planner import Planner

async def main():
    planner = Planner()
    turns = [
        "Show me gaming laptops under $1500",
        "(tool returns results)",  # simulate next turn after tool
        "Compare it with HP laptops",
        "Buy this one",
    ]
    for t in turns:
        act = await planner.handle_user_turn(t)
        print(f"USER: {t}")
        print(f"ACTION: {act}")
        print("-"*60)

if __name__ == "__main__":
    asyncio.run(main())
