from core.llm_client import LLMClient
import os
import asyncio

async def test_llm_client():
    # Test if LLM client works
    model_type = os.getenv("MODEL_TYPE", "openai")
    llm = LLMClient(model_type=model_type)
    system_prompt = ""
    user_prompt = "Who came first, chicken or egg? Answer in one word."

    try:
        response = await llm.generate(system_prompt, user_prompt)  # Awaiting async method
        print(f"✅ LLM Response: {response}")
    except Exception as e:
        print(f"❌ LLM Error: {str(e)}")
        print("💡 This explains why decision engine defaults to 'clarify'")

if __name__ == "__main__":
    # Running the async test function
    asyncio.run(test_llm_client())
