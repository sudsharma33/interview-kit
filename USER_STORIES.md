# User Stories — Interview Kit Generator

User stories captured in the standard `As a [persona] / I want [goal] / so that [benefit]` format, with acceptance criteria for each.

---

## Personas

| Persona | Role | Primary need |
|---|---|---|
| **Recruiter (TA Specialist)** | Owns the hiring funnel for one or more roles | Reduce manual interview-prep time per candidate |
| **Hiring Manager / Interviewer** | Conducts technical or behavioural interviews | Walk into the room with a structured, role-relevant kit |
| **Hiring Panel Lead** | Synthesises evaluations across multiple interviewers | Get consistent, comparable scorecards from every panel member |

---

## Story 1 — Generate a tailored interview kit

**As a** recruiter,
**I want** to provide a job description and a candidate resume and receive a tailored interview kit in under a minute,
**so that** I can prepare for interviews quickly without starting from a blank page.

### Acceptance criteria
- Both inputs accept paste OR upload (PDF / DOCX / TXT)
- The generated kit contains: role summary, candidate summary, matched skills, gap skills, technical questions, behavioural questions, gap-probing questions, and a scorecard
- Generation completes within 10 seconds under normal conditions
- The kit is rendered in a tabbed dashboard inside the same browser session

---

## Story 2 — Catch invalid inputs before wasting time

**As a** recruiter,
**I want** the system to detect when an uploaded document doesn't look like a job description or a resume,
**so that** I don't waste a generation attempt on the wrong file.

### Acceptance criteria
- Validation runs automatically before the main generation
- A clear warning explains which input failed and why
- I can either fix the input or override with a "Generate anyway" action
- The warning disappears automatically as soon as I change either input

---

## Story 3 — Score candidates live during the interview

**As an** interviewer,
**I want** to enter scores into the scorecard during the interview and see the weighted total update live,
**so that** I can finalise the evaluation immediately without manual math afterwards.

### Acceptance criteria
- Each scorecard row shows a criterion, weight, and a "strong response shows" anchor
- The Score column accepts values from 1 to 5
- The Notes column captures free-text observations
- The weighted total and percentage update on every score change
- A progress bar shows how many criteria are still pending

---

## Story 4 — Export results for the hiring panel and downstream systems

**As a** recruiter,
**I want** to download the scorecard as CSV and the full kit as JSON,
**so that** I can share results with the hiring panel and feed them into downstream systems.

### Acceptance criteria
- CSV opens cleanly in Excel and Google Sheets
- CSV contains the criteria, weights, anchors, my scores, and my notes
- JSON contains the full kit including original questions, gaps, and my completed scorecard
- JSON also contains a scoring summary (weighted total, max possible, percentage)

---

## Story 5 — Start a fresh kit cleanly

**As a** recruiter,
**I want** to clear inputs and previous results with a single click,
**so that** I can move to the next candidate without leftover state.

### Acceptance criteria
- Each input column has its own Clear button
- Removing a file via the uploader's "x" also clears its corresponding textarea
- A Clear results button removes the generated kit
- Stale validation warnings are dropped automatically when inputs change

---

## Future stories (out of scope for v1, listed for backlog visibility)

| ID | Story | Status |
|---|---|---|
| F1 | As a recruiter, I want to edit individual generated questions in the UI | Planned |
| F2 | As a hiring panel lead, I want to compare scorecards across multiple candidates for the same role side by side | Planned |
| F3 | As a recruiter, I want to push the kit directly into our ATS (Greenhouse, Lever, Workday) | Planned |
| F4 | As an admin, I want role templates (SDE, Data, PM, Designer) that bias the model toward role-specific questions | Planned |
| F5 | As a compliance officer, I want every kit to be archived with a retention policy | Planned |
| F6 | As a hiring manager, I want sign-in with my company SSO so my kits are private | Planned |

---

## How these were derived

These stories were extracted by walking through the hackathon brief's evaluation criteria and the natural sequence of a recruiter's day: prep → screen inputs → generate → interview → score → share → repeat. Each criterion in the brief maps to at least one story above:

| Brief criterion | Stories covering it |
|---|---|
| Business usefulness | 1, 4, 5 |
| Question quality | 1 |
| Gap analysis | 1, 3 |
| Practicality of the scorecard | 3, 4 |
| Clarity of output | 1, 3 |
| Ability to explain the logic | This document |
