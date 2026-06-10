import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Entry, EntryLink, GlobeType, Insight, InsightType, Pointer

logger = logging.getLogger(__name__)


ENERGY_FRICTION_SYSTEM_PROMPT = """You analyze a user's short personal fragments to help them notice patterns.

Non-negotiables:
- No advice, no prescriptions, no diagnosis, no moralizing.
- Do not interpret the user's life; only describe patterns grounded in the text.
- Authority stays with the human. Suggestions are editable.
- Output at most ONE insight.

Focus specifically on Energy vs. Friction patterns:
- Co-occurrence: Energy and Friction in one fragment.
- Sequences: Friction leading to Energy (or Energy leading to Friction) across time.
- Correlations: specific pointers that repeatedly appear with red globe fragments.

Also analyze Linked Chains (clusters of linked fragments, ordered):
- For each chain, identify whether it shows Decreasing Friction (Progress), Increasing Friction (Burnout), or Neutral/Unclear.
- "Friction" tends to correspond to red; "Energy" tends to correspond to green; mixed can be transitional.

Return JSON only with this exact shape:
{
  "insight_type": "asymmetry" | "correlation" | "contradiction" | "drift" | "silence" | "reality_check" | "question",
  "title": "short, non-judgmental",
  "body": "2-4 sentences max, pattern-focused, no advice",
  "evidence_summary": "one sentence, factual and lightweight",
  "evidence": [
    {"entry_id": 123, "quote": "short quote <= 140 chars"}
  ]
}

Rules:
- Cite 2-4 evidence items max.
- Quotes must be exact substrings from the provided fragments.
- If evidence is weak or ambiguous, set insight_type="question" and ask one concrete question the user can answer by reviewing their own entries.
"""


def _build_chains(entry_ids: set[int], links: list[EntryLink]) -> list[list[int]]:
    # Build simple directed chains from roots (nodes with no incoming within subset).
    outgoing: dict[int, list[int]] = {}
    incoming_count: dict[int, int] = {i: 0 for i in entry_ids}
    for l in links:
        if l.from_entry_id in entry_ids and l.to_entry_id in entry_ids:
            outgoing.setdefault(l.from_entry_id, []).append(l.to_entry_id)
            incoming_count[l.to_entry_id] = incoming_count.get(l.to_entry_id, 0) + 1

    roots = [i for i, c in incoming_count.items() if c == 0 and i in outgoing]
    chains: list[list[int]] = []

    def walk(path: list[int], node: int, seen: set[int]) -> None:
        nxts = outgoing.get(node, [])
        if not nxts:
            if len(path) > 1:
                chains.append(path[:])
            return
        for nxt in nxts:
            if nxt in seen:
                continue
            seen.add(nxt)
            walk(path + [nxt], nxt, seen)
            seen.remove(nxt)

    for r in roots:
        walk([r], r, {r})

    # Deduplicate identical chains.
    uniq: list[list[int]] = []
    seen_keys: set[tuple[int, ...]] = set()
    for ch in chains:
        key = tuple(ch)
        if key not in seen_keys:
            seen_keys.add(key)
            uniq.append(ch)
    return uniq


