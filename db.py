"""
Database engine + session factory.

Single source of truth for how the rest of the app talks to Postgres.
Other modules import `get_session` (a context manager) and never touch the
engine directly. That makes it easy to swap to a test database in pytest
fixtures and to add connection pooling tuning in one place.

The engine is created LAZILY on first use, not at import time. This lets
tests (and any tooling) import `db.py` without a DATABASE_URL configured —
the engine is built the first time a session is requested, at which point
the missing env var becomes a clear, actionable error.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

# Eager-load .env so any importer of this module gets DATABASE_URL when
# running locally with a .env file. In CI / containers, environment variables
# are injected by the runner, so a missing .env is fine.
load_dotenv()


def _build_url() -> str:
    """
    Read DATABASE_URL from environment. Normalize the scheme so SQLAlchemy
    uses the modern psycopg (v3) driver even if the URL came back from
    Render with the bare `postgresql://` prefix.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to your .env file (local dev), "
            "or to your hosting environment's secrets (Render / CI)."
        )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _connect_args(url: str) -> dict:
    """
    Require SSL when pointing at a hosted Postgres (Render, Supabase, etc.)
    but not for the in-cluster docker-compose Postgres which doesn't have it
    enabled. Detection is host-based: anything with a hostname containing
    'render.com' or 'supabase' or 'amazonaws' or 'neon.tech' gets SSL.
    """
    needs_ssl = any(p in url for p in ("render.com", "supabase", "amazonaws", "neon.tech"))
    return {"sslmode": "require"} if needs_ssl else {}


# Lazy singletons — populated on first call to get_engine().
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    """Build the engine on first call; reuse the singleton thereafter."""
    global _engine, _SessionLocal
    if _engine is None:
        url = _build_url()
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            connect_args=_connect_args(url),
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def _get_session_factory() -> sessionmaker:
    if _SessionLocal is None:
        get_engine()  # populates _SessionLocal as a side-effect
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def get_session() -> Session:
    """Yield a SQLAlchemy session that commits on success, rolls back on error."""
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
