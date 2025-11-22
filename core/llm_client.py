import os
import asyncio
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

class LLMClient:
    def __init__(self, model_type: str = "openai", model_name: Optional[str] = None):
        self.model_type = model_type
        self.model_name = model_name or (os.getenv("OPENAI_MODEL", "gpt-4o-mini") if model_type == "openai" else os.getenv("GEMINI_MODEL", "gemini-2.0-flash"))
        self._ready = False
        self._client = None

        # Initialize model client based on the selected model type
        if self.model_type == "gemini":
            self._initialize_gemini_client()
        elif self.model_type == "openai":
            self._initialize_openai_client()
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _initialize_gemini_client(self):
        try:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY", None)
            if api_key:
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(self.model_name)
                self._ready = True
        except Exception as e:
            print(f"Error initializing Gemini client: {e}")
            self._ready = False

    def _initialize_openai_client(self):
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_SECRET_KEY", None)
            if api_key:
                self._client = OpenAI(api_key=api_key)
                self._ready = True
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            self._ready = False

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate content from the selected model (either Gemini or OpenAI)."""
        prompt = str(system_prompt) + "\n\n" + str(user_prompt)

        if self._ready and self._client:
            try:
                if self.model_type == "gemini":
                    response = self._client.generate_content(prompt)
                    return getattr(response, "text", "").strip() or ""
                elif self.model_type == "openai":
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
        return f"[LLM-FALLBACK] {prompt[:200]}"


# For testing, the following part can be in another script or testing module

if __name__ == "__main__":
    client = LLMClient(model_type="openai")  # You can switch to "gemini" here

    system_prompt = "You are a concise math assistant."
    user_prompt = "What is 2+2? Answer in words."

    async def main():
        response = await client.generate(system_prompt, user_prompt)
        print("=== Response ===")
        print(response)

    asyncio.run(main())
