from typing import Dict, Any, List, Optional
import os
import asyncio
from config.enums import ModelType
from core.llm_client import LLMClient
from prompts.PlanGenerator import get_discovery_plan_generator_prompt
from config.enums import Agents, ChatInfo
import json

class PlanGenerator:
    def __init__(self, type: str, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient(model_type=os.getenv("MODEL_TYPE", ModelType.openai))
        self.type = type
        self.system_prompt = get_discovery_plan_generator_prompt()
        self.spec_nlu_response = None

    async def get_clean_response(self, raw_response: str) -> str:
        return json.loads(raw_response)

    async def get_user_msg(self, user_query: str, chats: List[Dict[str, Any]]) -> str:
        allowed_keys = {"ai_message", "user_message"}

        filtered_chats = [
            {k: v for k, v in chat.items() if k in allowed_keys}
            for chat in chats
        ]

        input = {"current_query": user_query, "conversation_history": filtered_chats}
        return str(input)

    async def run(self, user_query: str, chats: List[Dict[str, Any]]) -> str | Dict[str, Any]:
        try:
            user_prompt = await self.get_user_msg(user_query, chats)
            raw_llm_output = await self.llm_client.generate(self.system_prompt, user_prompt)
        except Exception as e:
            print(f"Discovery NLU caught exception: {e}")
            return None
        # clean response
        clean_response = await self.get_clean_response(raw_llm_output)
        return clean_response



if __name__ == "__main__":


    async def main():

        # chats = List[Dict[str, Any]]
        current_query = "A 15-inch screen would be ideal, and I prefer Intel processors."
        chats = [
            {
                ChatInfo.user_message.value: "I need a laptop with price under 5000 USD.",
                ChatInfo.ai_message.value: "Sure, could you please specify any preferred brand or specifications?",
            },
            {
                ChatInfo.user_message.value: "No brand preference, but I would like at least 16GB RAM and 512GB SSD.",
                ChatInfo.ai_message.value: "Got it. Do you have any preference for screen size or processor type?",
            }
        ]

        #########
        current_query = "RAM should be 8 GB."
        chats = [
            {
                ChatInfo.user_message.value: "I need a laptop with price under 5000 USD.",
                ChatInfo.ai_message.value: "Sure, could you please specify any preferred brand or specifications?",
            },
            {
                ChatInfo.user_message.value: "No brand preference, but I would like at least 16GB RAM and 512GB SSD.",
                ChatInfo.ai_message.value: "Got it. Do you have any preference for screen size or processor type?",
            }
        ]



        pg = PlanGenerator(type="discovery")
        result = await pg.run(current_query, chats)
        print(result)

    # RUN async function properly
    asyncio.run(main())
