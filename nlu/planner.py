# nlu/planner_nlu.py (updated for slim planner schema)
import json, re, os
from typing import Dict, Any, List, Optional
from core.llm_client import LLMClient
from prompts.planner import SYSTEM_PROMPT

class PlannerNLU:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        model_type = os.getenv("MODEL_TYPE", "gpt-3.5")
        self.llm_client = llm_client or LLMClient(model_type=model_type)

    async def analyze_message(self, user_message: str, conversation_context: Optional[List[Dict[str, Any]]] = None,
                              last_intent: str = "", session_entities: Dict[str, Any] = None) -> Dict[str, Any]:
        user_prompt = self._make_user_prompt(user_message, conversation_context or [], last_intent or "")
        raw = await self.llm_client.generate(SYSTEM_PROMPT, user_prompt)
        obj = self._extract_json(raw)
        return self._clean(obj)

    def _make_user_prompt(self, current: str, context: List[Dict[str, Any]], last_intent: str) -> str:
        # Build compact context for the prompt
        turns = context[-3:] if context else []
        lines = ["CURRENT_MESSAGE: " + current, "PAST_3_TURNS: ["]
        for t in turns:
            role = t.get("role", "user")
            lines.append(f'  {{"{role}": "{t.get("content","").replace("\\"," ").replace("\n"," ") }"}}')
        lines.append("]")
        lines.append("LAST_INTENT: " + (last_intent or ""))
        return "\n".join(lines)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        i, j = text.find('{'), text.rfind('}')
        if i == -1 or j == -1:
            raise ValueError("No JSON found in LLM response.")
        return json.loads(text[i:j+1])

    def _clean(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure required keys with safe defaults
        entities = obj.get("entities") or {}
        obj.setdefault("intent", "UNKNOWN")
        obj.setdefault("intent_confidence", 0.0)
        obj["entities"] = {
            "subcategory": entities.get("subcategory"),
            "order_id": entities.get("order_id"),
        }
        obj["referenced_entities"] = obj.get("referenced_entities") or []
        obj.setdefault("continuity", "UNCLEAR")
        decision = obj.get("decision") or {}
        obj["decision"] = {
            "new_workstreams": decision.get("new_workstreams", []),
            "existing_workflow_status": decision.get("existing_workflow_status") or decision.get("existing") or "UNCHANGED"
        }
        obj["clarify"] = obj.get("clarify")
        return obj
