# Interview Kit Generator

A web app that takes a **Job Description** and a **Candidate Resume** and produces a focused, ready-to-use interview kit for the interviewer — including tailored questions, skill-gap probes, and an interactive scorecard.

Built for the Fresher Hackathon — **Challenge #10: Interview Question and Scorecard Generator**.

---

## What it does

Given a JD and a CV, the app generates:

- **Role and candidate summaries** — quick context for the interviewer
- **Matched skills vs gap skills** — at-a-glance fit analysis
- **Technical questions** — role-relevant, each with the reasoning and the signal to look for
- **Behavioral questions** — same structure
- **Gap-probing questions** — targeted at specific skills missing or weak in the resume
- **Interviewer scorecard** — weighted criteria, live score totals, CSV export
- **Full kit export** — downloadable JSON for record-keeping or ATS import

Inputs can be **pasted directly** or **uploaded** as PDF / DOCX / TXT.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| UI / framework | Streamlit | Single-file Python app, fast to iterate, rich widgets out of the box |
| LLM | Google Gemini (via AI Studio free tier) | Free, no credit card, JSON-mode support |
| Resume / JD parsing | `pypdf`, `python-docx` | Handles common upload formats |
| Tables / export | `pandas` | Easy DataFrame → CSV |
| Config | `python-dotenv` | Keeps API keys out of code |

---

## Setup

```bash
git clone <this-repo>
cd interview-kit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Get a free Google AI Studio API key: https://aistudio.google.com/app/apikey

```bash
cp .env.example .env
# open .env and paste your key
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

You can also paste the API key directly in the sidebar instead of using `.env`.

---

## How to use

1. Paste or upload a **Job Description** on the left.
2. Paste or upload a **Resume** on the right.
3. Click **Generate Interview Kit**.

> **Quick demo:** the `samples/` folder contains a ready-to-use JD (Backend Engineer role) and a sample resume designed to surface both matched skills and real gaps. See `samples/README.md`.
4. The app validates the inputs, then produces the full kit.
5. During the interview, click into the **Score** column of the scorecard and enter 1–5 for each criterion. The weighted total updates live.
6. Click **Download Scorecard (CSV)** or **Download Full Kit (JSON)** to save results.

---

## Design decisions

- **Warn, don't block, on bad inputs.** Before generation, a lightweight LLM call classifies whether the documents actually look like a JD and a resume. If either looks off, the user sees a warning with a reason and can either fix it or override with "Generate anyway". This avoids the classic AI-product failure of producing confident output from garbage input, without frustrating legitimate edge cases (one-line JDs, unusual resume formats).
- **Structured JSON output.** The LLM is prompted with a strict schema and `response_mime_type=application/json`, so the UI can render reliably without text parsing.
- **Interactive scorecard, not just a static report.** The interviewer fills scores during/after the interview and the app computes a weighted total. CSV export means it integrates with any existing hiring workflow.
- **Session state for stability.** Streamlit reruns the whole script on every widget interaction. Storing the generated kit in `st.session_state` means editing a score cell doesn't wipe the results.
- **Free-tier model defaults.** The model selector defaults to `gemini-2.5-flash-lite`, which is the most reliable free-tier option. Other models are available in the sidebar but may hit quota limits.

---

## Assumptions

- Users have a Google account and can generate a free AI Studio API key.
- Job descriptions and resumes are text-based (or text-extractable PDFs/DOCX). Scanned image-only PDFs aren't supported in this prototype.
- The interviewer is the human-in-the-loop — the app suggests questions and weights but the interviewer's judgment is the source of truth.
- English-language documents. Other languages may work but are not tested.

## Limitations

- **No OCR** — scanned PDFs without a text layer return empty extracts.
- **Free-tier rate limits** — Gemini free tier allows ~15 requests/minute on the lite model; heavy demo traffic may hit 429 errors.
- **No persistence** — kits are not saved between sessions. Closing the tab loses unsaved scoring (download CSV to retain).
- **No authentication** — single-user prototype; not suitable for production multi-user deployment as-is.
- **LLM-generated content** — questions and gap analysis are model-generated and should be reviewed before use in a live interview.

---

## Next-step enhancements

- **Role templates** — preset prompts for SDE / Data / PM / Designer that bias the model toward role-specific question patterns.
- **PDF export** of the completed scorecard for sharing with hiring panels.
- **Multi-candidate comparison view** — side-by-side scoring for a single role.
- **Question difficulty levels** — let the interviewer tune for junior / mid / senior.
- **ATS integration** — push the JSON kit into Greenhouse / Lever / Workday.
- **Question bank persistence** — save commonly-used questions across kits.
- **Authentication + storage** so a team can collaborate on the same role.
- **Expanded sample library** — more JD + resume pairs covering different roles (Data, PM, Designer) beyond the current Backend Engineer sample.

---

## Project structure

```
interview-kit/
├── app.py                # Main Streamlit app
├── requirements.txt      # Python dependencies
├── .env.example          # Template for API key config
├── .gitignore
├── README.md
└── samples/
    ├── sample_jd.txt
    ├── sample_resume.txt
    └── README.md
```

---

## Author

Sudarshan Sharma — Fresher Hackathon submission.
