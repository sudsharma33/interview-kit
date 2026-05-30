"""
Authentication UI — email + password (bcrypt-hashed).

Pure DB-backed auth, no third-party identity provider. Two flows:
  - Sign in:        existing users authenticate with email + password
  - Create account: new users register with email + password

The whole app is gated behind `require_login()`. Until the user is signed in,
only the centred sign-in card renders. Once they sign in, `st.session_state`
carries:

    user_id     -> UUID string
    user_email  -> str
    user_name   -> str | None

The rest of the app reads `st.session_state.user_id` to attribute kits and
scorecards to the right person.
"""

from __future__ import annotations

import streamlit as st

import repository as repo


def _set_logged_in(user: dict) -> None:
    st.session_state.user_id = user["id"]
    st.session_state.user_email = user["email"]
    st.session_state.user_name = user.get("display_name")
    # Wipe any leftover kit state from a previous session
    st.session_state.pop("scorecard_last_saved_hash", None)
    st.session_state.pop("loaded_scorecard_rows", None)


def _logout() -> None:
    for key in [
        "user_id", "user_email", "user_name",
        "kit", "kit_id", "validation",
        "scorecard_last_saved_hash", "loaded_scorecard_rows",
    ]:
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return "user_id" in st.session_state


def render_logout_button() -> None:
    """Sidebar identity + Sign-out button. Only visible when logged in."""
    if not is_logged_in():
        return
    st.sidebar.markdown("---")
    name = st.session_state.get("user_name") or st.session_state.get("user_email") or "Signed in"
    st.sidebar.caption(f"Signed in as **{name}**")
    if st.sidebar.button("Sign out", use_container_width=True):
        _logout()
        st.rerun()


def _render_signin_form() -> None:
    # Plain widgets (no st.form) so Streamlit doesn't render its
    # "Press Enter to submit form" tooltip on the password field.
    email = st.text_input("Email", key="signin_email", placeholder="you@company.com")
    password = st.text_input("Password", type="password", key="signin_pw")
    if st.button("Sign in", type="primary", use_container_width=True, key="signin_btn"):
        try:
            user = repo.authenticate_user(email, password)
        except repo.InvalidCredentials as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Sign-in failed: {e}")
        else:
            _set_logged_in(user)
            st.rerun()


def _render_signup_form() -> None:
    email = st.text_input("Email", key="signup_email", placeholder="you@company.com")
    name = st.text_input("Display name (optional)", key="signup_name", placeholder="Sudarshan")
    password = st.text_input("Password", type="password", key="signup_pw", help="At least 8 characters")
    confirm = st.text_input("Confirm password", type="password", key="signup_pw2")
    if st.button("Create account", type="primary", use_container_width=True, key="signup_btn"):
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
            _set_logged_in(user)
            st.success("Account created — signing you in…")
            st.rerun()


def render_login_gate() -> None:
    """Centred sign-in card with Sign in / Create account tabs."""
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
        signin_tab, signup_tab = st.tabs(["Sign in", "Create account"])
        with signin_tab:
            _render_signin_form()
        with signup_tab:
            _render_signup_form()


def require_login() -> bool:
    """
    Returns True if the user is signed in. Otherwise renders the login gate
    and returns False — the caller should `st.stop()` to halt rendering of
    the protected app.
    """
    if is_logged_in():
        return True
    render_login_gate()
    return False
