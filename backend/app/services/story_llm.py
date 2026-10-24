"""Optional story drafting providers. Calculations do not depend on an LLM."""

import os
import re

import httpx

from ..models import DraftText, Moment


INSTRUCTIONS = (
    "You are a sports newsroom DRAFT writer. Use only supplied facts. "
    "Do not invent details, quotes, skill judgments, video descriptions, "
    "statistics, or future outcomes. The data is synthetic. Keep it "
    "clearly labeled fictional. Write a punchy headline and a short "
    "two-sentence narration. Cite the fact IDs you relied on."
)


def generate_draft(moment: Moment) -> DraftText | None:
    """Return a structured draft, or None when the selected provider has no key.

    The caller handles provider failures and verifies the cited fact IDs.
    The default preserves existing OpenAI configuration. Select 'template'
    explicitly to prevent any LLM requests, or 'gemini' to use only Gemini.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider == "template":
        return None
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        return _gemini_draft(moment, key) if key else None
    if provider != "openai":
        raise ValueError("Unsupported LLM provider")
    if not os.getenv("OPENAI_API_KEY"):
        return None

    from openai import OpenAI

    with OpenAI(timeout=20.0, max_retries=0) as client:
        response = client.responses.parse(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=INSTRUCTIONS,
            input=f"Synthetic sports moment: {moment.model_dump_json()}",
            text_format=DraftText,
        )
    return response.output_parsed


def _gemini_draft(moment: Moment, key: str) -> DraftText:
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ValueError("Invalid Gemini model name")
    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "headline": {"type": "STRING"},
                "narration": {"type": "STRING"},
                "used_fact_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["headline", "narration", "used_fact_ids"],
        },
        "maxOutputTokens": 1024,
    }
    if model == "gemini-2.5-flash":
        # This model supports disabling thinking for a short rephrasing task;
        # leave other models' thinking defaults alone for API compatibility.
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}
    # Use the native generateContent API. Gemini's OpenAI-compatible endpoint
    # does not make OpenAI's Responses API interchangeable with this call.
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={
                "systemInstruction": {"parts": [{"text": INSTRUCTIONS}]},
                "contents": [{
                    "role": "user",
                    "parts": [{"text": f"Synthetic sports moment: {moment.model_dump_json()}"}],
                }],
                "generationConfig": generation_config,
            },
        )
        response.raise_for_status()
        payload = response.json()
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini returned no draft candidate")
    candidate = candidates[0]
    if not isinstance(candidate, dict) or candidate.get("finishReason") != "STOP":
        raise ValueError("Gemini did not return a complete draft")
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise ValueError("Gemini returned no draft text")
    text = "".join(
        part["text"] for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
        and part.get("thought") is not True
    )
    return DraftText.model_validate_json(text)
