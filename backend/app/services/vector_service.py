import json
import math
import re
from collections import Counter
from datetime import datetime

import openai
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Entry, EntryEmbedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


_TOKEN_RE = re.compile(r"[a-z0-9']{2,}")


def _local_lite_embedding(text: str, *, dims: int = 256) -> list[float]:
    """
    Very lightweight local fallback (not a true semantic model):
    hashed bag-of-words into a fixed-length L2-normalized vector.
    """
    tokens = _TOKEN_RE.findall((text or "").lower())
    counts = Counter(tokens)
    vec = [0.0] * dims
    for tok, c in counts.items():
        idx = (hash(tok) % dims + dims) % dims
        vec[idx] += float(c)

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [v / norm for v in vec]
    return vec


def embed_text(text: str) -> tuple[str, list[float]]:
    """
    Returns (model_name, embedding_vector).
    Uses OpenAI embeddings when configured, otherwise a local-lite fallback.
    """
    cleaned = (text or "").strip()
    if settings.openai_api_key:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=cleaned,
        )
        vec = list(resp.data[0].embedding)
        return ("text-embedding-3-small", vec)

    vec = _local_lite_embedding(cleaned)
    return ("local-lite-v1", vec)


def get_or_create_entry_embedding(db: Session, entry: Entry) -> EntryEmbedding:
    existing = db.query(EntryEmbedding).filter(EntryEmbedding.entry_id == entry.id).first()
    if existing is not None:
        return existing

    model_name, vec = embed_text(entry.content)
    emb = EntryEmbedding(
        entry_id=entry.id,
        model=model_name,
        dims=len(vec),
        embedding_json=json.dumps(vec),
        created_at=datetime.utcnow(),
    )
    db.add(emb)
    db.commit()
    db.refresh(emb)
    return emb


def semantic_search_recent_entries(
    db: Session,
    *,
    query: str,
    k: int = 10,
    recent_limit: int = 500,
) -> list[tuple[Entry, float]]:
    model_name, qvec = embed_text(query)

    candidates = (
        db.query(Entry)
        .order_by(Entry.created_at.desc())
        .limit(recent_limit)
        .all()
    )

    scored: list[tuple[Entry, float]] = []
    for entry in candidates:
        emb = db.query(EntryEmbedding).filter(EntryEmbedding.entry_id == entry.id).first()
        if emb is None or not emb.embedding_json:
            emb = get_or_create_entry_embedding(db, entry)

        try:
            vec = json.loads(emb.embedding_json)
        except Exception:
            continue

        if emb.model != model_name:
            # Mixed models are allowed, but vectors may be incomparable.
            # We still attempt cosine if dims match; otherwise similarity=0.
            pass

        if not isinstance(vec, list):
            continue
        vec_f = [float(x) for x in vec]
        score = _cosine_similarity(qvec, vec_f)
        scored.append((entry, score))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[: max(1, min(int(k), 50))]

