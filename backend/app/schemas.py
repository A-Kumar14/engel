from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import GlobeType, InsightType


class PointerBase(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    source: str = Field(default="ai", max_length=16)


class PointerCreate(PointerBase):
    pass


class PointerRead(PointerBase):
    id: int

    model_config = {"from_attributes": True}


class EntryCreate(BaseModel):
    content: str = Field(min_length=1)
    source: str = Field(default="text", max_length=32)
    globe: GlobeType = GlobeType.UNSORTED
    ai_confidence: str | None = Field(default=None, max_length=16)
    pointers: list[PointerCreate] = []


class EntryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, max_length=32)
    globe: GlobeType | None = None
    ai_confidence: str | None = Field(default=None, max_length=16)


class EntryRead(BaseModel):
    id: int
    content: str
    source: str
    globe: GlobeType
    ai_confidence: str | None
    created_at: datetime
    pointers: list[PointerRead]

    model_config = {"from_attributes": True}


class InsightCreate(BaseModel):
    insight_type: InsightType
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1)
    evidence_summary: str = Field(min_length=1)
    evidence: list[dict] = Field(default_factory=list)


class InsightRead(BaseModel):
    id: int
    insight_type: InsightType
    title: str
    body: str
    evidence_summary: str
    evidence: list[dict] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    transcript: str
    suggested_globe: str
    suggested_pointers: list[str]
    confidence: float
    suggested_related_entry_ids: list[int] = Field(default_factory=list)


class EntryLinkCreate(BaseModel):
    to_entry_id: int
    link_type: str = Field(default="related", min_length=1, max_length=32)


class EntryLinkRead(BaseModel):
    id: int
    from_entry_id: int
    to_entry_id: int
    link_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    app: str


class AutoLinkRequest(BaseModel):
    related_entry_ids: list[int] = Field(default_factory=list)
    link_type: str = Field(default="related", min_length=1, max_length=32)


class AutoLinkResponse(BaseModel):
    created: int
    skipped: int
    links: list[EntryLinkRead]


class SemanticSearchResult(BaseModel):
    entry: EntryRead
    score: float


class AutoTagRequest(BaseModel):
    content: str = Field(min_length=1)
    existing_tags: list[str] = Field(default_factory=list)


class AutoTagResponse(BaseModel):
    tags: list[str]


class EmbedRequest(BaseModel):
    content: str = Field(min_length=1)


class EmbedResponse(BaseModel):
    embedding: list[float]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    cited_entry_ids: list[int] = Field(default_factory=list)


class TwoFAStartRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)


class TwoFAStartResponse(BaseModel):
    status: str = Field(default="ok")
    debug_code: str | None = None


class TwoFAVerifyRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=32)
    code: str = Field(min_length=6, max_length=6)


class TwoFAVerifyResponse(BaseModel):
    ok: bool


class WaitlistSubscribeRequest(BaseModel):
    email: EmailStr


class WaitlistSubscribeResponse(BaseModel):
    status: str
    message: str
