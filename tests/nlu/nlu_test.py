import asyncio
import json
from pathlib import Path
from core.nlu import EnhancedNLU
from core.llm_client import LLMClient
from tests.nlu.nlu_questions import questions  # Assuming questions are imported here
import time

async def main():
    nlu = EnhancedNLU()  # Initialize the NLU class
    answers = []
    total_start_time = time.time()

    for idx, (key, value) in enumerate(questions.items(), start=1):
        start_time = time.time()

        past_messages = []
        for msg in value.get("PAST_3_USER_MESSAGES", []):
            past_messages.append({"role": "user", "content": msg})

        answer = await nlu.analyze_message(  # Await the asynchronous call
            value["CURRENT_MESSAGE"],
            past_messages,
            value.get("last_intent", ""),
            value.get("session_entities", {})
        )
        answer["question"] = value["CURRENT_MESSAGE"]
        answer["question_key"] = key
        answers.append(answer)

        elapsed_time = time.time() - start_time
        print(f"Question {idx}: done ({elapsed_time:.2f}s)")

    total_time = time.time() - total_start_time
    print(f"\nTotal execution time: {total_time:.2f}s")

    # Save results
    output_file = Path("tests") / "nlu" / "nlu_answers.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w") as f:
        json.dump(answers, f, indent=2)

# Run the asyncio event loop
if __name__ == "__main__":
    asyncio.run(main())
