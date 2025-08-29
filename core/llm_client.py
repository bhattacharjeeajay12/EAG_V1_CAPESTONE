# core_1/llm_client.py
# Minimal LLM wrapper for gemini-2.0-flash with a safe fallback.

import os
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

# class LLMClient:
#     def __init__(self, model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash")):
#         self.model_name = model_name
#         self._ready = False
#         self._model = None
#         api_key = os.getenv("GEMINI_API_KEY", None)
#         try:
#             if api_key:
#                 import google.generativeai as genai
#                 genai.configure(api_key=api_key)
#                 self._model = genai.GenerativeModel(model_name)
#                 self._ready = True
#         except Exception:
#             self._ready = False
#
#     def generate(self, prompt: str) -> str:
#         if self._ready and self._model:
#             try:
#                 resp = self._model.generate_content(prompt)
#                 return getattr(resp, "text", "").strip() or ""
#             except Exception as e:
#                 print(f"LLM error: {str(e)}")
#                 pass
#         # Fallback: deterministic echo for tests/demos
#         return f"[LLM-FALLBACK] {prompt[:200]}"

class LLMClient:
    def __init__(self, model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini")):
        self.model_name = model_name
        self._ready = False
        self._client = None
        api_key = os.getenv("OPENAI_SECRET_KEY", None)
        try:
            if api_key:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
                self._ready = True
        except Exception:
            self._ready = False

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._ready and self._client:
            try:
                resp = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0
                )
                return (
                    resp.choices[0].message.content.strip()
                    if resp.choices and resp.choices[0].message.content
                    else ""
                )
            except Exception as e:
                print(f"LLM API error: {e}")
                pass

        # Fallback: deterministic echo for tests/demos
        return f"[LLM-FALLBACK] {str(messages)[:200]}"

if __name__ == "__main__":
    client = LLMClient()
    # prompt = input("Enter a prompt: ")
    messages = [
        {"role": "system", "content": "You are a concise math assistant."},
        {"role": "user", "content": "What is 2+2? Answer in one word."},
    ]

    print("=== Response ===")
    print(client.generate(messages))