# Current file: EAG_V1_CAPESTONE\agents\DiscoveryAgent.py

from typing import Dict, Any, List, Optional
from config.enums import Agents
from prompts.DiscoveryEntityExtractionPrompt import SYSTEM_PROMPT_ENTITY_EXTRACTION
from nlu.discovery_nlu import DiscoveryNLU

import os
from config.enums import ModelType
from core.llm_client import LLMClient

class DiscoveryAgent:
    def __init__(self, subcategory: str, specification_list: List[Dict[str, Any]]) -> None:
        self.subcategory = subcategory
        self.llm =  LLMClient(model_type=os.getenv("MODEL_TYPE", ModelType.openai))
        self.specification_list = specification_list # All available specifications for the subcategory
        self.entities: Dict[str, Any] = {}
        self.spec_nlu = DiscoveryNLU(self.subcategory, self.specification_list)

    async def get_user_prompt_entity_extraction(self, message: str) -> str:
        specification_text = str(self.specification_list)
        user_prompt = specification_text + "\n\n" + message
        return user_prompt

    async def run(self, user_query: str) -> Dict[str, Any]:
        nlu_response = await self.spec_nlu.run(user_query)
        if nlu_response is None:
            raise ValueError("Discovery NLU response is None. PLease investigate.")
        return nlu_response

    # 1

