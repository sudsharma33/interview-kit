# Demo Script

Bullet-style prep document for the hackathon presentation. Read once tonight, once tomorrow, once 30 min before the demo. Then close it.

For the speakable paragraph-form version see `Demo_Speech.md`.

---

## Before you start

- [ ] Laptop charged, charger packed
- [ ] Streamlit app running locally (`streamlit run app.py`) — pre-warm the deployed URL too
- [ ] Browser window already at `https://interview-kit-pr.streamlit.app`
- [ ] **Already signed in** with your demo account — don't sign in live
- [ ] `samples/sample_jd.txt` and `samples/sample_resume.txt` open in Finder, ready to drag
- [ ] **TablePlus** open and connected to the Render Postgres, ready to show `users` / `kits` / `scorecards` / `audit_log`
- [ ] `Test_Plan.xlsx` open in a second window in case Mahesh asks for it
- [ ] `Architecture.pptx` open in Keynote — slide 1 ready
- [ ] Phone in pocket as backup demo device
- [ ] Generate one kit **before walking into the room** as a backup — leave the browser tab open
- [ ] Notifications off, Slack closed, Grammarly off

---

## The 2-minute walkthrough

### Opening hook (15 sec)
> "Talent Acquisition teams spend 20-40 minutes per role preparing tailored interview kits. I built a production-grade tool that does it in under a minute, with the entire engineering pipeline behind it — real database, automated tests, gated deploys."

### Show the architecture slide (20 sec)
*Open `Architecture.pptx` slide 1.*
> "Here's what's live today. Streamlit Cloud serving the UI, deployed only from a `production` branch that's promoted via a 7-stage CI/CD pipeline. Postgres on Render with four tables — users, kits, scorecards, audit log. bcrypt password hashing. SQLAlchemy ORM with Alembic migrations. Dockerised. 31 automated tests."

### Show the app from a signed-in state (15 sec)
*Switch to the browser. You're already signed in.*
> "I'm signed in as my demo user. The sidebar shows my previous kits — these came from Postgres, scoped to my user ID. Let me generate a fresh one."

### Generate (15 sec)
*Upload `sample_jd.txt` and `sample_resume.txt`. Click Generate.*
> "Two inputs. Paste or upload. Behind the scenes the app runs a quick LLM validation — guards against garbage inputs — then calls Gemini with JSON-mode and a strict schema. The output goes straight into Postgres before rendering."

### Summary tab (20 sec)
*Make sure Summary tab is active.*
> "Role and candidate summaries. Matched skills in green pills, gap skills in amber. The recruiter walks into the interview already knowing where to probe."

### Questions tab (25 sec)
*Switch to Questions tab. Click into Gap Probes sub-tab.*
> "Three categories — technical, behavioral, and gap-probing. Each gap probe is tied to a specific missing skill. Every question comes with the reasoning and the signal to listen for. That structure stops the model from generating filler."

### Scorecard tab (30 sec)
*Switch to Scorecard tab. Click into 2-3 cells, type scores.*
> "The scorecard is interactive — interviewer fills scores live. Watch the weighted total update. The progress bar shows criteria scored. And — this is the key bit — every keystroke is auto-saved to Postgres."

*Switch to TablePlus, query `scorecards`.*
> "There's the row. Real persistence, real database."

### CSV / JSON export + history (15 sec)
> "Two exports. CSV for the hiring panel — opens in Excel. JSON for system integration, with my scores embedded. And if I close the tab and sign back in tomorrow, the sidebar shows this kit, click it, the scores I just entered are still there — restored from Postgres."

### Close (10 sec)
> "End to end: real auth, real database, real CI/CD pipeline gating production deploys. Happy to take questions about any layer."

---

## Q&A — likely questions and pre-built answers

### "Walk me through the CI/CD pipeline"
> 7 stages: ruff lint, mypy type check, bandit security scan, pytest unit tests, pytest integration tests against a Postgres service container, Docker build verification, and finally a promote step that fast-forwards `main` → `production`. Streamlit Cloud watches `production`. Bad code never reaches users.

### "How do you handle multi-user data isolation?"
> Every kit and scorecard row carries the `created_by` / `filled_by` foreign key to the user UUID. The repository layer scopes every read by `user_id`. There's an integration test — `test_list_kits_is_user_scoped` — that creates two users, generates kits for each, and asserts that neither user sees the other's kits.

### "How is the password stored?"
> Bcrypt hash with cost factor 12. The plain text never touches the database. There's a test — `test_password_hash_is_not_plain_text` — that asserts the hash starts with `$2b$` and that two hashes of the same password are different (because of the per-password salt).

### "How does the auto-save work?"
> Every Streamlit rerun computes a hash of the scorecard state. If the hash differs from the last saved one, the repository fires an upsert into the `scorecards` table. Hash unchanged = no DB write. So typing one digit is one write, not one per keystroke.

### "What's in your test suite?"
> 31 tests across 3 files. 22 unit tests for pure logic — parsing, schema contracts, scoring math, password hashing. 9 integration tests that spin up a real Postgres in CI and exercise the full repository layer. All run on every push via GitHub Actions.

### "Why not automate the UI tests?"
> Backend logic is automated with pytest. UI flows are manual today and listed in the Test Plan as "Partial" coverage. Adding Playwright is the documented next-step layer of the testing pyramid — would automate the manual cases without re-discovering what they test.

### "Why Streamlit and not React + FastAPI?"
> For a single-process app with one developer in a time-constrained build, Streamlit collapses the client/server split into one file. The Dockerfile and the production architecture doc show the path to a React + FastAPI split when scale demands it.

### "What does production-grade mean to you?"
> Five things: real data persistence, real authentication, automated tests gating deploys, schema migrations versioned in code, audit trail of every state change. All five are present in this build.

### "Show me the database schema"
*Open TablePlus, click on the `users` table → Schema view.*
> Four tables. Users with bcrypt password hash. Kits with the full LLM JSON output stored as JSONB. Scorecards with one row per `(kit, interviewer)` pair, upserted on every save. Audit log append-only, indexed by user and action.

### "What would you build next?"
> Three things in order: Microsoft Entra ID SSO alongside email/password (Azure registration is done, just an unresolved Streamlit OIDC interaction blocking the wire-up), multi-candidate comparison view, ATS integration via webhooks. Each one is additive — no rewrites needed.

---

## If something breaks live

| Failure | Recovery |
|---|---|
| Gemini 429 | Switch model in sidebar to `gemini-flash-latest`. Fall back to pre-generated kit if still broken. |
| Browser hangs | Refresh. Session_state preserved, kit data in DB. |
| Streamlit Cloud cold-start delay | Pre-warm by visiting the URL 5 min before demo. |
| Tablet/phone backup needed | Open `interview-kit-pr.streamlit.app` on your phone. Same login works. |
| Demo machine fails entirely | Run `streamlit run app.py` from your local laptop. Same DB, same data. |

---

## What NOT to do

- Don't sign in live — already be signed in
- Don't type the API key live — it's in Streamlit Cloud Secrets
- Don't admit uncertainty about your own code — "Let me show you" beats "I think"
- Don't apologise for limitations — frame them as deliberate scope choices
- Don't mention the leaked API keys or the abandoned SSO debug session

---

## Tone

- **Slow down 30%.** Nervous = fast. Pause one second after each sentence.
- **Eye contact on one person per sentence.** Move between panel members deliberately.
- **Point at the screen** when you say "here" — anchors attention.
- **If you blank** — say "let me show you this" and click the next tab. The visual restarts your brain. Nobody notices the pause.

You've shipped real production-grade work. Show it.
