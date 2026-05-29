import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

from parsing import extract_text  # pure-logic helpers, unit-tested in isolation
import repository as repo  # database persistence layer

load_dotenv()

st.set_page_config(page_title="Interview Kit Generator", layout="wide")

# ---------- Styling ----------
st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1200px; }
      h1 { font-weight: 600; letter-spacing: -0.02em; }
      h3 { font-weight: 600; margin-top: 2rem; margin-bottom: 0.5rem; }
      .stButton button { border-radius: 6px; }
      div[data-testid="stMetric"] { background: rgba(127,127,127,0.06); padding: 12px 16px; border-radius: 8px; }
      .muted { color: #888; font-size: 0.9rem; }
      .section-divider { border-top: 1px solid rgba(127,127,127,0.2); margin: 1.5rem 0; }
      .qcard {
        display: flex; gap: 14px;
        padding: 14px 16px; margin: 8px 0;
        border: 1px solid rgba(127,127,127,0.18);
        border-radius: 8px;
        background: rgba(127,127,127,0.04);
      }
      .qnum {
        flex-shrink: 0;
        font-weight: 600; font-size: 0.85rem;
        color: #888;
        padding-top: 2px; min-width: 28px;
      }
      .qbody { flex: 1; }
      .qtext { font-weight: 500; font-size: 1rem; margin-bottom: 8px; line-height: 1.45; }
      .qmeta { font-size: 0.88rem; color: #aaa; margin-top: 4px; line-height: 1.45; }
      .qlabel { color: #888; font-weight: 500; }
      .pill-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
      .pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 500;
        line-height: 1.2;
        border: 1px solid transparent;
      }
      .pill-match { background: rgba(46,160,67,0.12); color: #2ea043; border-color: rgba(46,160,67,0.3); }
      .pill-gap   { background: rgba(219,154,4,0.12); color: #dba904; border-color: rgba(219,154,4,0.3); }
      .pill-empty { background: rgba(127,127,127,0.08); color: #888; border-color: rgba(127,127,127,0.2); }
      .empty-state {
        text-align: center;
        padding: 60px 20px;
        border: 1px dashed rgba(127,127,127,0.3);
        border-radius: 12px;
        margin: 24px 0;
        color: #888;
      }
      .empty-state h3 { color: #aaa; margin: 0 0 8px 0; font-weight: 500; }
      .empty-state p { margin: 0; font-size: 0.95rem; }
      .summary-card {
        padding: 16px 18px;
        border: 1px solid rgba(127,127,127,0.18);
        border-radius: 8px;
        background: rgba(127,127,127,0.04);
        height: 100%;
      }
      .summary-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: #888; margin-bottom: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar ----------
# Server-side secret. NEVER passed to the password field's `value=` argument,
# because doing so would expose it to the visitor's browser (the masking is
# cosmetic — the underlying value is readable via dev tools or session state).
_server_key = os.getenv("GOOGLE_API_KEY", "")

st.sidebar.header("Settings")
_user_key = st.sidebar.text_input(
    "Google AI Studio API Key",
    type="password",
    placeholder="Paste your key, or leave blank to use the server default" if _server_key else "Paste your AI Studio key here",
    help="Get a free key at https://aistudio.google.com/app/apikey. The server-configured key (if any) stays on the server and is never sent to the browser.",
)
# Visitor-supplied key takes precedence; otherwise fall back to the server secret.
api_key = _user_key or _server_key

if _server_key and not _user_key:
    st.sidebar.caption("✓ Using server-configured key")

model_name = st.sidebar.selectbox(
    "Model",
    ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"],
    index=0,
    help="Lite is the safest free-tier choice.",
)


def _render_history_sidebar():
    """Show the current user's recent kits, loaded from Postgres."""
    if "user_id" not in st.session_state:
        return
    st.sidebar.markdown("---")
    st.sidebar.subheader("Recent Kits")
    try:
        kits = repo.list_kits_for_user(st.session_state.user_id, limit=8)
    except Exception as e:
        st.sidebar.caption(f"History unavailable ({type(e).__name__})")
        return
    if not kits:
        st.sidebar.caption("No kits yet — generate one to populate.")
        return
    for k in kits:
        label = (k.get("role_title") or "Untitled kit")[:50]
        when = k["created_at"].strftime("%b %d, %H:%M")
        if st.sidebar.button(f"{label}\n{when}", key=f"hist_{k['id']}", use_container_width=True):
            loaded = repo.load_kit(k["id"])
            if loaded:
                st.session_state.kit = loaded["kit_json"]
                st.session_state.kit_id = loaded["id"]
                # Pull any saved scorecard progress back into session_state
                # so the interviewer resumes exactly where they left off.
                sc = repo.get_latest_scorecard(loaded["id"], st.session_state.user_id)
                if sc and sc.get("rows"):
                    st.session_state.loaded_scorecard_rows = sc["rows"]
                else:
                    st.session_state.pop("loaded_scorecard_rows", None)
                # invalidate any stale auto-save snapshot from a previous kit
                st.session_state.pop("scorecard_last_saved_hash", None)
                st.rerun()


# `extract_text` lives in parsing.py for unit-testability and reuse.

PROMPT = """You are an expert technical recruiter and interviewer.

Given the JOB DESCRIPTION and CANDIDATE RESUME below, produce a structured interview kit.

Return ONLY valid JSON (no markdown fences) with this exact schema:
{{
  "candidate_summary": "2-3 sentence overview of the candidate",
  "jd_summary": "2-3 sentence overview of the role",
  "matched_skills":   ["skills present in BOTH resume and JD"],
  "gap_skills":       ["skills required by JD but missing/weak in resume"],
  "technical_questions": [
    {{"question": "...", "why_asked": "...", "expected_signal": "..."}}
  ],
  "behavioral_questions": [
    {{"question": "...", "why_asked": "...", "expected_signal": "..."}}
  ],
  "gap_probe_questions": [
    {{"question": "...", "targets_gap": "<skill>", "expected_signal": "..."}}
  ],
  "scorecard": [
    {{"criterion": "...", "weight": 1-5, "what_good_looks_like": "..."}}
  ]
}}

Aim for 5-7 technical questions, 3-5 behavioral, 3-5 gap probes, 6-8 scorecard rows.

=== JOB DESCRIPTION ===
{jd}

=== CANDIDATE RESUME ===
{resume}
"""


def generate_kit(jd: str, resume: str) -> dict:
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model_name,
        contents=PROMPT.format(jd=jd, resume=resume),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    return json.loads(resp.text)


VALIDATE_PROMPT = """Classify the two documents below. Return ONLY valid JSON:
{{
  "jd_valid": true/false,
  "jd_reason": "one short sentence",
  "cv_valid": true/false,
  "cv_reason": "one short sentence"
}}

A valid JOB DESCRIPTION typically lists role, responsibilities, requirements, or qualifications.
A valid RESUME / CV typically lists a person's experience, education, skills, or projects.

=== DOCUMENT A (claimed Job Description) ===
{jd}

=== DOCUMENT B (claimed Resume) ===
{resume}
"""


def validate_inputs(jd: str, resume: str) -> dict:
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model_name,
        contents=VALIDATE_PROMPT.format(jd=jd[:4000], resume=resume[:4000]),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(resp.text)


def questions_df(rows, cols):
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)[cols]


def render_pills(items, kind: str):
    """Render a list of strings as colored pills. kind: 'match' | 'gap'."""
    if not items:
        st.markdown('<div class="pill-row"><span class="pill pill-empty">None identified</span></div>', unsafe_allow_html=True)
        return
    cls = f"pill pill-{kind}"
    html = '<div class="pill-row">' + "".join(f'<span class="{cls}">{s}</span>' for s in items) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_question_cards(rows, secondary_label: str, secondary_key: str):
    """Render a list of question dicts as readable numbered cards instead of a table."""
    if not rows:
        st.markdown("<div class='muted'>No questions generated.</div>", unsafe_allow_html=True)
        return
    for i, q in enumerate(rows, 1):
        question = q.get("question", "")
        secondary = q.get(secondary_key, "")
        signal = q.get("expected_signal", "")
        st.markdown(
            f"""
            <div class="qcard">
              <div class="qnum">Q{i}</div>
              <div class="qbody">
                <div class="qtext">{question}</div>
                <div class="qmeta"><span class="qlabel">{secondary_label}:</span> {secondary}</div>
                <div class="qmeta"><span class="qlabel">Expected signal:</span> {signal}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------- Input panel ----------
st.session_state.setdefault("jd_text", "")
st.session_state.setdefault("cv_text", "")
st.session_state.setdefault("jd_file_name", None)
st.session_state.setdefault("cv_file_name", None)


def drop_validation():
    """Any change to inputs makes the previous validation result stale."""
    st.session_state.pop("validation", None)


def clear_jd():
    st.session_state.jd_text = ""
    st.session_state.jd_file_name = None
    drop_validation()


def clear_cv():
    st.session_state.cv_text = ""
    st.session_state.cv_file_name = None
    drop_validation()


def input_column(label: str, state_key: str, file_key: str, name_key: str, clear_fn):
    st.subheader(label)
    uploaded = st.file_uploader(
        "Upload file (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        key=file_key,
        label_visibility="collapsed",
    )
    # If a new file was just uploaded, populate the textarea from it.
    if uploaded is not None and uploaded.name != st.session_state[name_key]:
        st.session_state[state_key] = extract_text(uploaded)
        st.session_state[name_key] = uploaded.name
        drop_validation()
    # If the file was removed via the uploader's "x", clear the textarea too.
    elif uploaded is None and st.session_state[name_key] is not None:
        st.session_state[state_key] = ""
        st.session_state[name_key] = None
        drop_validation()

    cols = st.columns([1, 5])
    cols[0].button("Clear", key=f"clear_{state_key}", on_click=clear_fn, use_container_width=True)
    chars = len(st.session_state[state_key])
    cols[1].markdown(f"<div class='muted' style='padding-top:8px'>{chars:,} characters</div>", unsafe_allow_html=True)

    st.text_area(
        "Content",
        height=260,
        key=state_key,
        label_visibility="collapsed",
        placeholder="Paste text here, or upload a file above…",
        on_change=drop_validation,
    )


st.title("Interview Kit Generator")
st.markdown(
    "<p class='muted'>Generate tailored interview questions and a scorecard from a job description and a candidate resume.</p>",
    unsafe_allow_html=True,
)

# Ensure a user exists so the history sidebar can populate even before the
# first generation. Day 2 replaces this with real auth.
try:
    if "user_id" not in st.session_state:
        u = repo.get_or_create_user("demo@interview-kit.local", "Demo User")
        st.session_state.user_id = u["id"]
except Exception:
    pass  # DB unavailable; app still works in ephemeral mode

_render_history_sidebar()

col1, col2 = st.columns(2)
with col1:
    input_column("Job Description", "jd_text", "jd_file", "jd_file_name", clear_jd)
with col2:
    input_column("Candidate Resume", "cv_text", "cv_file", "cv_file_name", clear_cv)

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

go = st.button("Generate Interview Kit", type="primary", use_container_width=True)


def _current_user_id() -> str:
    """
    Until real auth lands (Day 2), every generation is attributed to a
    single demo user so persistence is visible end-to-end.
    """
    if "user_id" not in st.session_state:
        u = repo.get_or_create_user("demo@interview-kit.local", "Demo User")
        st.session_state.user_id = u["id"]
    return st.session_state.user_id


def run_generation():
    with st.spinner("Analyzing and generating interview kit…"):
        try:
            kit = generate_kit(st.session_state.jd_text, st.session_state.cv_text)
            st.session_state.kit = kit
            # Persist to Postgres so the kit survives reloads, deploys, and
            # appears in the user's history sidebar.
            try:
                kit_id = repo.save_kit(
                    user_id=_current_user_id(),
                    jd_text=st.session_state.jd_text,
                    resume_text=st.session_state.cv_text,
                    kit_json=kit,
                )
                st.session_state.kit_id = kit_id
            except Exception as db_err:
                # Never block the user if the DB write fails — the kit is
                # still in session_state. Log to the UI for visibility.
                st.warning(f"Kit generated but not persisted to history: {db_err}")
            st.session_state.pop("validation", None)
        except Exception as e:
            st.error(f"Generation failed: {e}")
            st.stop()


if go:
    if not api_key:
        st.error("Please add your Google AI Studio API key in the sidebar.")
        st.stop()
    if not st.session_state.jd_text.strip() or not st.session_state.cv_text.strip():
        st.error("Please provide both a Job Description and a Resume.")
        st.stop()

    with st.spinner("Checking inputs…"):
        try:
            st.session_state.validation = validate_inputs(
                st.session_state.jd_text, st.session_state.cv_text
            )
        except Exception:
            st.session_state.validation = {"jd_valid": True, "cv_valid": True, "jd_reason": "", "cv_reason": ""}

    v = st.session_state.validation
    if v.get("jd_valid") and v.get("cv_valid"):
        run_generation()

# If validation flagged a problem, show warning + override button
if (
    "validation" in st.session_state
    and "kit" not in st.session_state
    and not (st.session_state.validation.get("jd_valid") and st.session_state.validation.get("cv_valid"))
):
    v = st.session_state.validation
    msgs = []
    if not v.get("jd_valid"):
        msgs.append(f"**Job Description** doesn't look like a typical JD — {v.get('jd_reason','')}")
    if not v.get("cv_valid"):
        msgs.append(f"**Resume** doesn't look like a typical CV — {v.get('cv_reason','')}")
    st.warning("Heads up:\n\n" + "\n\n".join(f"- {m}" for m in msgs) + "\n\nResults may be unreliable. You can generate anyway or fix the inputs.")

    oc1, oc2 = st.columns(2)
    if oc1.button("Generate anyway", type="primary", use_container_width=True):
        run_generation()
    if oc2.button("Cancel", use_container_width=True):
        st.session_state.pop("validation", None)
        st.rerun()

# ---------- Output panel ----------
if "kit" in st.session_state:
    kit = st.session_state.kit
    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    header_cols = st.columns([6, 1])
    header_cols[0].markdown("### Interview Kit")
    if header_cols[1].button("Clear results", use_container_width=True):
        del st.session_state.kit
        st.rerun()

    tab_summary, tab_questions, tab_scorecard = st.tabs(["Summary", "Questions", "Scorecard"])

    # ---- Summary tab ----
    with tab_summary:
        a, b = st.columns(2)
        with a:
            st.markdown(
                f"""<div class="summary-card">
                  <div class="summary-label">Role</div>
                  <div>{kit.get('jd_summary','')}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        with b:
            st.markdown(
                f"""<div class="summary-card">
                  <div class="summary-label">Candidate</div>
                  <div>{kit.get('candidate_summary','')}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("")  # spacing
        m, g = st.columns(2)
        with m:
            st.markdown('<div class="summary-label">Matched Skills</div>', unsafe_allow_html=True)
            render_pills(kit.get("matched_skills", []), "match")
        with g:
            st.markdown('<div class="summary-label">Gap Skills</div>', unsafe_allow_html=True)
            render_pills(kit.get("gap_skills", []), "gap")

    # ---- Questions tab ----
    with tab_questions:
        sub_tech, sub_beh, sub_gap = st.tabs([
            f"Technical ({len(kit.get('technical_questions', []))})",
            f"Behavioral ({len(kit.get('behavioral_questions', []))})",
            f"Gap Probes ({len(kit.get('gap_probe_questions', []))})",
        ])
        with sub_tech:
            render_question_cards(kit.get("technical_questions", []), "Why asked", "why_asked")
        with sub_beh:
            render_question_cards(kit.get("behavioral_questions", []), "Why asked", "why_asked")
        with sub_gap:
            render_question_cards(kit.get("gap_probe_questions", []), "Targets gap", "targets_gap")

    # ---- Scorecard tab ----
    with tab_scorecard:
        st.caption("Click any cell in the Score column and type 1–5. The weighted total updates live. Scores are auto-saved to the database.")
        sc_rows = kit.get("scorecard", [])
        sc_df = pd.DataFrame(sc_rows) if sc_rows else pd.DataFrame()
        if not sc_df.empty:
            sc_df["Score"] = None
            sc_df["Notes"] = ""
            # Restore previously saved scorecard progress if any.
            saved_rows = st.session_state.get("loaded_scorecard_rows") or []
            if saved_rows:
                # Index saved rows by criterion so we tolerate row reordering.
                saved_by_criterion = {r.get("criterion"): r for r in saved_rows}
                for i, row in sc_df.iterrows():
                    prev = saved_by_criterion.get(row["criterion"])
                    if prev:
                        sc_df.at[i, "Score"] = prev.get("Score")
                        sc_df.at[i, "Notes"] = prev.get("Notes", "") or ""
            edited = st.data_editor(
                sc_df,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                column_config={
                    "criterion": st.column_config.TextColumn("Criterion", disabled=True),
                    "weight": st.column_config.NumberColumn("Weight", min_value=1, max_value=5, disabled=True),
                    "what_good_looks_like": st.column_config.TextColumn("What good looks like", disabled=True, width="large"),
                    "Score": st.column_config.NumberColumn("Score", min_value=1, max_value=5, step=1, help="1–5"),
                    "Notes": st.column_config.TextColumn("Notes", width="medium"),
                },
            )
            scores = edited["Score"].fillna(0)
            weighted = (edited["weight"] * scores).sum()
            scored_mask = edited["Score"].notna()
            max_score = (edited.loc[scored_mask, "weight"] * 5).sum()
            pct = (weighted / max_score * 100) if max_score else 0
            scored_count = int(scored_mask.sum())
            total_count = len(edited)
            completion = scored_count / total_count if total_count else 0

            st.progress(completion, text=f"Scoring progress: {scored_count} of {total_count} criteria")

            c1, c2 = st.columns(2)
            c1.metric(
                "Weighted Score",
                f"{weighted:.0f} / {max_score:.0f}" if max_score else "—",
                f"{pct:.1f}%" if max_score else "Enter scores to see total",
            )
            c2.metric("Criteria Scored", f"{scored_count} / {total_count}")

            # ---- Auto-save scorecard progress to Postgres ----
            # On every Streamlit rerun we hash the current scorecard state and
            # only issue a DB write if it changed since the last save. That
            # keeps the keystroke-level rerun cycle cheap.
            if "kit_id" in st.session_state and "user_id" in st.session_state:
                scorecard_rows = edited.to_dict(orient="records")
                # tuple of (criterion, score, notes) is a stable, JSON-safe signature
                sig = tuple(
                    (r.get("criterion"), r.get("Score"), r.get("Notes", ""))
                    for r in scorecard_rows
                )
                if st.session_state.get("scorecard_last_saved_hash") != sig:
                    try:
                        repo.upsert_scorecard_progress(
                            kit_id=st.session_state.kit_id,
                            user_id=st.session_state.user_id,
                            scores_json=scorecard_rows,
                            weighted_total=float(weighted),
                            max_possible=float(max_score) if max_score else 0.0,
                            percentage=float(pct),
                        )
                        st.session_state.scorecard_last_saved_hash = sig
                        if scored_count > 0:
                            st.caption("✓ Auto-saved")
                    except Exception as save_err:
                        st.caption(f"Auto-save failed: {save_err}")

            # Build a complete export that merges the interviewer's scores/notes
            # back into the kit and includes computed totals.
            export_kit = {
                **kit,
                "scorecard": edited.to_dict(orient="records"),
                "scoring_summary": {
                    "weighted_score": float(weighted),
                    "max_possible": float(max_score) if max_score else 0.0,
                    "percentage": float(pct),
                    "criteria_scored": scored_count,
                    "criteria_total": total_count,
                },
            }

            d1, d2 = st.columns(2)
            d1.download_button(
                "Download Scorecard (CSV)",
                edited.to_csv(index=False).encode("utf-8"),
                file_name="interview_scorecard.csv",
                mime="text/csv",
                use_container_width=True,
            )
            d2.download_button(
                "Download Full Kit (JSON)",
                json.dumps(export_kit, indent=2).encode("utf-8"),
                file_name="interview_kit.json",
                mime="application/json",
                use_container_width=True,
            )

# ---------- Empty state (only when nothing is in progress) ----------
elif "validation" not in st.session_state:
    st.markdown(
        """
        <div class="empty-state">
          <h3>No interview kit yet</h3>
          <p>Upload or paste a Job Description and a Resume above, then click <b>Generate Interview Kit</b>.</p>
          <p style="margin-top:10px; font-size:0.85rem;">Tip: try the files in the <code>samples/</code> folder for a quick demo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
