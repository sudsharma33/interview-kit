"""
Authentication UI — Microsoft SSO via OpenID Connect.

Uses Streamlit's built-in OIDC support (added in v1.42). All identity is
managed by Microsoft Entra ID; we just match the returned email against our
`users` table, creating a new row on first sign-in.

No passwords. No password resets. No bcrypt at the UI layer. Standard
enterprise SSO — what real B2B SaaS tools look like.

Configuration lives in:
    - Streamlit Cloud: Settings → Secrets (an `[auth]` TOML section)
    - Local dev:        .streamlit/secrets.toml (same shape)

The repository's password-based functions (register_user, authenticate_user)
are preserved for backwards compatibility — they're useful for service
accounts and as a fallback if the SSO IdP is unreachable. Day-to-day app
auth no longer touches them.
"""

from __future__ import annotations

import streamlit as st

import repository as repo


def _ensure_user_record() -> None:
    """
    Streamlit confirmed the user with Microsoft. Make sure they have a row
    in our `users` table — create on first SSO sign-in. Cache the matched
    user_id in session_state so the rest of the app can attribute kits and
    scorecards to them.
    """
    if "user_id" in st.session_state:
        return
    email = getattr(st.user, "email", None)
    name = getattr(st.user, "name", None)
    if not email:
        st.error(
            "Microsoft sign-in didn't return an email address. "
            "Sign out and try again with an account that has an email claim."
        )
        st.stop()

    user = repo.get_or_create_user(email, name)
    st.session_state.user_id = user["id"]
    st.session_state.user_email = user["email"]
    st.session_state.user_name = name or user.get("display_name") or email


def is_logged_in() -> bool:
    """True if Streamlit's OIDC layer says the user is authenticated."""
    return bool(getattr(st.user, "is_logged_in", False))


def render_logout_button() -> None:
    """Show user identity + a Sign-out button in the sidebar. Visible only when logged in."""
    if not is_logged_in():
        return
    st.sidebar.markdown("---")
    name = st.session_state.get("user_name") or st.session_state.get("user_email") or "Signed in"
    st.sidebar.caption(f"Signed in as **{name}**")
    if st.sidebar.button("Sign out", use_container_width=True):
        # Wipe local app state first, then trigger Microsoft logout via Streamlit.
        for key in [
            "user_id", "user_email", "user_name",
            "kit", "kit_id", "validation",
            "scorecard_last_saved_hash", "loaded_scorecard_rows",
        ]:
            st.session_state.pop(key, None)
        st.logout()


def render_login_gate() -> None:
    """Centred sign-in card with the single 'Sign in with Microsoft' button."""
    st.markdown(
        """
        <div style="max-width:540px;margin:80px auto 24px;text-align:center;">
          <h1 style="margin-bottom:8px;font-weight:600;">Interview Kit Generator</h1>
          <p style="color:#888;font-size:1rem;">
            Sign in with your Microsoft account to generate and manage interview kits.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if st.button(
            "Sign in with Microsoft",
            type="primary",
            use_container_width=True,
            key="sso_signin_button",
        ):
            # `st.login()` redirects to the configured IdP (Microsoft Entra)
            # and returns to /oauth2callback. The next rerun will have
            # st.user.is_logged_in == True.
            st.login()


def require_login() -> bool:
    """
    Returns True if the user is signed in (and ensures a matching DB record).
    Otherwise renders the centred login gate; the caller should st.stop().
    """
    if is_logged_in():
        _ensure_user_record()
        return True
    render_login_gate()
    return False
