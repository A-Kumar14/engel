import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

SORT_SYSTEM_PROMPT = """You are sorting a personal fragment into one of three categories:
- green: positive, alive, energizing
- red: negative, stuck, draining
- mixed: genuinely ambivalent, belongs to both

You suggest only. The user always has final say.

Also suggest 1-3 short pointer tags (lowercase, no #) that capture the key themes.

Optionally suggest 1-2 existing entry IDs that are semantically related to the fragment.
Only suggest links when there is a clear bridge in topic/theme (not just both being "negative").
If nothing is clearly related, return an empty list.

Return JSON only, with this exact shape:
{
  "globe": "green" | "red" | "mixed",
  "pointers": ["tag1", "tag2"],
  "confidence": 0.0 to 1.0,
  "related_entry_ids": [123, 456]
}

Do not add commentary. Do not give advice. Do not interpret meaning.
Classify based on emotional tone and energy direction only."""


@dataclass
class SortSuggestion:
    globe: str = "mixed"
    pointers: list[str] = field(default_factory=list)
    confidence: float = 0.5
    related_entry_ids: list[int] = field(default_factory=list)


def suggest_sort(transcript: str, *, candidates: list[dict] | None = None) -> SortSuggestion:
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set, returning default suggestion")
        return SortSuggestion()

    try:
        user_content = transcript
        if candidates:
            # Constrain suggestions to a small candidate set.
            user_content = json.dumps({"fragment": transcript, "candidates": candidates})

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            system=SORT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = message.content[0].text.strip()
        parsed = json.loads(raw)

        globe = parsed.get("globe", "mixed")
        if globe not in ("green", "red", "mixed"):
            globe = "mixed"

        pointers = parsed.get("pointers", [])
        if not isinstance(pointers, list):
            pointers = []
        pointers = [str(p).lower().strip() for p in pointers[:5]]

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        related_ids = parsed.get("related_entry_ids", [])
        if not isinstance(related_ids, list):
            related_ids = []
        cleaned_related: list[int] = []
        for x in related_ids[:2]:
            try:
                cleaned_related.append(int(x))
            except Exception:
                continue
        # If candidates were provided, force IDs to be from that set.
        if candidates:
            allowed = {int(c.get("id")) for c in candidates if isinstance(c, dict) and "id" in c}
            cleaned_related = [i for i in cleaned_related if i in allowed]

        return SortSuggestion(globe=globe, pointers=pointers, confidence=confidence, related_entry_ids=cleaned_related)

    except Exception:
        logger.exception("Sort suggestion failed")
        return SortSuggestion()
