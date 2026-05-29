"""
SQLAlchemy ORM models for the Interview Kit Generator.

Schema rationale (matches PRODUCTION_ARCHITECTURE.md):
  - users           — authenticated identities (Day 2 adds password hash + sessions)
  - kits            — every generated kit, with the model's raw JSON output
  - scorecards      — interviewer-filled scores against a kit
  - audit_log       — append-only record of every state-changing action

Multi-tenancy is deferred to a future migration (a `tenant_id` column on
each row + Postgres row-level security policies). Captured in
PRODUCTION_ARCHITECTURE.md Phase 4.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # set in Day 2
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    kits: Mapped[list[Kit]] = relationship(back_populates="created_by_user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Kit(Base):
    __tablename__ = "kits"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    kit_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # raw model output
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    created_by_user: Mapped[User] = relationship(back_populates="kits")
    scorecards: Mapped[list[Scorecard]] = relationship(back_populates="kit", cascade="all, delete-orphan")


class Scorecard(Base):
    __tablename__ = "scorecards"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    kit_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("kits.id"), nullable=False, index=True)
    filled_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    scores_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    weighted_total: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    max_possible: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    kit: Mapped[Kit] = relationship(back_populates="scorecards")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
