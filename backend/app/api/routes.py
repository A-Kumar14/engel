import json
import logging
import tempfile
from pathlib import Path

import openai
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db import get_db
from app.models import Entry, EntryLink, Insight, Pointer
from app.schemas import (
    AutoLinkRequest,
    AutoLinkResponse,
    AutoTagRequest,
    AutoTagResponse,
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    EntryCreate,
    EntryLinkCreate,
    EntryLinkRead,
    EntryRead,
    EntryUpdate,
    HealthResponse,
    InsightCreate,
    InsightRead,
    PointerCreate,
    PointerRead,
    SemanticSearchResult,
    TranscriptResponse,
)
from app.services.insight_engine import build_weekly_insight
from app.services.sort_engine import suggest_sort
# Auth disabled — twilio_verify.py kept on disk for potential future use.
# from app.services.twilio_verify import check_sms_verification, start_sms_verification
from app.services.vector_service import embed_text, semantic_search_recent_entries

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.api_prefix)


@router.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@router.get("/entries", response_model=list[EntryRead])
def list_entries(db: Session = Depends(get_db)) -> list[Entry]:
    return (
        db.query(Entry)
        .options(selectinload(Entry.pointers))
        .order_by(Entry.created_at.desc())
        .all()
    )


@router.post("/entries", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: EntryCreate, db: Session = Depends(get_db)) -> Entry:
    entry = Entry(
        content=payload.content,
        source=payload.source,
        globe=payload.globe,
        ai_confidence=payload.ai_confidence,
    )

    for pointer in payload.pointers:
        entry.pointers.append(Pointer(label=pointer.label, source=pointer.source))

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}", response_model=EntryRead)
def update_entry(entry_id: int, payload: EntryUpdate, db: Session = Depends(get_db)) -> Entry:
    entry = (
        db.query(Entry)
        .options(selectinload(Entry.pointers))
        .filter(Entry.id == entry_id)
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, db: Session = Depends(get_db)) -> Response:
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/entries/{entry_id}/link", response_model=EntryLinkRead, status_code=status.HTTP_201_CREATED)
def link_entries(entry_id: int, payload: EntryLinkCreate, db: Session = Depends(get_db)) -> EntryLink:
    if entry_id == payload.to_entry_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot link an entry to itself",
        )

    from_entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if from_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    to_entry = db.query(Entry).filter(Entry.id == payload.to_entry_id).first()
    if to_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target entry not found")

    link = EntryLink(
        from_entry_id=entry_id,
        to_entry_id=payload.to_entry_id,
        link_type=payload.link_type,
    )

    try:
        db.add(link)
        db.commit()
        db.refresh(link)
        return link
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Link already exists (or violates link constraints)",
        )


@router.post("/entries/{entry_id}/pointers", response_model=PointerRead, status_code=status.HTTP_201_CREATED)
def add_pointer(entry_id: int, payload: PointerCreate, db: Session = Depends(get_db)) -> Pointer:
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    pointer = Pointer(entry_id=entry_id, label=payload.label, source=payload.source)
    db.add(pointer)
    db.commit()
    db.refresh(pointer)
    return pointer


@router.post("/entries/{entry_id}/auto-link", response_model=AutoLinkResponse, status_code=status.HTTP_201_CREATED)
def auto_link_entries(entry_id: int, payload: AutoLinkRequest, db: Session = Depends(get_db)) -> AutoLinkResponse:
    if not payload.related_entry_ids:
        return AutoLinkResponse(created=0, skipped=0, links=[])

    source = db.query(Entry).filter(Entry.id == entry_id).first()
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    created_links: list[EntryLink] = []
    skipped = 0

    for to_id in payload.related_entry_ids[:2]:
        if to_id == entry_id:
            skipped += 1
            continue

        target = db.query(Entry).filter(Entry.id == to_id).first()
        if target is None:
            skipped += 1
            continue

        link = EntryLink(from_entry_id=entry_id, to_entry_id=to_id, link_type=payload.link_type)
        try:
            db.add(link)
            db.commit()
            db.refresh(link)
            created_links.append(link)
        except IntegrityError:
            db.rollback()
            skipped += 1

    return AutoLinkResponse(
        created=len(created_links),
        skipped=skipped,
        links=[EntryLinkRead.model_validate(l) for l in created_links],
    )


@router.get("/entries/search/semantic", response_model=list[SemanticSearchResult])
def semantic_search_entries(
    q: str,
    k: int = 10,
    db: Session = Depends(get_db),
) -> list[SemanticSearchResult]:
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Query string 'q' is required")

    k = max(1, min(int(k), 50))
    results = semantic_search_recent_entries(db, query=q, k=k, recent_limit=500)

    return [
        SemanticSearchResult(entry=EntryRead.model_validate(entry), score=score)
        for entry, score in results
    ]


@router.get("/insights", response_model=list[InsightRead])
def list_insights(db: Session = Depends(get_db)) -> list[Insight]:
    return db.query(Insight).order_by(Insight.created_at.desc()).all()


@router.post("/insights", response_model=InsightRead, status_code=status.HTTP_201_CREATED)
def create_insight(payload: InsightCreate, db: Session = Depends(get_db)) -> Insight:
    insight = Insight(
        insight_type=payload.insight_type,
        title=payload.title,
        body=payload.body,
        evidence_summary=payload.evidence_summary,
        evidence_json=json.dumps(payload.evidence),
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return insight


@router.post("/insights/weekly", response_model=InsightRead, status_code=status.HTTP_201_CREATED)
def generate_weekly_insight(db: Session = Depends(get_db)) -> Insight:
    latest = build_weekly_insight(db)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough entry data to generate an insight",
        )

    db.add(latest)
    db.commit()
    db.refresh(latest)
    return latest


