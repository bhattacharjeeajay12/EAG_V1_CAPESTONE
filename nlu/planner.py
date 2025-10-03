# nlu/planner.py - LLM-based Planner NLU
import re, json, os
from typing import Dict, Any, List, Optional
from core.llm_client import LLMClient

# Try importing SYSTEM_PROMPT from prompts.planner; fallback to loading file if import fails
try:
    from prompts.planner import SYSTEM_PROMPT
except Exception:
    _prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'planner.py')
    if not os.path.exists(_prompt_path):
        _prompt_path = os.path.join(os.path.dirname(__file__), '..', 'planner.py')
    try:
        with open(_prompt_path, 'r', encoding='utf-8') as _f:
            # crude extraction: find SYSTEM_PROMPT = """ ... """
            txt = _f.read()
            m = re.search(r'SYSTEM_PROMPT\\s*=\\s*f?("""|\'\'\')(.*?)(\\1)', txt, re.DOTALL)
            SYSTEM_PROMPT = m.group(2) if m else "You are an e-commerce Workflow Planner."
    except Exception:
        SYSTEM_PROMPT = "You are an e-commerce Workflow Planner."

class PlannerNLU:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient(model_type=os.getenv("MODEL_TYPE", "openai"))

    async def analyze_message(self, user_message: str, conversation_context: Optional[List[Dict[str, Any]]] = None,
                              last_intent: str = "", session_entities: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call the Planner LLM to produce the slim planner JSON schema."""
        conversation_context = conversation_context or []
        user_prompt = self._make_user_prompt(user_message, conversation_context, last_intent)
        raw = await self.llm_client.generate(SYSTEM_PROMPT, user_prompt)
        try:
            obj = self._extract_json(raw)
        except Exception:
            # fallback: return a conservative UNKNOWN result
            return {
                "intent": "UNKNOWN",
                "intent_confidence": 0.0,
                "entities": {"subcategories": [], "order_id": None},
                "referenced_entities": [],
                "continuity": "UNCLEAR",
                "decision": {"new_workstreams": [], "existing_workflow_status": "UNCHANGED"},
                "clarify": None
            }
        # retain raw for heuristics if needed
        obj['raw_text'] = raw or ""
        return self._clean(obj)

    def _make_user_prompt(self, current: str, context: List[Dict[str, Any]], last_intent: str) -> str:
        turns = context[-3:] if context else []
        lines = ["CURRENT_MESSAGE: " + current, "PAST_3_TURNS: ["]
        for t in turns:
            role = t.get("role", "user")
            content = t.get("content", "").replace("\n", " ").replace('"', "'")
            lines.append(f'  {{"{role}": "{content}"}}')
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
        # Ensure required keys with safe defaults and normalize to slim schema
        entities = obj.get("entities") or {}
        # support both 'subcategory' (str) or 'subcategories' (list)
        subs = entities.get("subcategories") or entities.get("subcategory") or []
        if isinstance(subs, str):
            parts = [s.strip() for s in re.split(r'\\band\\b|,', subs) if s.strip()]
            subs = parts
        if not isinstance(subs, list):
            subs = [subs] if subs else []
        subs = [s for s in subs if s]

        cleaned = {
            "intent": obj.get("intent", "UNKNOWN"),
            "intent_confidence": float(obj.get("intent_confidence", 0.0) or 0.0),
            "entities": {"subcategories": subs, "order_id": entities.get("order_id")},
            "referenced_entities": obj.get("referenced_entities") or [],
            "continuity": obj.get("continuity") or "UNCLEAR",
            "decision": {"new_workstreams": [], "existing_workflow_status": "UNCHANGED"},
            "clarify": obj.get("clarify")
        }

        # Normalize decision.new_workstreams if present
        decision = obj.get("decision") or {}
        new_ws = decision.get("new_workstreams") or []
        # If LLM didn't propose but subcategories exist, create DISCOVERY workstreams
        if not new_ws and subs:
            for s in subs:
                new_ws.append({"type": "DISCOVERY", "target": {"subcategory": s, "order_id": None}})

        # If LLM provided new_workstreams, keep them
        cleaned["decision"]["new_workstreams"] = new_ws
        cleaned["decision"]["existing_workflow_status"] = decision.get("existing_workflow_status") or decision.get("existing") or "UNCHANGED"

        return cleaned
