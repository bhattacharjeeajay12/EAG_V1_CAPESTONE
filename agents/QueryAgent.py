from core.llm_client import LLMClient
from typing import Any, Dict, List, Optional
from prompts.QueryTool import get_system_prompt_query_tool
import json
from config.enums import ChatInfo
import re

class QueryAgent:
    def __init__(self):
        self.llm_client = LLMClient()
        self.system_prompt: Optional[str] = None

    async def create_user_prompt(self, current_query: str, consolidated_entities: List[Dict[str, Any]], chats:List[Dict[str, Any]]) -> str:
        """
        The user query needs
            1. current query
            2. specification NLU result for current query
            3. chats
            4. spec_nlu_result for chats (if any)
        """
        nlu_result = []
        if chats:
            last_chat = chats[-1]
        else:
            last_chat = {}
        if ChatInfo.processed.value in last_chat.keys():
            processed_list = last_chat[ChatInfo.processed.value]
            for processed in  processed_list:
                if processed.get("process_name") == "ENTITY_EXTRACTION":
                    nlu_result = processed.get("output", [])
                    break

        keys_to_keep = {
            ChatInfo.user_message.value,
            ChatInfo.ai_message.value,
        }
        chats = [
            {k: v for k, v in chat.items() if k in keys_to_keep}
            for chat in chats
        ]

        input_json = {
            "current_user_message": current_query,
            "current_entities_and_operator": nlu_result,
            "consolidated_entities_and_operator": consolidated_entities,
            "conversation_history": chats
        }
        # As string, ready for LLM
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

    async def run(self, current_query: str,
                  consolidated_entities, specification_list: List[Dict[str, Any]],
                  chats: List[Dict[str, Any]], subcategory: Optional[str] = None) -> Dict[str, Any]:
        system_prompt = await get_system_prompt_query_tool(subcategory, specification_list)
        user_prompt = await self.create_user_prompt(current_query, consolidated_entities, chats)
        llm_response = await self.llm_client.generate(system_prompt, user_prompt)
        result = await self.parse_llm_json(llm_response)
        return result


if __name__ == "__main__":
    import asyncio

    async def main():
        # Example conversation history: Each turn contains user query and entities extracted (if available)
        chats = []
        current_query = "Show laptops with i7 processor, 16GB RAM, and 512GB storage"
        subcategory = "smartphone"
        consolidated_entities = [
            {"key": "processor", "value": "i7", "operator": "="},
            {"key": "ram", "value": 16, "unit": "GB", "operator": "="},
            {"key": "storage", "value": 512, "unit": "GB", "operator": "="}
        ]

        specification_list = [
            {'data_type': 'text', 'spec_name': 'Brand', 'spec_name_label': 'Brand', 'spec_value': 'Apple',
             'unit': None},
            {'data_type': 'text', 'spec_name': 'Processor', 'spec_name_label': 'Processor', 'spec_value': 'Apple M3',
             'unit': None},
            {'data_type': 'integer', 'spec_name': 'RAM', 'spec_name_label': 'RAM', 'spec_value': '8',
             'unit': 'gigabytes'},
            {'data_type': 'integer', 'spec_name': 'Storage', 'spec_name_label': 'Storage', 'spec_value': '256',
             'unit': 'gigabytes'},
            {'data_type': 'float', 'spec_name': 'Display_Size', 'spec_name_label': 'Display Size', 'spec_value': '13.6',
             'unit': 'inches'},
            {'data_type': 'integer', 'spec_name': 'Battery_Life', 'spec_name_label': 'Battery Life', 'spec_value': '18',
             'unit': 'hours'},
            {'data_type': 'float', 'spec_name': 'Weight', 'spec_name_label': 'Weight', 'spec_value': '1.49',
             'unit': 'kilograms'},
            {'data_type': 'text', 'spec_name': 'Operating_System', 'spec_name_label': 'Operating System',
             'spec_value': 'macOS', 'unit': None},
            {'data_type': 'text', 'spec_name': 'Graphics', 'spec_name_label': 'Graphics', 'spec_value': 'Apple GPU',
             'unit': None},
            {'data_type': 'integer', 'spec_name': 'Warranty', 'spec_name_label': 'Warranty', 'spec_value': '1',
             'unit': 'years'},
            {'data_type': 'float', 'spec_name': 'Price', 'spec_name_label': 'Price', 'spec_value': '1694',
             'unit': 'USD'}
        ]
        agent = QueryAgent()
        result = await agent.run(current_query=current_query, consolidated_entities=consolidated_entities, specification_list = specification_list, chats=chats, subcategory=subcategory)
        print("==== LLM RESULT ====")
        print(json.dumps(result, indent=2))

    asyncio.run(main())
