"""
Pure-logic helpers for the Interview Kit Generator.

This module deliberately has no Streamlit dependency, so it can be unit-tested
in isolation and reused by future non-Streamlit consumers (e.g. a FastAPI
backend or a CLI tool). Keeping UI concerns out of here is a small step toward
the production architecture described in PRODUCTION_ARCHITECTURE.md.
"""

from io import BytesIO

from docx import Document
from pypdf import PdfReader


def extract_text(uploaded_file) -> str:
    """
    Extract plain text from an uploaded file.

    Accepts any object with a `.name` attribute and a `.read()` method that
    returns bytes (matches Streamlit's UploadedFile interface, but also
    works with simple fakes in tests).

    Returns an empty string for None inputs or unsupported file types so
    callers can safely chain on the return value.
    """
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if name.endswith(".docx"):
        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    return ""


def compute_score_summary(rows):
    """
    Recreate the weighted-score math the UI shows.

    Each row is a dict with at least `weight` (int 1-5) and optionally
    `score` (int 1-5 or None). Only scored rows contribute to the max
    possible, so the percentage is always meaningful in the moment.

    Returns: (weighted_total, max_possible, percentage, scored_count, total_count)
    """
    total_count = len(rows)
    scored_rows = [r for r in rows if r.get("score") is not None]
    weighted_total = sum(r["weight"] * r["score"] for r in scored_rows)
    max_possible = sum(r["weight"] * 5 for r in scored_rows)
    percentage = (weighted_total / max_possible * 100) if max_possible else 0.0
    return weighted_total, max_possible, percentage, len(scored_rows), total_count
