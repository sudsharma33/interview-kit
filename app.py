import json
import os
from io import BytesIO

import pandas as pd
import streamlit as st
from docx import Document
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader

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
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar ----------
st.sidebar.header("Settings")
api_key = st.sidebar.text_input(
    "Google AI Studio API Key",
    value=os.getenv("GOOGLE_API_KEY", ""),
    type="password",
    help="Get a free key at https://aistudio.google.com/app/apikey",
)
model_name = st.sidebar.selectbox(
    "Model",
    ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"],
    index=0,
    help="Lite is the safest free-tier choice.",
)

# ---------- Helpers ----------
def extract_text(uploaded_file) -> str:
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

col1, col2 = st.columns(2)
with col1:
    input_column("Job Description", "jd_text", "jd_file", "jd_file_name", clear_jd)
with col2:
    input_column("Candidate Resume", "cv_text", "cv_file", "cv_file_name", clear_cv)

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

go = st.button("Generate Interview Kit", type="primary", use_container_width=True)


def run_generation():
    with st.spinner("Analyzing and generating interview kit…"):
        try:
            st.session_state.kit = generate_kit(st.session_state.jd_text, st.session_state.cv_text)
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

    st.markdown("#### Summary")
    a, b = st.columns(2)
    a.markdown(f"**Role**  \n{kit.get('jd_summary','')}")
    b.markdown(f"**Candidate**  \n{kit.get('candidate_summary','')}")

    st.markdown("#### Skill Match vs Gap")
    m, g = st.columns(2)
    with m:
        st.markdown("**Matched**")
        for s in kit.get("matched_skills", []) or ["—"]:
            st.markdown(f"- {s}")
    with g:
        st.markdown("**Gaps**")
        for s in kit.get("gap_skills", []) or ["—"]:
            st.markdown(f"- {s}")

    st.markdown("#### Technical Questions")
    render_question_cards(kit.get("technical_questions", []), "Why asked", "why_asked")

    st.markdown("#### Behavioral Questions")
    render_question_cards(kit.get("behavioral_questions", []), "Why asked", "why_asked")

    st.markdown("#### Gap-Probing Questions")
    render_question_cards(kit.get("gap_probe_questions", []), "Targets gap", "targets_gap")

    st.markdown("#### Interviewer Scorecard")
    st.caption("Click any cell in the Score column and type 1–5. The weighted total updates live.")
    sc_rows = kit.get("scorecard", [])
    sc_df = pd.DataFrame(sc_rows) if sc_rows else pd.DataFrame()
    if not sc_df.empty:
        sc_df["Score"] = None
        sc_df["Notes"] = ""
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

        c1, c2 = st.columns(2)
        c1.metric(
            "Weighted Score",
            f"{weighted:.0f} / {max_score:.0f}" if max_score else "—",
            f"{pct:.1f}%" if max_score else "Enter scores to see total",
        )
        c2.metric("Criteria Scored", f"{scored_count} / {total_count}")

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
            json.dumps(kit, indent=2).encode("utf-8"),
            file_name="interview_kit.json",
            mime="application/json",
            use_container_width=True,
        )
