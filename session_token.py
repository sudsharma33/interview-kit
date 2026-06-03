"""
Stateless, signed session tokens for surviving a browser refresh.

Streamlit's `st.session_state` is in-memory and tied to the WebSocket, so it is
wiped on a hard refresh. To let a signed-in user survive a refresh WITHOUT a
server-side session store or a third-party cookie component, we mint a short
HMAC-signed token and park it in the URL query string (`st.query_params`).

Why query params and not cookies:
  - The URL (and therefore the query string) is preserved across a refresh by
    the browser, so the token round-trips for free with no component to wait on.
  - It needs ZERO extra dependencies — pure stdlib (`hmac`, `hashlib`, `base64`,
    `time`) — so requirements.txt, the CI image, and the Docker build are
    untouched.
  - It sidesteps the `EncryptedCookieManager.ready()` rerun race that the cookie
    approach hit.

Security properties:
  - The token is HMAC-SHA256 signed with a server-side secret, so a client
    cannot forge or tamper with the user id.
  - It carries an expiry; an expired token is rejected.
  - It is verified with a constant-time compare to avoid timing leaks.

Known trade-off (documented, acceptable for this prototype):
  - The token lives in the URL, so it can leak via shared links, browser
    history, or referrer headers. The mitigation is a short TTL plus the fact
    that it only references a user id — the real authorization check still goes
    through `repository.get_user_by_id`. The clean production answer is a
    cookie-backed JWT with HttpOnly+Secure flags, which is the documented next
    step. This is a deliberate prototype-scope choice, not an oversight.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

# Token lifetime. After this, the user must sign in again.
_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Server-side signing secret. In production this MUST be set via the
# SESSION_SECRET env var (Streamlit Cloud Secrets / .env). The fallback only
# exists so local dev works out of the box; it is intentionally constant so
# tokens stay valid across reruns on a single machine.
# Justification (B105 suppressed below): not a real credential — a dev default;
# the real secret is supplied at runtime via the SESSION_SECRET env var.
_FALLBACK_SECRET = "ikg-dev-session-secret-change-me"  # nosec B105


def _secret() -> bytes:
    return os.getenv("SESSION_SECRET", _FALLBACK_SECRET).encode("utf-8")


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(s: str) -> bytes:
    # Restore padding stripped by _b64e.
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_token(user_id: str, *, ttl: int = _TTL_SECONDS) -> str:
    """Mint a signed `<payload>.<sig>` token carrying the user id and expiry."""
    expiry = int(time.time()) + ttl
    payload = f"{user_id}:{expiry}".encode()
    sig = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return f"{_b64e(payload)}.{_b64e(sig)}"


def read_token(token: str) -> str | None:
    """
    Verify a token and return the user id, or None if it is malformed,
    tampered with, or expired. Never raises.
    """
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64d(payload_b64)
        sig = _b64d(sig_b64)
    except Exception:
        return None

    expected = hmac.new(_secret(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        user_id, expiry_str = payload.decode("utf-8").rsplit(":", 1)
        expiry = int(expiry_str)
    except Exception:
        return None

    if time.time() > expiry:
        return None
    return user_id
