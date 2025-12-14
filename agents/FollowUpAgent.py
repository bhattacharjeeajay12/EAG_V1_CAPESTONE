from core.llm_client import LLMClient
from typing import Any, Dict, List, Optional
from prompts.FollowUpPrompt import DiscoveryFollowUpPrompt
import json
from config.enums import ChatInfo
import re

class FollowupAgent:
    def __init__(self):
        self.llm_client = LLMClient()
        self.system_prompt: Optional[str] = None

    async def create_user_prompt(self, user_query: str, ai_response: str) -> str:
        input_json = {
            "Question": user_query,
            "Answer": ai_response
        }
        return json.dumps(input_json, indent=2)

    async def parse_llm_json(self, text: str):
        try:
            # Remove known code fences
            cleaned = text.replace("```json", "").replace("```", "").strip()

            # Optional: extract the JSON object if extra text exists
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                cleaned = match.group(0)

            return json.loads(cleaned)

        except json.JSONDecodeError as e:
            raise ValueError("LLM returned invalid JSON") from e

    async def run(self, current_query: str, ai_response) -> str:
        system_prompt = DiscoveryFollowUpPrompt
        user_prompt = await self.create_user_prompt(current_query, ai_response)
        llm_response = await self.llm_client.generate(system_prompt, user_prompt)
        result = await self.parse_llm_json(llm_response)
        return result


if __name__ == "__main__":
    import asyncio

    async def main():
        # Example conversation history: Each turn contains user query and entities extracted (if available)
        chats = []
        current_query = "Show me laptops from Dell."
        ai_response = "Here are Dell laptops available across different subcategories, along with their prices and key specifications."

        # current_query = "Does this phone support 5G?"
        # ai_response = "Yes, this phone supports 5G connectivity based on its listed specifications."
        #
        # current_query = "Is there a cheaper option than this?"
        # ai_response = "Yes, there are lower-priced products available in the same subcategory."

        agent = FollowupAgent()
        result = await agent.run(current_query=current_query, ai_response=ai_response)
        print("==== LLM RESULT ====")
        print(json.dumps(result, indent=2))

    asyncio.run(main())
