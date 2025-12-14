import json
from typing import Any, Dict, List, Optional

from config.enums import ChatInfo
from core.llm_client import LLMClient
from prompts.Summarizer import get_summarizer_prompt


class SummarizerAgent:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    async def _build_user_prompt(
        self,
        current_query: str,
        chats: List[Dict[str, Any]],
        query_result: Optional[Dict[str, Any]],
        history_limit: int = 5,
    ) -> str:
        trimmed_chats = []
        for chat in chats[-history_limit:]:
            trimmed_chats.append(
                {
                    ChatInfo.user_message.value: chat.get(ChatInfo.user_message.value),
                    ChatInfo.ai_message.value: chat.get(ChatInfo.ai_message.value),
                }
            )

        qr_payload = None
        if query_result:
            qr_payload = {
                "row_count": query_result.get("row_count", 0),
                "columns": query_result.get("columns", []),
                "preview": query_result.get("preview", []),
            }

        payload = {
            "current_query": current_query,
            "conversation_history": trimmed_chats,
            "query_result": qr_payload,
        }
        return json.dumps(payload, indent=2)

    async def _parse_llm_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        try:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start : end + 1]
            return json.loads(cleaned)
        except Exception:
            return {"answer": cleaned}

    def _format_response(self, parsed: Dict[str, Any]) -> str:
        answer = parsed.get("answer")

        if not answer:
            return ""
        return str(answer).strip()

    async def run(
        self,
        current_query: str,
        chats: List[Dict[str, Any]],
        query_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        system_prompt = get_summarizer_prompt()
        user_prompt = await self._build_user_prompt(current_query, chats, query_result)
        raw_response = await self.llm_client.generate(system_prompt, user_prompt)
        parsed = await self._parse_llm_json(raw_response)
        return self._format_response(parsed)
