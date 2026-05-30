# Interview Kit Generator

[![CI/CD Pipeline](https://github.com/sudsharma33/interview-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/sudsharma33/interview-kit/actions/workflows/ci.yml)
[![Live App](https://img.shields.io/badge/live-interview--kit--pr.streamlit.app-brightgreen)](https://interview-kit-pr.streamlit.app)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![Postgres](https://img.shields.io/badge/database-PostgreSQL-336791)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

A production-grade web app that takes a **Job Description** and a **Candidate Resume** and produces a focused, ready-to-use interview kit for the interviewer — tailored questions, skill-gap probes, and a live interactive scorecard. Backed by Postgres, gated by a 7-stage CI/CD pipeline, deployed on every green build.

Built for the **IGS Edgex Fresher Hackathon — Challenge #10: Interview Question and Scorecard Generator**.

**Live demo:** [interview-kit-pr.streamlit.app](https://interview-kit-pr.streamlit.app)
**Repo:** [github.com/sudsharma33/interview-kit](https://github.com/sudsharma33/interview-kit)

---

## What it does

Given a JD and a CV, the app produces:

- **Role and candidate summaries** — quick context for the interviewer
- **Matched skills vs gap skills** — colour-coded pills, scannable at a glance
- **Technical questions** — role-relevant, each with the reasoning and the signal to look for
- **Behavioral questions** — same structure
- **Gap-probing questions** — targeted at specific skills missing or weak in the resume
- **Interviewer scorecard** — weighted criteria, live score totals, auto-saved to Postgres
- **Full kit export** — downloadable JSON including the interviewer's filled scores

Inputs accept **paste or upload** (PDF / DOCX / TXT). Generated kits are **persisted per user** — sign back in any time and resume scoring from where you left off.

---

## What "production-grade" means here

| Production concern | How it's addressed |
|---|---|
| **Real database** | PostgreSQL on Render with managed backups, SSL, connection pooling |
| **Schema migrations** | Alembic — every schema change is versioned and replay-able |
| **Authentication** | Email + bcrypt-hashed passwords, session-based login |
| **Multi-user data isolation** | Every kit and scorecard is scoped to the creating user's UUID |
| **Audit log** | Append-only `audit_log` table records sign-ins, kit creation, scorecard updates |
| **Automated testing** | 31 pytest tests — 22 unit + 9 integration against a real Postgres service container in CI |
| **Static analysis** | ruff (lint), mypy (types), bandit (security) — all gating CI |
| **CI/CD pipeline** | 7-stage GitHub Actions: lint → typecheck → security → unit → integration → build → promote-to-production |
| **Production deploy** | Streamlit Cloud, gated by a `production` branch that only receives commits that pass all 7 CI stages |
| **Container portability** | Dockerfile + docker-compose for local stack; same image deploys to Render/Kubernetes/ECS |
| **Secret hygiene** | API keys and DB credentials in `.env` (gitignored) and Streamlit Cloud Secrets — never in code |

---

## Architecture overview

### What's built today (live in production)

```
USERS  →  Streamlit Cloud  →  PostgreSQL (Render)
              │                       ↑
              ├──→ Google Gemini API  │  bcrypt auth · SQLAlchemy ORM · Alembic
              │                       │  audit log · per-user scoping
              ↑
              └─ deployed from `production` branch
                   ↑
                   └─ promoted only when all 7 CI/CD stages pass
                        ↑
                        └─ developer pushes to `main` on GitHub
```

Detailed two-slide visual in `Architecture.pptx` (Desktop). Production scaling roadmap in [`PRODUCTION_ARCHITECTURE.md`](PRODUCTION_ARCHITECTURE.md).

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| **UI** | Streamlit (1.42+) | Single-process Python app, no separate frontend/backend, fast to iterate |
| **LLM** | Google Gemini via AI Studio free tier (`gemini-2.5-flash-lite`) | Free tier, JSON-mode output, provider-agnostic abstraction |
| **Database** | PostgreSQL 16 (Render managed) | ACID, JSONB for kit payloads, ready for multi-tenancy |
| **ORM + migrations** | SQLAlchemy 2.0 + Alembic | Type-hinted models, versioned schema changes |
| **Auth** | bcrypt + Streamlit `session_state` | Industry-standard password hashing, lightweight session management |
| **Parsing** | `pypdf` + `python-docx` | Handles the three most common JD/CV upload formats |
| **CI/CD** | GitHub Actions, 7-stage pipeline | Lint, typecheck, security, unit, integration, build, deploy gate |
| **Testing** | pytest + pytest-cov + Postgres service container in CI | Unit + integration in the same suite |
| **Container** | Docker + docker-compose | Portability proof; full local stack via `docker compose up` |
| **Deploy** | Streamlit Community Cloud (`production` branch) | Free, auto-redeploys on push, TLS terminated |

---

## Setup

### Run locally

```bash
git clone https://github.com/sudsharma33/interview-kit
cd interview-kit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file at the repo root:

```env
GOOGLE_API_KEY=your_key_from_https://aistudio.google.com/app/apikey
DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DBNAME
```

Apply the database schema:

```bash
alembic upgrade head
```

Run the app:

```bash
streamlit run app.py
```

Opens at http://localhost:8501.

### Run via Docker (full stack with Postgres)

```bash
docker compose up
```

Starts Postgres and the app together in containers. App at http://localhost:8501. No local Python required.

---

## How to use

1. **Sign in or create an account** with an email and a password (≥ 8 characters).
2. **Paste or upload** a Job Description (left) and a Candidate Resume (right).
3. **Click Generate Interview Kit.** The app validates the inputs (warns if either doesn't look like a JD/CV), then asks Gemini to produce a structured kit.
4. **Read the Summary, Questions, and Scorecard tabs.**
5. **Score the candidate live** in the Scorecard tab. Scores auto-save to Postgres on every change.
6. **Download** the scorecard as CSV (for Excel/Sheets) or the full kit as JSON (with your scores embedded).
7. **Come back later.** Sign in again. The sidebar shows your recent kits — click any one to resume scoring.

---

## Project structure

```
interview-kit/
├── app.py                       # Main Streamlit app (UI + orchestration)
├── auth.py                      # Sign-in / sign-up UI + session gating
├── db.py                        # SQLAlchemy engine + session factory (lazy init)
├── models.py                    # ORM models: User, Kit, Scorecard, AuditLog
├── repository.py                # All database queries (the only place SQL happens)
├── parsing.py                   # PDF/DOCX/TXT extraction + scoring math (pure logic)
├── requirements.txt
├── pyproject.toml               # ruff / mypy / bandit / pytest config
├── Dockerfile                   # Multi-stage build, non-root user, healthcheck
├── docker-compose.yml           # Local stack: app + Postgres in one command
├── alembic.ini                  # Alembic config
├── alembic/                     # Schema migration scripts
├── .github/workflows/ci.yml     # 7-stage CI/CD pipeline
├── tests/
│   ├── test_parsing.py             # Unit tests (no DB)
│   ├── test_auth.py                # Password hashing + validation unit tests
│   └── test_repository_integration.py  # Integration tests against real Postgres
├── samples/
│   ├── sample_jd.txt               # Backend Engineer JD for quick demos
│   └── sample_resume.txt           # Fictional candidate with mixed match/gap profile
├── USER_STORIES.md              # Formal user stories with acceptance criteria
├── PRODUCTION_ARCHITECTURE.md   # Target architecture for enterprise scale
└── README.md                    # This file
```

---

## CI/CD pipeline

Every push to `main` runs the 7-stage pipeline in GitHub Actions:

1. **Lint** — `ruff check` enforces style + catches common bugs
2. **Type check** — `mypy` verifies static type annotations
3. **Security scan** — `bandit` looks for security anti-patterns
4. **Unit tests** — `pytest -m "not integration"` runs 22 tests in seconds, no DB needed
5. **Integration tests** — `pytest -m integration` runs against a Postgres service container in CI
6. **Build** — Docker image build verification (proves the app packages cleanly)
7. **Promote** — if and only if all prior stages pass, `main` is fast-forwarded to the `production` branch

Streamlit Cloud watches `production` and auto-deploys on every update. **Bad code never reaches production.**

CI status badge at the top of this README is live — green means the pipeline passed on the latest commit.

---

## Design decisions

- **Server-side API key.** The Gemini API key is held in Streamlit Cloud Secrets and never sent to the visitor's browser. The sidebar key field is empty; the value is merged server-side before the LLM call.
- **JSON-mode LLM output.** Gemini is invoked with `response_mime_type=application/json` and a strict schema in the prompt. The UI renders structured fields directly — no fragile text parsing.
- **Two temperatures.** Main generation uses 0.4 (some variety across runs). Input validation uses 0.1 (near-deterministic classification).
- **Pre-flight validator.** Before the main generation, a small LLM call classifies inputs as "looks like a JD?" / "looks like a CV?". Warns and lets the user override; doesn't block.
- **Auto-save scorecard.** Scores are hashed and persisted to Postgres on every change, but only when the hash changes — keystroke-level reruns don't trigger redundant DB writes.
- **Pure-logic module.** `parsing.py` has no Streamlit dependency, so it's unit-testable in isolation and reusable by a future FastAPI backend.
- **Repository pattern.** All DB queries go through `repository.py` — easy to mock in tests, easy to swap storage later.

---

## Assumptions

- Users have a Google account to generate a free AI Studio API key.
- Job descriptions and resumes are text-based (or text-extractable PDFs/DOCX). Scanned image-only PDFs aren't supported in this prototype.
- The interviewer is the human-in-the-loop — the app suggests questions and weights but the interviewer's judgment is the source of truth.
- English-language documents. Other languages may work but are not tested.

## Limitations

- **No OCR** — scanned PDFs without a text layer return empty extracts.
- **Free-tier rate limits** — Gemini free tier allows ~15 requests/minute on the lite model.
- **Streamlit Cloud cold-start** — first request after idle takes ~30 sec.
- **Single tenant** — no organisation-level isolation yet; would add `tenant_id` columns + Postgres row-level security for true multi-tenancy.
- **No end-to-end UI tests** — backend covered by pytest, UI flows are manual. Playwright is the next layer (documented as "next-step" in the test plan).

---

## Next-step enhancements

- **Role templates** — preset prompts for SDE / Data / PM / Designer
- **Multi-candidate comparison view** — score multiple candidates against one role
- **ATS integration** — push JSON kit into Greenhouse / Lever / Workday via webhooks
- **Microsoft Entra ID SSO** — OIDC alongside email/password (Azure app registration already done; pending one-day deeper integration)
- **Playwright E2E tests** — automate the UI flows currently in the manual column of the test plan
- **PDF export** — full-kit PDF for non-technical reviewers

---

## Testing artifacts

- **`Test_Plan.xlsx`** — full QA test plan: 7 user stories, 34 acceptance criteria, 29 test scenarios, 31 test cases (Excel)
- **`USER_STORIES.md`** — same content in markdown for repo-side review
- **`tests/`** — 31 automated tests run on every push via CI

---

## Author

Sudarshan Sharma — IGS Edgex Fresher Hackathon submission, May 2026.
