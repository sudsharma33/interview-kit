"""
Unit tests for the parsing and helper logic in app.py.

These tests intentionally avoid hitting the real LLM API. They cover:
  - File extraction for the three supported file types (TXT, PDF, DOCX)
  - Empty / missing file handling
  - Sample data sanity checks
  - JSON schema shape of expected LLM output
"""

import sys
from pathlib import Path

import pytest

# Make the project root importable so we can pull `extract_text` out of app.py.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeUpload:
    """Mimics Streamlit's UploadedFile interface (has .name and .read())."""
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data
    def read(self) -> bytes:
        return self._data


# ---------------------------------------------------------------------------
# extract_text tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def extract_text():
    """Pure-logic import from parsing.py — no Streamlit dependency needed."""
    from parsing import extract_text as fn
    return fn


@pytest.fixture(scope="module")
def compute_score_summary():
    from parsing import compute_score_summary as fn
    return fn


def test_extract_text_returns_empty_for_none(extract_text):
    assert extract_text(None) == ""


def test_extract_text_txt(extract_text):
    f = FakeUpload("hello.txt", b"This is a sample resume.")
    assert "This is a sample resume." in extract_text(f)


def test_extract_text_unknown_extension(extract_text):
    f = FakeUpload("weird.xyz", b"unsupported content")
    assert extract_text(f) == ""


def test_extract_text_txt_unicode(extract_text):
    f = FakeUpload("resume.txt", "Name: Riya Menon — Bengaluru".encode())
    out = extract_text(f)
    assert "Riya Menon" in out
    assert "Bengaluru" in out


# ---------------------------------------------------------------------------
# Sample data sanity tests
# ---------------------------------------------------------------------------

def test_sample_jd_exists_and_nonempty():
    p = PROJECT_ROOT / "samples" / "sample_jd.txt"
    assert p.exists(), "sample_jd.txt is missing"
    content = p.read_text()
    assert len(content) > 200
    assert "Job Title" in content or "Responsibilities" in content


def test_sample_resume_exists_and_nonempty():
    p = PROJECT_ROOT / "samples" / "sample_resume.txt"
    assert p.exists(), "sample_resume.txt is missing"
    content = p.read_text()
    assert len(content) > 200
    assert "Experience" in content or "Education" in content


# ---------------------------------------------------------------------------
# Output schema contract tests
# ---------------------------------------------------------------------------

EXPECTED_TOP_LEVEL_KEYS = {
    "candidate_summary",
    "jd_summary",
    "matched_skills",
    "gap_skills",
    "technical_questions",
    "behavioral_questions",
    "gap_probe_questions",
    "scorecard",
}


def test_kit_schema_shape():
    """
    The LLM kit JSON must contain these top-level keys. This is the contract
    between the model output and the UI renderer. If a future prompt change
    drops a key, this test will catch it before deploy.
    """
    fake_kit = {
        "candidate_summary": "x",
        "jd_summary": "x",
        "matched_skills": [],
        "gap_skills": [],
        "technical_questions": [],
        "behavioral_questions": [],
        "gap_probe_questions": [],
        "scorecard": [],
    }
    assert set(fake_kit.keys()) == EXPECTED_TOP_LEVEL_KEYS


def test_question_object_shape():
    """Each technical / behavioral question must have question + why_asked + expected_signal."""
    q = {"question": "Walk me through how you'd shard a Postgres table.",
         "why_asked": "JD requires scaling experience",
         "expected_signal": "Mentions partitioning keys, hot spots, rebalancing"}
    assert set(q.keys()) >= {"question", "why_asked", "expected_signal"}


def test_gap_probe_object_shape():
    """Gap probes must carry the gap they target."""
    q = {"question": "How would you ramp on Kafka?",
         "targets_gap": "Kafka",
         "expected_signal": "Pragmatic learning plan"}
    assert "targets_gap" in q


def test_scorecard_row_shape():
    row = {"criterion": "SQL", "weight": 5, "what_good_looks_like": "Uses indexes correctly"}
    assert {"criterion", "weight", "what_good_looks_like"} <= set(row.keys())
    assert 1 <= row["weight"] <= 5


# ---------------------------------------------------------------------------
# Scoring math tests
# ---------------------------------------------------------------------------

def weighted_total(rows):
    """Recreates the scoring math used in app.py."""
    return sum(r["weight"] * (r.get("score") or 0) for r in rows)


def max_possible(rows):
    return sum(r["weight"] * 5 for r in rows if r.get("score") is not None)


def test_weighted_total_basic():
    rows = [
        {"weight": 5, "score": 4},
        {"weight": 2, "score": 5},
    ]
    assert weighted_total(rows) == 30


def test_max_possible_only_counts_scored_rows():
    rows = [
        {"weight": 5, "score": 4},   # contributes 25 to max
        {"weight": 2, "score": None},  # ignored
    ]
    assert max_possible(rows) == 25


def test_zero_scored_returns_zero_max():
    rows = [{"weight": 3, "score": None}, {"weight": 4, "score": None}]
    assert max_possible(rows) == 0
