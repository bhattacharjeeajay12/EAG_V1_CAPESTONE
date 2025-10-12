from core.llm_client import LLMClient
from typing import Any, Dict, List, Optional
from prompts.QueryTool import get_system_prompt_query_tool

class QueryAgent:
    def __init__(self, conversation_history):
        self.query_tool = conversation_history
        self.llm_client = LLMClient()
        self.system_prompt: Optional[str] = None
        self.user_prompt = None

    async def create_input_structure(self, conversation_history):
        user_prompt = []
        return user_prompt

    async def get_prompt(self):
        self.system_prompt = get_system_prompt_schema()







