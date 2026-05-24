# 🎯 Interview Question & Scorecard Generator

A Streamlit app that takes a **Job Description** + **Candidate Resume** and generates a tailored interview kit:
- Role + candidate summaries
- Matched skills vs gap skills
- Technical, behavioral, and gap-probing questions
- An interactive scorecard with weighted scoring
- CSV / JSON export

Built for the Fresher Hackathon — Challenge #10.

## Stack
- **Streamlit** — UI
- **Google Gemini (free via AI Studio)** — LLM
- **pypdf / python-docx** — resume + JD parsing
- **pandas** — scorecard

## Setup

```bash
cd ~/Desktop/interview-kit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Get a free API key: https://aistudio.google.com/app/apikey

```bash
cp .env.example .env
# edit .env and paste your key
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

## Assumptions & Limitations
- LLM-generated questions — quality depends on model + input clarity.
- Resume parsing is text-only (no OCR for image-based PDFs).
- Scorecard weights are model-suggested; interviewer can override.

## Next-step Enhancements
- PDF export of completed scorecard
- Multi-candidate comparison view
- ATS / Greenhouse integration
- Question bank with difficulty levels
- Role templates (SDE, Data, PM, etc.)
