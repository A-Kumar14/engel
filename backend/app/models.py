from datetime import datetime
from enum import Enum

import json

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GlobeType(str, Enum):
    GREEN = "green"
    RED = "red"
    MIXED = "mixed"
    UNSORTED = "unsorted"


class InsightType(str, Enum):
    ASYMMETRY = "asymmetry"
    CORRELATION = "correlation"
    CONTRADICTION = "contradiction"
    DRIFT = "drift"
    SILENCE = "silence"
    REALITY_CHECK = "reality_check"
    QUESTION = "question"


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="text")
    globe: Mapped[GlobeType] = mapped_column(
        SqlEnum(
            GlobeType,
            native_enum=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=GlobeType.UNSORTED,
    )
    ai_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    pointers: Mapped[list["Pointer"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
    )

    outgoing_links: Mapped[list["EntryLink"]] = relationship(
        back_populates="from_entry",
        cascade="all, delete-orphan",
        foreign_keys="EntryLink.from_entry_id",
    )
    incoming_links: Mapped[list["EntryLink"]] = relationship(
        back_populates="to_entry",
        cascade="all, delete-orphan",
        foreign_keys="EntryLink.to_entry_id",
    )

    embedding: Mapped["EntryEmbedding | None"] = relationship(
        cascade="all, delete-orphan",
        uselist=False,
        primaryjoin="Entry.id==EntryEmbedding.entry_id",
    )


class Pointer(Base):
    __tablename__ = "pointers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="ai")

    entry: Mapped[Entry] = relationship(back_populates="pointers")


class EntryLink(Base):
    __tablename__ = "entry_links"
    __table_args__ = (
        CheckConstraint("from_entry_id != to_entry_id", name="chk_entry_links_not_self"),
        UniqueConstraint("from_entry_id", "to_entry_id", name="uq_entry_links_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    from_entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    to_entry_id: Mapped[int] = mapped_column(ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, default="related")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    from_entry: Mapped[Entry] = relationship(
        "Entry",
        foreign_keys=[from_entry_id],
        back_populates="outgoing_links",
    )
    to_entry: Mapped[Entry] = relationship(
        "Entry",
        foreign_keys=[to_entry_id],
        back_populates="incoming_links",
    )


class EntryEmbedding(Base):
    __tablename__ = "entry_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="local-lite-v1")
    dims: Mapped[int] = mapped_column(nullable=False, default=0)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entry: Mapped[Entry] = relationship("Entry")


class WaitlistSubscriber(Base):
    __tablename__ = "waitlist_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    confirm_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    insight_type: Mapped[InsightType] = mapped_column(
        SqlEnum(
            InsightType,
            native_enum=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def evidence(self) -> list[dict]:
        try:
            parsed = json.loads(self.evidence_json or "[]")
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
