"""Centralized Groq chat-model setup for all agents."""

import os
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load .env file so GROQ_API_KEY is available.
load_dotenv()
_active_model: Optional[str] = None
_fallback_models = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")


def is_provider_key_configured() -> bool:
    """Return whether a non-placeholder Groq API key is available."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(api_key and not api_key.lower().startswith("your_"))


def get_response_text(response: Any) -> str:
    """Normalize LangChain text responses across provider versions."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_blocks = []
        for block in content:
            if isinstance(block, str):
                text_blocks.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                text_blocks.append(block["text"])
        return "\n".join(text_blocks)
    return str(content)


def get_llm(
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> ChatGroq:
    """
    Return a configured Groq chat model.

    Args:
        temperature: Controls creativity (0 = deterministic, 1 = creative).
                     Agents that need facts use low values; critic uses higher.
        model:       Groq model name. Defaults to GROQ_MODEL or openai/gpt-oss-20b.

    Returns:
        ChatGroq instance ready to use with LangChain.

    Interview note:
        We use a factory function so every agent can independently tune its
        temperature without touching environment variables.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not is_provider_key_configured():
        raise EnvironmentError(
            "GROQ_API_KEY not found. Copy .env.example to .env and add a key "
            "from https://console.groq.com/keys."
        )
    model_name = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
    options: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
        "timeout": 20,
        "max_retries": 0,
        "temperature": temperature,
    }
    if model_name.startswith("qwen/"):
        options["reasoning_format"] = "parsed"
    return ChatGroq(**options)


def invoke_with_fallback(messages: Any, temperature: float = 0.3) -> Any:
    """Try the configured Groq model, then known alternatives on failure."""
    global _active_model

    if not is_provider_key_configured():
        raise EnvironmentError(
            "GROQ_API_KEY is not configured. Add a valid key to .env to enable "
            "Groq analysis; local sample-database analytics remain available."
        )

    configured_model = os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
    models = list(
        dict.fromkeys(
            model
            for model in (_active_model, configured_model, *_fallback_models)
            if model
        )
    )
    last_error = None
    for model_name in models:
        try:
            response = get_llm(temperature=temperature, model=model_name).invoke(
                messages
            )
            _active_model = model_name
            return response
        except Exception as error:
            last_error = error
            message = str(error).casefold()
            if any(
                marker in message
                for marker in (
                    "401",
                    "403",
                    "invalid api key",
                    "authentication_error",
                )
            ):
                break

    raise RuntimeError(
        f"Groq failed with the configured and fallback models: {last_error}"
    ) from last_error
