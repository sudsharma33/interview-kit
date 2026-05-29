"""
Database engine + session factory.

Single source of truth for how the rest of the app talks to Postgres.
Other modules import `get_session` (a context manager) and never touch the
engine directly. That makes it easy to swap to a test database in pytest
fixtures and to add connection pooling tuning in one place.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Eager-load .env so any importer of this module gets DATABASE_URL without
# having to call load_dotenv() themselves.
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
            "DATABASE_URL is not set. Add it to your .env file or to "
            "your hosting environment's secrets."
        )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _connect_args(url: str) -> dict:
    """
    Require SSL when pointing at a hosted Postgres (Render, Supabase, etc.)
    but not for the in-cluster docker-compose Postgres which doesn't have it
    enabled. Detection is host-based: anything with a hostname containing
    'render.com' or 'supabase' or 'amazonaws' gets sslmode=require.
    """
    needs_ssl = any(p in url for p in ("render.com", "supabase", "amazonaws", "neon.tech"))
    return {"sslmode": "require"} if needs_ssl else {}


# `pool_pre_ping=True` keeps long-lived connections alive across Render's
# idle timeouts. `pool_size`/`max_overflow` are sized for a single Streamlit
# process — bump these when the app is split into a real backend service.
_url = _build_url()
engine = create_engine(
    _url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    connect_args=_connect_args(_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Session:
    """Yield a SQLAlchemy session that commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
