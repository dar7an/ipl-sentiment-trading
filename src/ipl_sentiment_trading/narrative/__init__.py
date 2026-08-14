from __future__ import annotations

import os

from ipl_sentiment_trading.narrative.base import NarrativeProvider, NullNarrative


def narrative_credentials_present() -> bool:
    return bool(
        os.getenv("NARRATIVE_BASE_URL")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )


def build_narrative_provider(*, enabled: bool) -> NarrativeProvider | None:
    """Construct a provider only when explicitly enabled and credentials exist.

    Offline CLI/tests must call this with enabled=False so google-genai is never imported.
    """
    if not enabled:
        return None
    base = os.getenv("NARRATIVE_BASE_URL", "").strip()
    model = os.getenv("NARRATIVE_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"
    if base:
        from ipl_sentiment_trading.narrative.openai_compat import OpenAICompatNarrative

        return OpenAICompatNarrative(
            base_url=base,
            model=model,
            api_key=os.getenv("NARRATIVE_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        )
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    from ipl_sentiment_trading.narrative.gemini import GeminiNarrative

    return GeminiNarrative(api_key=api_key, model=model)


__all__ = [
    "NarrativeProvider",
    "NullNarrative",
    "build_narrative_provider",
    "narrative_credentials_present",
]
