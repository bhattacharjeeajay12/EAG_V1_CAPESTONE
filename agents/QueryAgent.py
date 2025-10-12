from core.llm_client import LLMClient
from typing import Any, Dict, List, Optional
from prompts.QueryTool import get_system_prompt_query_tool
import json

class QueryAgent:
    def __init__(self, conversation_history=None):
        self.llm_client = LLMClient()
        self.system_prompt: Optional[str] = None
        self.conversation_history = conversation_history

    def format_conversation(self, turns: List[Dict]) -> List[Dict]:
        # Turn history into the structure expected by the prompt.
        formatted = []
        for t in turns:
            entry = {}
            if "user_query" in t:
                entry["user"] = {"user_query": t["user_query"], "entities": t.get("entities", [])}
            if "agent_response" in t:
                entry["agent"] = {"agent_response": t["agent_response"]}
            formatted.append(entry)
        return formatted

    async def create_input_structure(self, current_query: str, turns: List[Dict]) -> str:
        formatted_history = self.format_conversation(turns)
        input_json = {
            "current_query": current_query,
            "conversation_history": formatted_history
        }
        # As string, ready for LLM
        return json.dumps(input_json, indent=2)

    async def get_prompt(self, category: Optional[str] = None) -> str:
        # Category-specific prompt, else general
        if category:
            return get_system_prompt_query_tool(category)
        else:
            return get_system_prompt_query_tool("default")
    
    async def run(self, current_query: str, turns: List[Dict], category: Optional[str] = None) -> Dict[str, Any]:
        system_prompt = await self.get_prompt(category)
        user_prompt = await self.create_input_structure(current_query, turns)
        llm_response = await self.llm_client.generate(system_prompt, user_prompt)
        try:
            result = json.loads(llm_response)
        except Exception:
            # Try extract JSON object from string if extra text
            import re
            m = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if m:
                result = json.loads(m.group(0))
            else:
                result = {"error": "Could not parse LLM response"}
        return result


if __name__ == "__main__":
    import asyncio

    async def main():
        # Example conversation history: Each turn contains user query and entities extracted (if available)
        conversation_turns = [
            {"user_query": "I need a Dell laptop", "entities": [
                {"key": "subcategory_name", "value": "laptop", "operator": "="},
                {"key": "brand", "value": "Dell", "operator": "="}
            ], "agent_response": "What specifications are important to you?"},
            {"user_query": "16GB RAM would be great", "entities": [
                {"key": "RAM", "value": 16, "operator": ">=", "unit": "GB"}
            ], "agent_response": "Any preference for storage?"},
        ]

        current_query = "Show me the second cheapest Dell laptop with at least 16GB RAM"
        category = "laptop"

        agent = QueryAgent()
        result = await agent.run(current_query=current_query, turns=conversation_turns, category=category)
        print("==== LLM RESULT ====")
        print(json.dumps(result, indent=2))

    asyncio.run(main())