def _load_voice_doc_section(section: str) -> str:
    """Read a section from docs/voice.md at request time so edits propagate without redeploy."""
    voice_path = Path(__file__).resolve().parents[3] / "docs" / "voice.md"
    if not voice_path.exists():
        return ""
    text = voice_path.read_text(encoding="utf-8")
    # Extract content between ```markers after the section heading
    marker = f"### {section}"
    idx = text.find(marker)
    if idx == -1:
        return ""
    rest = text[idx:]
    start = rest.find("```\n")
    if start == -1:
        return ""
    end = rest.find("```", start + 4)
    if end == -1:
        return rest[start + 4:]
    return rest[start + 4:end].strip()


@router.post("/embed", response_model=EmbedResponse)
def embed_content(payload: EmbedRequest) -> EmbedResponse:
    try:
        _, vec = embed_text(payload.content)
        return EmbedResponse(embedding=vec)
    except Exception:
        logger.exception("Embedding failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Embedding failed.",
        )


@router.post("/auto-tag", response_model=AutoTagResponse)
def auto_tag_entry(payload: AutoTagRequest) -> AutoTagResponse:
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENROUTER_API_KEY is not configured on the server.",
        )

    system_prompt = _load_voice_doc_section("Auto-tagging addendum")
    if not system_prompt:
        system_prompt = (
            "You are tagging a journal entry. Return 2 to 4 lowercase tags as a JSON array. "
            "Prefer existing tags when a near-match exists. Do not tag emotions directly."
        )

    existing = payload.existing_tags[:30]
    user_content = f"Entry:\n{payload.content}"
    if existing:
        user_content += f"\n\nExisting tags (prefer these when a near-match exists):\n{json.dumps(existing)}"

    try:
        client = openai.OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            max_tokens=100,
        )
        raw = response.choices[0].message.content.strip()
        tags = json.loads(raw)
        if not isinstance(tags, list):
            tags = []
        tags = [t.lower().strip() for t in tags if isinstance(t, str) and t.strip()][:4]
        return AutoTagResponse(tags=tags)
    except Exception:
        logger.exception("Auto-tagging failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auto-tagging failed.",
        )


@router.post("/transcribe", response_model=TranscriptResponse)
async def transcribe_audio(audio: UploadFile = File(...), db: Session = Depends(get_db)) -> TranscriptResponse:
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GROQ_API_KEY is not configured on the server.",
        )

    try:
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=True) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp.flush()

            client = openai.OpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
            )
            with open(tmp.name, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=settings.groq_whisper_model,
                    file=audio_file,
                )

        transcript = transcription.text.strip()
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Whisper returned an empty transcript.",
            )

        related_ids: list[int] = []
        try:
            # Constrain predictive linking to a small candidate set from semantic search.
            candidates_scored = semantic_search_recent_entries(db, query=transcript, k=8, recent_limit=500)
            candidates = [{"id": e.id, "content": e.content} for e, _score in candidates_scored]
            suggestion = suggest_sort(transcript, candidates=candidates)
            related_ids = suggestion.related_entry_ids
        except Exception:
            logger.exception("Predictive linking candidate generation failed")
            suggestion = suggest_sort(transcript)

        return TranscriptResponse(
            transcript=transcript,
            suggested_globe=suggestion.globe,
            suggested_pointers=suggestion.pointers,
            confidence=suggestion.confidence,
            suggested_related_entry_ids=related_ids,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Transcription failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transcribe audio. Check server logs for details.",
        )


@router.post("/chat", response_model=ChatResponse)
def chat_with_ledger(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENROUTER_API_KEY is not configured on the server.",
        )

    question = payload.question.strip()

    # Retrieve relevant entries via semantic search
    results = semantic_search_recent_entries(db, query=question, k=8, recent_limit=500)

    if len(results) < 3:
        return ChatResponse(
            answer="You do not have enough entries for this. Write more.",
            cited_entry_ids=[e.id for e, _ in results],
        )

    # Build context from retrieved entries
    entry_lines = []
    cited_ids = []
    for entry, _score in results:
        date_str = entry.created_at.strftime("%B %d")
        globe_str = entry.globe or "unsorted"
        tags = ""
        if entry.pointers:
            tag_labels = [p.label for p in entry.pointers]
            tags = f" [tags: {', '.join(tag_labels)}]"
        entry_lines.append(f"- ID {entry.id}, {date_str}, {globe_str}{tags}: \"{entry.content}\"")
        cited_ids.append(entry.id)

    entries_block = "\n".join(entry_lines)

    # Load system prompt from voice doc
    base_prompt = _load_voice_doc_section("AI system prompt skeleton")
    if not base_prompt:
        base_prompt = (
            "You are the voice of a personal ledger. You are not a therapist, coach, advisor, or friend. "
            "You are a mirror. State facts from the data. Never offer advice or reassurance."
        )

    chat_addendum = _load_voice_doc_section("Chat synthesis addendum")
    if chat_addendum:
        base_prompt += "\n\n" + chat_addendum

    try:
        client = openai.OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": base_prompt},
                {
                    "role": "user",
                    "content": f"Retrieved entries:\n{entries_block}\n\nQuestion: {question}",
                },
            ],
            temperature=0.4,
            max_tokens=400,
        )
        answer = response.choices[0].message.content.strip()
        return ChatResponse(answer=answer, cited_entry_ids=cited_ids)
    except Exception:
        logger.exception("Chat synthesis failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat synthesis failed.",
        )


# Auth routes disabled. twilio_verify.py kept on disk for potential future use.
# @router.post("/auth/2fa/start") ...
# @router.post("/auth/2fa/verify") ...