def build_weekly_insight(db: Session) -> Insight | None:
    def _to_naive_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    now = datetime.utcnow()
    since = now - timedelta(days=7)

    # Pull recent entries and their pointers (used for correlations).
    entries: list[Entry] = (
        db.query(Entry)
        .order_by(Entry.created_at.desc())
        .all()
    )

    recent_entries = [e for e in entries if _to_naive_utc(e.created_at) >= since]
    if not recent_entries:
        return None

    # If no LLM configured, fall back to the previous minimal heuristic.
    if not settings.anthropic_api_key:
        # If there are linked chains, attempt a small deterministic "progress/burnout" read.
        recent_ids = {e.id for e in recent_entries}
        link_rows: list[EntryLink] = (
            db.query(EntryLink)
            .filter(EntryLink.from_entry_id.in_(list(recent_ids)))
            .all()
        )
        chains = _build_chains(recent_ids, link_rows)

        def friction_score(globe: GlobeType) -> float:
            if globe == GlobeType.RED:
                return 1.0
            if globe == GlobeType.MIXED:
                return 0.6
            if globe == GlobeType.GREEN:
                return 0.0
            return 0.5

        if chains:
            entry_map = {e.id: e for e in recent_entries}
            for ch in chains:
                if len(ch) < 3:
                    continue
                first = entry_map.get(ch[0])
                last = entry_map.get(ch[-1])
                mid = entry_map.get(ch[1]) if len(ch) > 1 else None
                if not first or not last:
                    continue

                start = friction_score(first.globe)
                end = friction_score(last.globe)
                if start - end >= 0.6:
                    evidence = [
                        {"entry_id": first.id, "quote": first.content[:140]},
                        {"entry_id": last.id, "quote": last.content[:140]},
                    ]
                    title = "A linked chain that eased"
                    via = f" via {mid.id}" if mid else ""
                    body = (
                        "One linked chain moves from friction toward energy over the week. "
                        "It starts heavier and ends lighter, which may be worth noticing."
                    )
                    return Insight(
                        insight_type=InsightType.CORRELATION,
                        title=title,
                        body=body,
                        evidence_summary=f"Chain {ch[0]} → {ch[-1]}{via} shifts from red/mixed toward green.",
                        evidence_json=json.dumps(evidence),
                    )

                if end - start >= 0.6:
                    evidence = [
                        {"entry_id": first.id, "quote": first.content[:140]},
                        {"entry_id": last.id, "quote": last.content[:140]},
                    ]
                    title = "A linked chain that tightened"
                    body = (
                        "One linked chain moves from energy toward friction over the week. "
                        "It starts lighter and ends heavier, which may be worth noticing."
                    )
                    return Insight(
                        insight_type=InsightType.CORRELATION,
                        title=title,
                        body=body,
                        evidence_summary=f"Chain {ch[0]} → {ch[-1]} shifts from green/mixed toward red.",
                        evidence_json=json.dumps(evidence),
                    )

        green_count = db.query(func.count(Entry.id)).filter(Entry.globe == GlobeType.GREEN).scalar() or 0
        red_count = db.query(func.count(Entry.id)).filter(Entry.globe == GlobeType.RED).scalar() or 0
        if green_count == 0 and red_count == 0:
            return None

        if green_count == red_count:
            return Insight(
                insight_type=InsightType.QUESTION,
                title="Balanced signals this week",
                body="Green and red entries are evenly matched. Open the latest entries together and decide what that balance means.",
                evidence_summary=f"{green_count} green entries and {red_count} red entries detected.",
                evidence_json="[]",
            )

        dominant_globe = "green" if green_count > red_count else "red"
        gap = abs(green_count - red_count)
        return Insight(
            insight_type=InsightType.ASYMMETRY,
            title=f"{dominant_globe.title()} globe is louder this week",
            body=f"The {dominant_globe} globe has {gap} more entries than the other globe. That difference may be worth reviewing, without forcing an interpretation.",
            evidence_summary=f"{green_count} green entries and {red_count} red entries detected.",
            evidence_json="[]",
        )

    # Build compact input JSON for the model.
    pointer_rows: list[Pointer] = (
        db.query(Pointer)
        .filter(Pointer.entry_id.in_([e.id for e in recent_entries]))
        .all()
    )
    pointers_by_entry: dict[int, list[str]] = {}
    for p in pointer_rows:
        pointers_by_entry.setdefault(p.entry_id, []).append(p.label)

    recent_ids = {e.id for e in recent_entries}
    link_rows: list[EntryLink] = (
        db.query(EntryLink)
        .filter(EntryLink.from_entry_id.in_(list(recent_ids)))
        .all()
    )

    chains = _build_chains(recent_ids, link_rows)
    chain_id_set = {eid for ch in chains for eid in ch}
    unlinked = [e for e in recent_entries if e.id not in chain_id_set]

    entry_map = {e.id: e for e in recent_entries}

    payload = {
        "linked_chains": [
            {
                "name": f"Chain {i + 1}",
                "path": ch,
                "entries": [
                    {
                        "id": eid,
                        "created_at": entry_map[eid].created_at.isoformat(),
                        "globe": entry_map[eid].globe.value if hasattr(entry_map[eid].globe, "value") else str(entry_map[eid].globe),
                        "content": entry_map[eid].content,
                        "pointers": pointers_by_entry.get(eid, []),
                    }
                    for eid in ch
                    if eid in entry_map
                ],
            }
            for i, ch in enumerate(chains[:8])
        ],
        "unlinked_entries": [
            {
                "id": e.id,
                "created_at": e.created_at.isoformat(),
                "globe": e.globe.value if hasattr(e.globe, "value") else str(e.globe),
                "content": e.content,
                "pointers": pointers_by_entry.get(e.id, []),
            }
            for e in sorted(unlinked, key=lambda x: x.created_at)
        ],
    }

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=700,
            system=ENERGY_FRICTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        raw = message.content[0].text.strip()
        parsed = json.loads(raw)

        insight_type_raw = str(parsed.get("insight_type", "question")).lower().strip()
        try:
            insight_type = InsightType(insight_type_raw)
        except Exception:
            insight_type = InsightType.QUESTION

        title = str(parsed.get("title", "")).strip()[:120]
        body = str(parsed.get("body", "")).strip()
        evidence_summary = str(parsed.get("evidence_summary", "")).strip()
        evidence = parsed.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []

        # Keep evidence small and safe.
        cleaned_evidence: list[dict] = []
        for item in evidence[:4]:
            if not isinstance(item, dict):
                continue
            entry_id = item.get("entry_id")
            quote = str(item.get("quote", "")).strip()
            if isinstance(entry_id, int) and quote:
                cleaned_evidence.append({"entry_id": entry_id, "quote": quote[:140]})

        if not title or not body or not evidence_summary:
            insight_type = InsightType.QUESTION
            title = title or "A small question about the week"
            body = body or "A pattern may be present, but the signal is thin. Skim your last few fragments and decide what feels most true."
            evidence_summary = evidence_summary or f"{len(recent_entries)} recent fragments reviewed."

        return Insight(
            insight_type=insight_type,
            title=title,
            body=body,
            evidence_summary=evidence_summary,
            evidence_json=json.dumps(cleaned_evidence),
        )

    except Exception:
        logger.exception("Weekly insight generation failed")
        # Fall back to a minimal, non-prescriptive question.
        return Insight(
            insight_type=InsightType.QUESTION,
            title="A small question about the week",
            body="Something may be forming, but the signal is unclear. Skim the last few fragments and decide what feels most true, without forcing a story.",
            evidence_summary=f"{len(recent_entries)} recent fragments reviewed.",
            evidence_json="[]",
        )
