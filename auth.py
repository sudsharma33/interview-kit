"""
Authentication UI — Microsoft SSO + email/password (hybrid).

Users have two ways to sign in:
  1. **Sign in with Microsoft** (OpenID Connect via Streamlit's built-in OIDC).
     Real B2B users sign in via Microsoft Entra ID — no passwords for the user
     to manage, identity verified by Microsoft.
  2. **Email + password** (bcrypt-hashed). Fallback for service accounts,
     testing, and any user whose org isn't on Microsoft.

Whichever path is used, the same `users` row is matched/created by email.
The rest of the app doesn't care how a user signed in — it just reads
`st.session_state.user_id`.

Configuration lives in:
  - Streamlit Cloud: Settings → Secrets (an `[auth]` TOML section)
  - Local dev:        .streamlit/secrets.toml (same shape)
"""

from __future__ import annotations

import streamlit as st

import repository as repo

# ---------------------------------------------------------------------------
# Session-state plumbing
# ---------------------------------------------------------------------------

def _set_logged_in(user: dict, method: str) -> None:
    """Shared post-sign-in bookkeeping. `method` is 'sso' or 'password'."""
    st.session_state.user_id = user["id"]
    st.session_state.user_email = user["email"]
    st.session_state.user_name = user.get("display_name")
    st.session_state.auth_method = method
    # Wipe any leftover kit state from a previous session
    st.session_state.pop("scorecard_last_saved_hash", None)
    st.session_state.pop("loaded_scorecard_rows", None)


def _logout() -> None:
    """Clear local session. SSO logout also calls Streamlit's logout helper."""
    method = st.session_state.get("auth_method")
    for key in [
        "user_id", "user_email", "user_name", "auth_method",
        "kit", "kit_id", "validation",
        "scorecard_last_saved_hash", "loaded_scorecard_rows",
    ]:
        st.session_state.pop(key, None)
    if method == "sso":
        # Tells Microsoft to clear its session too, then returns to the app.
        st.logout()
    else:
        st.rerun()


def is_logged_in() -> bool:
    """
    Logged in if either:
      - Streamlit's SSO layer reports a Microsoft session, OR
      - Our session_state has a user_id from the email/password flow.
    """
    if "user_id" in st.session_state:
        return True
    return bool(getattr(st.user, "is_logged_in", False))


def _ensure_user_record_from_sso() -> None:
    """
    Streamlit confirmed a Microsoft sign-in but we haven't materialised our
    own `users` row yet. Match (or create) the row by email and stash the
    user_id in session_state.

    Microsoft personal accounts sometimes return the email under
    `preferred_username` instead of `email`, so we fall back through several
    claims before giving up.
    """
    if "user_id" in st.session_state:
        return
    # Try multiple claim names — Microsoft varies these by account type.
    email = (
        getattr(st.user, "email", None)
        or getattr(st.user, "preferred_username", None)
        or getattr(st.user, "upn", None)
    )
    name = getattr(st.user, "name", None) or getattr(st.user, "given_name", None)
    if not email:
        # Surface what claims we DID get, so the user/developer can debug.
        available = {k: v for k, v in dict(st.user).items() if not k.startswith("_")} if hasattr(st.user, "__iter__") else {}
        st.error(
            "Microsoft sign-in didn't return an email address. "
            f"Available claims: {sorted(available.keys()) or 'unknown'}. "
            "Sign out and try a different Microsoft account, or use email + password instead."
        )
        st.stop()
    user = repo.get_or_create_user(email, name)
    _set_logged_in(user, method="sso")


# ---------------------------------------------------------------------------
# UI — logout button (sidebar) + sign-in card (main area)
# ---------------------------------------------------------------------------

def render_logout_button() -> None:
    """Sidebar identity + Sign-out button. Only visible when logged in."""
    if not is_logged_in():
        return
    st.sidebar.markdown("---")
    name = st.session_state.get("user_name") or st.session_state.get("user_email") or "Signed in"
    method = st.session_state.get("auth_method", "password")
    method_label = "Microsoft SSO" if method == "sso" else "Email + password"
    st.sidebar.caption(f"Signed in as **{name}**  \n*{method_label}*")
    if st.sidebar.button("Sign out", use_container_width=True):
        _logout()


def _render_microsoft_button() -> None:
    """The big SSO button at the top of the sign-in card."""
    if st.button(
        "Sign in with Microsoft",
        type="primary",
        use_container_width=True,
        key="sso_signin_button",
    ):
        # Named provider must match the secrets.toml [auth.microsoft] section.
        st.login("microsoft")


def _render_password_signin_form() -> None:
    with st.form("signin_form", clear_on_submit=False):
        email = st.text_input("Email", key="signin_email", placeholder="you@company.com")
        password = st.text_input("Password", type="password", key="signin_pw")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        try:
            user = repo.authenticate_user(email, password)
        except repo.InvalidCredentials as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Sign-in failed: {e}")
        else:
            _set_logged_in(user, method="password")
            st.rerun()


def _render_password_signup_form() -> None:
    with st.form("signup_form", clear_on_submit=False):
        email = st.text_input("Email", key="signup_email", placeholder="you@company.com")
        name = st.text_input("Display name (optional)", key="signup_name", placeholder="Sudarshan")
        password = st.text_input("Password", type="password", key="signup_pw", help="At least 8 characters")
        confirm = st.text_input("Confirm password", type="password", key="signup_pw2")
        submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
    if submitted:
        if password != confirm:
            st.error("Passwords don't match.")
            return
        try:
            user = repo.register_user(email, password, name)
        except repo.UserAlreadyExists:
            st.error("An account with that email already exists. Try signing in.")
        except ValueError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Sign-up failed: {e}")
        else:
            _set_logged_in(user, method="password")
            st.success("Account created — signing you in…")
            st.rerun()


def render_login_gate() -> None:
    """Centred sign-in card with SSO button on top and password tabs below."""
    st.markdown(
        """
        <div style="max-width:540px;margin:60px auto 24px;text-align:center;">
          <h1 style="margin-bottom:8px;font-weight:600;">Interview Kit Generator</h1>
          <p style="color:#888;font-size:1rem;">
            Sign in to generate kits and resume scoring history.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        _render_microsoft_button()

        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:10px;margin:18px 0 10px;color:#666;font-size:0.85rem;">
              <div style="flex:1;border-top:1px solid #444;"></div>
              <span>or use email and password</span>
              <div style="flex:1;border-top:1px solid #444;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        signin_tab, signup_tab = st.tabs(["Sign in", "Create account"])
        with signin_tab:
            _render_password_signin_form()
        with signup_tab:
            _render_password_signup_form()


def require_login() -> bool:
    """
    Returns True if the user is signed in (via SSO or password).
    Otherwise renders the login gate; the caller should st.stop().
    """
    # Path 1: already authenticated via password flow (session_state)
    if "user_id" in st.session_state:
        return True
    # Path 2: SSO flow — Microsoft confirmed sign-in, materialise the DB row
    if getattr(st.user, "is_logged_in", False):
        _ensure_user_record_from_sso()
        return True
    # Otherwise show the gate
    render_login_gate()
    return False
