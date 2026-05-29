"""
Unit tests for password hashing and the auth contracts.

These tests don't talk to Postgres — they exercise the pure-Python pieces
of the auth flow (hashing, verification, validation rules) so they run in
milliseconds inside CI without needing a database fixture.

Integration tests that hit a real test database live in
tests/test_repository_integration.py (added on Day 3).
"""

import importlib

import pytest

repo = importlib.import_module("repository")


def test_password_hash_is_not_plain_text():
    h = repo._hash_password("CorrectHorse9")
    assert h != "CorrectHorse9"
    assert h.startswith("$2b$") or h.startswith("$2a$"), "should be bcrypt"


def test_password_verification_round_trip():
    h = repo._hash_password("CorrectHorse9")
    assert repo._verify_password("CorrectHorse9", h) is True
    assert repo._verify_password("wrong-password", h) is False


def test_password_verification_handles_empty_hash():
    assert repo._verify_password("anything", "") is False
    assert repo._verify_password("anything", None) is False  # type: ignore[arg-type]


def test_password_verification_handles_garbage_hash():
    assert repo._verify_password("anything", "not-a-bcrypt-hash") is False


def test_two_hashes_of_same_password_are_different():
    """bcrypt salts make every hash unique even for identical inputs."""
    assert repo._hash_password("CorrectHorse9") != repo._hash_password("CorrectHorse9")


def test_hash_handles_unicode_password():
    pw = "pässwørd-€-12345"
    h = repo._hash_password(pw)
    assert repo._verify_password(pw, h)


# ---------------------------------------------------------------------------
# Validation rules embedded in register_user — tested without touching DB.
# We patch get_session to a no-op so the validation logic is exercised
# without writing to Postgres.
# ---------------------------------------------------------------------------

class _FakeSession:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def scalar(self, *a, **kw): return None
    def add(self, *a, **kw): pass
    def flush(self): pass


@pytest.fixture
def patch_session(monkeypatch):
    monkeypatch.setattr(repo, "get_session", lambda: _FakeSession())


def test_register_user_rejects_short_password(patch_session):
    with pytest.raises(ValueError, match="at least 8 characters"):
        repo.register_user("test@example.com", "short", None)


def test_register_user_rejects_invalid_email(patch_session):
    with pytest.raises(ValueError, match="valid email"):
        repo.register_user("not-an-email", "GoodPassword123", None)


def test_register_user_rejects_empty_email(patch_session):
    with pytest.raises(ValueError):
        repo.register_user("", "GoodPassword123", None)
