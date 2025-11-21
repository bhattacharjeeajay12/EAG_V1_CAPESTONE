# nlu/planner_nlu.py - LLM-based Planner NLU

import re
import json
import os
from typing import Dict, Any, List, Optional
from core.llm_client import LLMClient
from prompts.planner import SYSTEM_PROMPT
from core.conversation_history import ConversationHistory
from config.enums import MsgTypes, ConverstionVars, ModelType


class PlannerNLU:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient(model_type=os.getenv("MODEL_TYPE", ModelType.openai))

    def get_user_prompt(self, current_msg: str, conversation_history: ConversationHistory) -> str:
        all_ws = conversation_history.get_all_workstreams()
        active_ws = conversation_history.get_active_workstream()

        past_5_turns_all_ws = {}
        for ws_id, ws in all_ws.items():
            chats = ws.get_chats()
            past_5_turns_all_ws[ws_id] = chats[-int(ConverstionVars.max_turns):] if chats else []

        active_ws_turns = {
            "active_workstream_id": active_ws.id if active_ws else None,
            "past_5_turns": active_ws.get_chats()[-int(ConverstionVars.max_turns):] if active_ws else []
        }

        input_dict = {
            "CURRENT_MESSAGE": current_msg,
            "ACTIVE_WORKSTREAM_PAST_5_TURNS": active_ws_turns,
            "SESSION_WORKSTREAMS": past_5_turns_all_ws
        }
        return str(input_dict)

    # ------------------------------------------------------------
    # CLEAN RAW RESPONSE
    # ------------------------------------------------------------
    def clean_raw_response(self, response: str) -> Dict[str, Any]:
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

    # ------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------
    async def run(self, user_message: str, conversation_context: ConversationHistory):
        """
        Call the Planner LLM and return cleaned JSON planner output.
        """

        user_prompt = self.get_user_prompt(user_message, conversation_context)

        try:
            raw_llm_output = await self.llm_client.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt
            )
        except Exception as e:
            print(f"Exception {e} occurred while calling Planner LLM.")
            return None

        cleaned = self.clean_raw_response(raw_llm_output)
        return cleaned

if __name__ == "__main__":
    pass
