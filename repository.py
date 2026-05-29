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

import bcrypt
from sqlalchemy import select, desc

from db import get_session
from models import AuditLog, Kit, Scorecard, User


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_or_create_user(email: str, display_name: str | None = None) -> dict:
    """
    Passwordless helper kept only for the initial demo seed user. New users
    flowing through the UI must use `register_user()` instead.
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


class UserAlreadyExists(Exception):
    """Raised when sign-up is attempted with an email that's already taken."""


class InvalidCredentials(Exception):
    """Raised when sign-in fails due to wrong email or password."""


def _hash_password(plain: str) -> str:
    """bcrypt with a per-password salt. Cost factor 12 is the 2024 sweet spot."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def register_user(email: str, password: str, display_name: str | None = None) -> dict:
    """
    Create a new user with a bcrypt-hashed password.
    Raises UserAlreadyExists if the email is taken.
    """
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Please enter a valid email address.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    with get_session() as s:
        if s.scalar(select(User).where(User.email == email)):
            raise UserAlreadyExists(email)
        user = User(
            email=email,
            display_name=(display_name or "").strip() or None,
            password_hash=_hash_password(password),
        )
        s.add(user)
        s.flush()
        s.add(AuditLog(user_id=user.id, action="user.registered", resource_id=user.id))
        result = _user_to_dict(user)
    return result


def authenticate_user(email: str, password: str) -> dict:
    """
    Verify an email + password combination. Returns the user dict on success;
    raises InvalidCredentials on any failure. Deliberately gives the same
    error message for "no such user" and "wrong password" to avoid leaking
    which emails exist.
    """
    email = email.strip().lower()
    with get_session() as s:
        u = s.scalar(select(User).where(User.email == email))
        if not u or not _verify_password(password, u.password_hash or ""):
            raise InvalidCredentials("Email or password is incorrect.")
        s.add(AuditLog(user_id=u.id, action="user.signed_in", resource_id=u.id))
        return _user_to_dict(u)


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


def upsert_scorecard_progress(
    *,
    kit_id: str,
    user_id: str,
    scores_json: list[dict],
    weighted_total: float,
    max_possible: float,
    percentage: float,
) -> str:
    """
    Save or update the user's in-progress scorecard for a given kit.

    One scorecard row per (kit_id, user_id) — overwriting earlier progress.
    This is the right shape for "auto-save while the interviewer scores":
    we don't want a new row on every keystroke, but we do want the latest
    state to survive page reloads or app restarts.
    """
    with get_session() as s:
        existing = s.scalar(
            select(Scorecard).where(
                Scorecard.kit_id == kit_id, Scorecard.filled_by == user_id
            )
        )
        if existing:
            existing.scores_json = {"rows": scores_json}
            existing.weighted_total = weighted_total
            existing.max_possible = max_possible
            existing.percentage = percentage
            # only mark completed once every row has a non-null score
            if scores_json and all(r.get("Score") is not None for r in scores_json):
                existing.completed_at = datetime.now(timezone.utc)
            sc_id = existing.id
            action = "scorecard.updated"
        else:
            sc = Scorecard(
                kit_id=kit_id,
                filled_by=user_id,
                scores_json={"rows": scores_json},
                weighted_total=weighted_total,
                max_possible=max_possible,
                percentage=percentage,
            )
            s.add(sc)
            s.flush()
            sc_id = sc.id
            action = "scorecard.started"
        s.add(AuditLog(user_id=user_id, action=action, resource_id=sc_id))
    return sc_id


def get_latest_scorecard(kit_id: str, user_id: str) -> dict | None:
    """
    Return the most recent scorecard the user has for this kit, or None.

    Used by the UI to pre-fill the Score and Notes columns when a kit is
    re-opened from history, so the interviewer's previous progress is
    restored exactly as they left it.
    """
    with get_session() as s:
        sc = s.scalar(
            select(Scorecard)
            .where(Scorecard.kit_id == kit_id, Scorecard.filled_by == user_id)
            .order_by(desc(Scorecard.created_at))
            .limit(1)
        )
        if not sc:
            return None
        return {
            "id": sc.id,
            "kit_id": sc.kit_id,
            "filled_by": sc.filled_by,
            "rows": sc.scores_json.get("rows", []) if sc.scores_json else [],
            "weighted_total": float(sc.weighted_total) if sc.weighted_total is not None else None,
            "max_possible": float(sc.max_possible) if sc.max_possible is not None else None,
            "percentage": float(sc.percentage) if sc.percentage is not None else None,
            "completed_at": sc.completed_at,
        }


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
