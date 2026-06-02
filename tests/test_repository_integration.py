"""
Integration tests — exercise the repository layer against a real Postgres.

These tests are skipped when TEST_DATABASE_URL is not set so the unit-only
test run (used by the lint/test job that doesn't spin up a service container)
stays fast and dependency-free. In the integration-tests CI job, a Postgres
service container is started and TEST_DATABASE_URL points at it.

Marked with `@pytest.mark.integration` so they can be filtered:
    pytest -m integration   # run only these
    pytest -m "not integration"  # skip these
"""

import importlib
import os
import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Skip the whole module if there's no DB URL configured for tests.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="TEST_DATABASE_URL not set — integration tests skipped",
    ),
]


@pytest.fixture(scope="module", autouse=True)
def _bind_test_database():
    """
    Point the app's DB layer at the test Postgres for this module only.
    We override DATABASE_URL, force a re-import of db.py to rebuild the
    engine, then run Alembic migrations to create the schema fresh.
    """
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # type: ignore[arg-type]

    # Re-import db so the engine picks up the new URL.
    for mod in ("db", "repository", "models"):
        if mod in sys.modules:
            del sys.modules[mod]

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace(  # type: ignore[union-attr]
        "postgresql://", "postgresql+psycopg://", 1
    ))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="module")
def repo():
    return importlib.import_module("repository")


@pytest.fixture
def fresh_email():
    """Unique email per test so signups don't collide."""
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


# ---------------------------------------------------------------------------
# User lifecycle
# ---------------------------------------------------------------------------

def test_register_user_persists_to_database(repo, fresh_email):
    user = repo.register_user(fresh_email, "StrongPass123", "Test User")
    assert user["email"] == fresh_email
    assert user["display_name"] == "Test User"
    assert user["id"]


def test_register_then_authenticate_round_trip(repo, fresh_email):
    repo.register_user(fresh_email, "RoundTripPass1", None)
    user = repo.authenticate_user(fresh_email, "RoundTripPass1")
    assert user["email"] == fresh_email


def test_duplicate_registration_rejected(repo, fresh_email):
    repo.register_user(fresh_email, "FirstPass123", None)
    with pytest.raises(repo.UserAlreadyExists):
        repo.register_user(fresh_email, "SecondPass456", None)


def test_authenticate_with_wrong_password_rejected(repo, fresh_email):
    repo.register_user(fresh_email, "RightPassword12", None)
    with pytest.raises(repo.InvalidCredentials):
        repo.authenticate_user(fresh_email, "wrong-password")


def test_authenticate_unknown_email_rejected(repo):
    with pytest.raises(repo.InvalidCredentials):
        repo.authenticate_user("ghost-user@example.com", "any-password-99")


# ---------------------------------------------------------------------------
# Kit persistence and retrieval
# ---------------------------------------------------------------------------

def test_save_and_load_kit_round_trip(repo, fresh_email):
    user = repo.register_user(fresh_email, "KitTestPass1", None)
    kit_id = repo.save_kit(
        user_id=user["id"],
        jd_text="JD body",
        resume_text="Resume body",
        kit_json={"jd_summary": "role X", "candidate_summary": "candidate Y"},
        role_title="Riya — Acme / Backend Eng",
        candidate_name="Riya",
    )
    loaded = repo.load_kit(kit_id)
    assert loaded is not None
    assert loaded["role_title"] == "Riya — Acme / Backend Eng"
    assert loaded["kit_json"]["jd_summary"] == "role X"
    assert loaded["jd_text"] == "JD body"


def test_list_kits_is_user_scoped(repo):
    """A user only sees their own kits — not another user's."""
    user_a = repo.register_user(f"a-{uuid.uuid4().hex[:6]}@ex.com", "PassA12345", None)
    user_b = repo.register_user(f"b-{uuid.uuid4().hex[:6]}@ex.com", "PassB12345", None)
    repo.save_kit(user_id=user_a["id"], jd_text="x", resume_text="y", kit_json={}, role_title="A-kit")
    repo.save_kit(user_id=user_b["id"], jd_text="x", resume_text="y", kit_json={}, role_title="B-kit")

    a_kits = repo.list_kits_for_user(user_a["id"])
    b_kits = repo.list_kits_for_user(user_b["id"])
    assert all(k["role_title"] == "A-kit" for k in a_kits)
    assert all(k["role_title"] == "B-kit" for k in b_kits)


def test_delete_kit_removes_owned_kit(repo, fresh_email):
    """A user can delete their own kit; it disappears from their list."""
    user = repo.register_user(fresh_email, "DeletePass123", None)
    kit_id = repo.save_kit(user_id=user["id"], jd_text="x", resume_text="y", kit_json={}, role_title="To-delete")
    assert repo.load_kit(kit_id) is not None

    deleted = repo.delete_kit(kit_id, user["id"])
    assert deleted is True
    assert repo.load_kit(kit_id) is None
    assert all(k["id"] != kit_id for k in repo.list_kits_for_user(user["id"]))


def test_delete_kit_cannot_delete_another_users_kit(repo):
    """Deleting someone else's kit is a no-op — owner scoping holds."""
    owner = repo.register_user(f"own-{uuid.uuid4().hex[:6]}@ex.com", "OwnerPass123", None)
    attacker = repo.register_user(f"atk-{uuid.uuid4().hex[:6]}@ex.com", "AttackPass12", None)
    kit_id = repo.save_kit(user_id=owner["id"], jd_text="x", resume_text="y", kit_json={}, role_title="Owned")

    assert repo.delete_kit(kit_id, attacker["id"]) is False
    assert repo.load_kit(kit_id) is not None  # still there


# ---------------------------------------------------------------------------
# Scorecard persistence + upsert
# ---------------------------------------------------------------------------

def test_upsert_scorecard_inserts_then_updates(repo, fresh_email):
    user = repo.register_user(fresh_email, "ScorecardPass1", None)
    kit_id = repo.save_kit(user_id=user["id"], jd_text="x", resume_text="y", kit_json={})

    # First call — inserts a new row
    repo.upsert_scorecard_progress(
        kit_id=kit_id, user_id=user["id"],
        scores_json=[{"criterion": "SQL", "weight": 5, "Score": 3, "Notes": "ok"}],
        weighted_total=15.0, max_possible=25.0, percentage=60.0,
    )
    first = repo.get_latest_scorecard(kit_id, user["id"])
    assert first is not None
    assert first["percentage"] == 60.0

    # Second call — updates the same row, doesn't create a duplicate
    repo.upsert_scorecard_progress(
        kit_id=kit_id, user_id=user["id"],
        scores_json=[{"criterion": "SQL", "weight": 5, "Score": 5, "Notes": "excellent"}],
        weighted_total=25.0, max_possible=25.0, percentage=100.0,
    )
    second = repo.get_latest_scorecard(kit_id, user["id"])
    assert second is not None
    assert second["id"] == first["id"]   # same row, upserted
    assert second["percentage"] == 100.0


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def test_audit_log_records_kit_creation(repo, fresh_email):
    user = repo.register_user(fresh_email, "AuditPass12345", None)
    repo.save_kit(user_id=user["id"], jd_text="x", resume_text="y", kit_json={})

    events = repo.recent_audit_events(user["id"])
    actions = [e["action"] for e in events]
    assert "user.registered" in actions
    assert "kit.created" in actions
