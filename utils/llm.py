"""
llm.py - Gemini LLM Setup
=========================
Centralised place to initialise the Gemini model used by all agents.
Swap the model name here to upgrade/downgrade globally.
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load .env file so GOOGLE_API_KEY is available
load_dotenv()

def get_llm(temperature: float = 0.3, model: str = "gemini-1.5-flash") -> ChatGoogleGenerativeAI:
    """
    Returns a configured Gemini LLM instance.

    Args:
        temperature: Controls creativity (0 = deterministic, 1 = creative).
                     Agents that need facts use low values; critic uses higher.
        model:       Gemini model name. Defaults to gemini-1.5-flash (stable & free).

    Returns:
        ChatGoogleGenerativeAI instance ready to use with LangChain.

    Interview note:
        We use a factory function so every agent can independently tune its
        temperature without touching environment variables.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY not found. "
            "Copy .env.example → .env and add your key from https://aistudio.google.com/app/apikey"
        )
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key,
    )
