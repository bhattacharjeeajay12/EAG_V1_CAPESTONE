#core/planner_nlu.py

from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient
from config.enums import ModelType
from prompts.DiscoveryEntityExtractionPrompt import SYSTEM_PROMPT_ENTITY_EXTRACTION
import os
import json
import re

class DiscoveryNLU:

    def __init__(self, subcategory, specification_list, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient(model_type=os.getenv("MODEL_TYPE", ModelType.openai))
        self.user_prompt: str | None = None
        self.system_prompt: str = SYSTEM_PROMPT_ENTITY_EXTRACTION
        self.subcategory = subcategory
        self.specification_list: List[Dict[str, Any]] = specification_list

    async def get_user_prompt(self, question):
        user_prompt = "Input:\n"
        user_prompt += f"Product: {self.subcategory}\n"
        user_prompt += "Available specs:\n"
        spec_list_label = [spec["spec_name_label"].lower() for spec in self.specification_list]
        for obj in self.specification_list:
            str_ = ""
            str_ += f"\t- {obj['spec_name_label']}: datatype={obj['data_type']}, "
            if obj["unit"] is not None:
                str_ += f"unit - {obj['unit']}. "
                str_ += f"example - **{obj['spec_value']} {obj['unit']}."
            else:
                str_ += f"example - {obj['spec_value']}."
            user_prompt += str_ + "\n"
        user_prompt += f"Note: Use lowercase keys exactly as listed (e.g. {', '.join(spec_list_label)}) \n"
        user_prompt += f"\nuser prompt - {question}"
        return user_prompt

    # ------------------------------------------------------------
    # CLEAN RAW RESPONSE
    # ------------------------------------------------------------
    async def clean_raw_response(self, response: str) -> Dict[str, Any]:
        """
        Extract valid JSON from the LLM response.
        Handles:
        - extra text before/after JSON
        - markdown code fences
        - trailing commas
        - accidental backslashes
        """

        if not response:
            return {}

        # Remove markdown fences
        response = re.sub(r"```json", "", response, flags=re.IGNORECASE).strip()
        response = re.sub(r"```", "", response).strip()

        # Extract JSON substring using first '{' and last '}'
        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            json_str = response[start:end]
        except ValueError:
            return {}

        # Remove trailing commas inside objects or arrays
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

        # Remove weird escape sequences that LLM sometimes introduces
        json_str = json_str.replace("\n", "").replace("\t", "").replace("\\", "")

        # Try JSON load
        try:
            return json.loads(json_str)
        except Exception:
            try:
                # last fallback – try to repair common missing quotes & parse again
                json_str = re.sub(r"(['\"])?(\w+)(['\"])?\s*:", r'"\2":', json_str)
                return json.loads(json_str)
            except Exception:
                return {}

    async def run(self, user_query: str) -> Optional[Dict[str, Any]] | None:
        self.user_prompt = await self.get_user_prompt(user_query)
        try:
            raw_llm_output = await self.llm_client.generate(self.system_prompt, self.user_prompt)
        except Exception as e:
            print(f"Discovery NLU caught exception: {e}")
            return None
        llm_output_dict = await self.clean_raw_response(raw_llm_output)
        return llm_output_dict