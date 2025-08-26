# debug_test.py
from core.llm_client import LLMClient

# Test if LLM client works
llm = LLMClient()
test_prompt = "What is 2+2? Answer in one word."

try:
    response = llm.generate(test_prompt)
    print(f"✅ LLM Response: {response}")
except Exception as e:
    print(f"❌ LLM Error: {str(e)}")
    print("💡 This explains why decision engine defaults to 'clarify'")