"""Configuration and safe provider selection for the unified AI Companion.

AI keys stay on the FastAPI server. The teammate's provider classes and
fact-verification engine stay in fan-companion/ unchanged. No network check is
performed by the status endpoint: a configured key may still be invalid.
"""
from __future__ import annotations

import os
from typing import Literal

PROVIDERS = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}
PROVIDER_LABELS = {"gemini": "Gemini", "openai": "OpenAI", "anthropic": "Claude"}


def companion_ai_status() -> dict:
    """Public non-secret config summary; never return a key or its value."""
    enabled = os.getenv("COMPANION_ENABLE_LLM", "").strip().lower() == "true"
    provider = os.getenv("LLM_PROVIDER", "template").strip().lower()
    if not enabled:
        return {
            "available": False, "provider": None,
            "message": "AI is disabled on the server. Using offline demo replies.",
        }
    if provider not in PROVIDERS:
        return {
            "available": False, "provider": None,
            "message": ("Choose an AI provider in the backend configuration "
                        "(gemini, openai or anthropic). Offline demo replies are active."),
        }
    if not any(os.getenv(key, "").strip() for key in PROVIDERS[provider]):
        return {
            "available": False, "provider": PROVIDER_LABELS[provider],
            "message": (f"{PROVIDER_LABELS[provider]} is selected, but its server-side "
                        "API key is missing. Offline demo replies are active."),
        }
    return {
        "available": True,
        "provider": PROVIDER_LABELS[provider],
        "message": (f"{PROVIDER_LABELS[provider]} is configured for AI chat. "
                    "Connectivity and quota are checked when a reply is requested."),
    }


def configured_backend():
    """Construct exactly the provider selected by LLM_PROVIDER.

    The original fan-companion helper chooses by whichever key exists first;
    for the integrated app, the user's explicitly configured provider wins.
    Provider constructors can fail (missing package/config), in which case
    we return a reason rather than silently pretending AI was used.
    """
    status = companion_ai_status()
    if not status["available"]:
        return None, status["message"]
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    try:
        from companion.llm import AnthropicBackend, GeminiBackend, OpenAIBackend

        cls = {
            "gemini": GeminiBackend,
            "openai": OpenAIBackend,
            "anthropic": AnthropicBackend,
        }[provider]
        return cls(), None
    except Exception:
        return None, "The configured AI model could not start. Showing the offline demo reply."
