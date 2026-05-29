"""
Repository layer — the only place the app talks to the database.

By funnelling persistence through these functions we get:
  - One place to add caching, retries, or change DB technology
  - Easy mocking in unit tests
  - A clear contract between business logic and storage

Each function takes either a session (for tests) or grabs one from
`get_session()`. Everything returns plain dicts or domain objects, never
SQLAlchemy result rows that would leak ORM details into the UI layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, desc

from db import get_session
from models import AuditLog, Kit, Scorecard, User


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_or_create_user(email: str, display_name: str | None = None) -> dict:
    """
    For Day 1, auth is "trust the email". Day 2 adds password verification.
    Returns a dict (id, email, display_name) so callers don't need to know
    about SQLAlchemy.
    """
    email = email.strip().lower()
    with get_session() as s:
        existing = s.scalar(select(User).where(User.email == email))
        if existing:
            return _user_to_dict(existing)
        user = User(email=email, display_name=display_name)
        s.add(user)
        s.flush()
        result = _user_to_dict(user)
    return result


def get_user_by_id(user_id: str) -> dict | None:
    with get_session() as s:
        u = s.get(User, user_id)
        return _user_to_dict(u) if u else None


def _user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "display_name": u.display_name,
        "created_at": u.created_at,
    }


# ---------------------------------------------------------------------------
# Kits
# ---------------------------------------------------------------------------

def save_kit(
    *,
    user_id: str,
    jd_text: str,
    resume_text: str,
    kit_json: dict,
    role_title: str | None = None,
    candidate_name: str | None = None,
) -> str:
    """Persist a generated kit and return its UUID."""
    with get_session() as s:
        kit = Kit(
            created_by=user_id,
            jd_text=jd_text,
            resume_text=resume_text,
            kit_json=kit_json,
            role_title=role_title or kit_json.get("jd_summary", "")[:240] or None,
            candidate_name=candidate_name or kit_json.get("candidate_summary", "")[:240] or None,
        )
        s.add(kit)
        s.add(AuditLog(user_id=user_id, action="kit.created", resource_id=kit.id))
        s.flush()
        kit_id = kit.id
    return kit_id


def list_kits_for_user(user_id: str, limit: int = 25) -> list[dict]:
    """Return the user's most-recent kits, newest first."""
    with get_session() as s:
        rows = s.scalars(
            select(Kit).where(Kit.created_by == user_id).order_by(desc(Kit.created_at)).limit(limit)
        ).all()
        return [_kit_to_dict(k) for k in rows]


def load_kit(kit_id: str) -> dict | None:
    with get_session() as s:
        k = s.get(Kit, kit_id)
        return _kit_to_dict(k, include_text=True) if k else None


def _kit_to_dict(k: Kit, *, include_text: bool = False) -> dict:
    out = {
        "id": k.id,
        "created_by": k.created_by,
        "role_title": k.role_title,
        "candidate_name": k.candidate_name,
        "kit_json": k.kit_json,
        "created_at": k.created_at,
    }
    if include_text:
        out["jd_text"] = k.jd_text
        out["resume_text"] = k.resume_text
    return out


# ---------------------------------------------------------------------------
# Scorecards
# ---------------------------------------------------------------------------

def save_scorecard(
    *,
    kit_id: str,
    user_id: str,
    scores_json: list[dict],
    weighted_total: float,
    max_possible: float,
    percentage: float,
) -> str:
    with get_session() as s:
        sc = Scorecard(
            kit_id=kit_id,
            filled_by=user_id,
            scores_json={"rows": scores_json},
            weighted_total=weighted_total,
            max_possible=max_possible,
            percentage=percentage,
            completed_at=datetime.now(timezone.utc),
        )
        s.add(sc)
        s.add(AuditLog(user_id=user_id, action="scorecard.completed", resource_id=sc.id))
        s.flush()
        sc_id = sc.id
    return sc_id


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def log_event(action: str, *, user_id: str | None = None, resource_id: str | None = None, metadata: dict | None = None) -> None:
    with get_session() as s:
        s.add(AuditLog(user_id=user_id, action=action, resource_id=resource_id, metadata_json=metadata))


def recent_audit_events(user_id: str | None = None, limit: int = 50) -> list[dict]:
    with get_session() as s:
        stmt = select(AuditLog).order_by(desc(AuditLog.occurred_at)).limit(limit)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        rows = s.scalars(stmt).all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "resource_id": r.resource_id,
                "metadata": r.metadata_json,
                "occurred_at": r.occurred_at,
            }
            for r in rows
        ]
