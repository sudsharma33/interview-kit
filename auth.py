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
import session_token

# Query-param key that carries the signed session token. Living in the URL is
# what lets a sign-in survive a browser refresh (see session_token.py).
_TOKEN_QP = "s"


def _apply_user(user: dict) -> None:
    """Populate session_state from a user dict (no token side effects)."""
    st.session_state.user_id = user["id"]
    st.session_state.user_email = user["email"]
    st.session_state.user_name = user.get("display_name")
    # Wipe any leftover kit state from a previous session
    st.session_state.pop("scorecard_last_saved_hash", None)
    st.session_state.pop("loaded_scorecard_rows", None)


def _set_logged_in(user: dict) -> None:
    _apply_user(user)
    # Park a signed token in the URL so the session survives a hard refresh.
    try:
        st.query_params[_TOKEN_QP] = session_token.make_token(user["id"])
    except Exception:
        # Never let token minting break the login flow — worst case the user
        # simply doesn't get refresh-survival this session.
        pass


def _logout() -> None:
    for key in [
        "user_id", "user_email", "user_name",
        "kit", "kit_id", "validation",
        "scorecard_last_saved_hash", "loaded_scorecard_rows",
    ]:
        st.session_state.pop(key, None)
    # Drop the token from the URL so a refresh after sign-out stays signed out.
    if _TOKEN_QP in st.query_params:
        del st.query_params[_TOKEN_QP]


def restore_session_from_token() -> None:
    """
    Re-hydrate session_state from a signed URL token after a refresh.

    Called once at the top of the app, BEFORE require_login(). If the user is
    already in session_state this is a no-op. Otherwise it verifies the token
    in the URL and, if valid, looks the user up in the database and restores
    them — so a hard refresh no longer kicks them back to the login screen.
    """
    if is_logged_in():
        return
    token = st.query_params.get(_TOKEN_QP)
    if not token:
        return
    user_id = session_token.read_token(token)
    if not user_id:
        # Tampered, malformed, or expired — clear the stale token.
        del st.query_params[_TOKEN_QP]
        return
    try:
        user = repo.get_user_by_id(user_id)
    except Exception:
        # DB hiccup — leave the token in place and try again next run rather
        # than logging the user out on a transient error.
        return
    if user:
        _apply_user(user)
    else:
        # User no longer exists — clear the orphaned token.
        del st.query_params[_TOKEN_QP]


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
    # Wrapped in st.form so pressing Enter in any field submits the form —
    # st.form_submit_button is the only button type Streamlit triggers on
    # Enter. Plain st.button only fires on a click.
    with st.form("signin_form"):
        email = st.text_input("Email", key="signin_email")
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
            _set_logged_in(user)
            st.rerun()


def _render_signup_form() -> None:
    # Same st.form pattern as sign-in so Enter submits the registration.
    with st.form("signup_form"):
        email = st.text_input("Email", key="signup_email")
        name = st.text_input("Display name (optional)", key="signup_name")
        password = st.text_input("Password", type="password", key="signup_pw")
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
