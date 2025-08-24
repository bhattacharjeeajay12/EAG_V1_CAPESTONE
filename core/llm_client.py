# core/llm_client.py
# Minimal LLM wrapper for gemini-2.0-flash with a safe fallback.

import os

class LLMClient:
    def __init__(self, model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash")):
        self.model_name = model_name
        self._ready = False
        self._model = None
        api_key = os.getenv("GEMINI_API_KEY", None)
        try:
            if api_key:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self._model = genai.GenerativeModel(model_name)
                self._ready = True
        except Exception:
            self._ready = False

    def generate(self, prompt: str) -> str:
        if self._ready and self._model:
            try:
                resp = self._model.generate_content(prompt)
                return getattr(resp, "text", "").strip() or ""
            except Exception:
                pass
        # Fallback: deterministic echo for tests/demos
        return f"[LLM-FALLBACK] {prompt[:200]}"
