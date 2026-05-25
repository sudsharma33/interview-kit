# Demo Script

A ~2-minute walkthrough for the hackathon presentation. Practice this once aloud before you present.

---

## Before you start (setup checklist)

- [ ] Streamlit app running (`streamlit run app.py`)
- [ ] Browser window already open at http://localhost:8501
- [ ] API key already pasted in the sidebar — **do not type it live**
- [ ] `samples/sample_jd.txt` and `samples/sample_resume.txt` open in Finder, ready to drag
- [ ] Generate one kit beforehand and **leave it loaded** as a backup, in case the live demo fails
- [ ] Close every other tab, notification, and Slack — no leaks

---

## The 2-minute walkthrough

### Opening hook (15s)
> "Talent Acquisition teams spend 20 to 40 minutes per role preparing a tailored interview kit — they read the JD, read the candidate's resume, draft role-specific questions, identify skill gaps, and build a scorecard. I built a tool that does all of that in under a minute."

### Show the inputs (20s)
> "Two inputs: a job description on the left, a resume on the right. Both accept paste or upload — PDF, DOCX, or TXT."

*Upload `sample_jd.txt` on the left, then `sample_resume.txt` on the right.*

> "I have a sample pair ready — a Backend Engineer role and a fictional candidate with three years of Python experience. The sample is deliberately mixed: she's strong on the fundamentals but has clear gaps."

### Click Generate (10s)
*Click Generate Interview Kit.*

> "Before generation, the tool runs a quick validation — it asks the LLM whether the inputs actually look like a JD and a resume. That's a guard against the classic AI failure of producing confident output from garbage input."

### Walk through Summary tab (25s)
> "The Summary tab gives the interviewer instant context."

*Point to the role card.*
> "Role overview, candidate overview."

*Point to the skill pills.*
> "Matched skills in green — Python, Django, PostgreSQL, REST, CI/CD. Gap skills in amber — Go, Kafka, AWS at the depth they need, observability. So the interviewer walks in already knowing where to probe."

### Walk through Questions tab (20s)
*Switch to Questions tab.*

> "Three categories. Technical, behavioral, and — most useful — gap-probing questions, tied to the specific skills she's missing."

*Click into Gap Probes sub-tab. Read one question aloud.*
> "Notice each question comes with the reasoning and the signal to listen for. The interviewer isn't just told what to ask — they're told why, and what a good answer sounds like."

### Walk through Scorecard tab (25s)
*Switch to Scorecard tab.*

> "The scorecard is interactive — the interviewer fills scores 1 to 5 during the interview."

*Click into 2 or 3 score cells, type numbers, hit Tab.*

> "Weighted total updates live. Progress bar shows how many criteria are still pending. And everything exports — scorecard as CSV for the hiring panel, full kit as JSON for ATS integration."

### Close (10s)
> "End to end: text in, structured interview kit out, with the interviewer staying in the loop on every judgment call. Hours of TA capacity back per week."

---

## Q&A — likely questions and pre-built answers

**"Why Streamlit over React?"**
> "Single-file Python, no separate frontend or backend, no build step. Best ROI for an 8-hour budget. React would have burned two hours on scaffolding before any business logic."

**"Why Gemini?"**
> "Genuine free tier, no credit card. The provider is swappable in roughly ten lines — the architecture isn't locked in."

**"How do you stop the model from hallucinating?"**
> "Three guardrails. First, a pre-flight validator that classifies the inputs. Second, JSON-mode with a strict schema — the model can't return free-form text, so I get a contract. Third, the interviewer is always the final judge — the app suggests, the human decides."

**"What testing did you do?"**
> "Manual exploratory testing — adversarial inputs, deliberately broken cases. I caught and fixed real bugs that way, like stale validation warnings and a scorecard reset issue. In a production version I'd add pytest unit tests, a contract test on the JSON schema, and an eval set of expected gap skills to guard against prompt regressions."

**"What development methodology?"**
> "Iterative incremental — build a minimal end-to-end scaffold first, then small feature cycles: build, test, commit, repeat. Closer to Agile than waterfall, but with no team and an 8-hour budget the right honest label is iterative-incremental."

**"What would you do with more time?"**
> Pick *two or three* — don't list everything:
> - Role templates (SDE, Data, PM) for role-specific question patterns
> - Multi-candidate comparison view for a single role
> - ATS integration to push the JSON kit into Greenhouse or Lever

**"What's the cost?"**
> "Free tier — zero. Two LLM calls per kit. At production scale on paid tier, roughly a tenth of a cent per kit on flash-lite."

**"What if the LLM is down?"**
> "Validation degrades gracefully — if the validator call fails, it assumes inputs are valid and proceeds. If the main generation fails, the error is surfaced clearly to the user with the underlying message. No silent failures."

---

## If something breaks live

- **Generation 429 / quota error** → switch model in sidebar to `gemini-flash-latest`. If still failing, fall back to the pre-loaded kit you generated beforehand.
- **Browser stuck** → refresh. Session state will keep the loaded kit.
- **Streamlit crashed** → in terminal, hit ↑ then Enter to restart. Takes 3 seconds.
- **Nothing works** → talk through the README's "Design decisions" section instead. Substance over spectacle.

---

## What NOT to do

- Don't type the API key live — paste it before you start
- Don't list every "next-step enhancement" — pick 2 or 3
- Don't apologize for limitations — frame them as deliberate scope choices
- Don't mention the leaked keys, ever
- Don't use the word "just" ("I just built…") — it undersells the work
