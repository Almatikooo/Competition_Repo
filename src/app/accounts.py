"""Optional accounts: sign in with Google or GitHub to keep your progress.

Guests need no account: their browser keeps the profile, plans, courses and AI Chat for the current tab only
(sessionStorage), so everything is gone when the tab is closed. A person who signs in with Google gets the same data
saved to their account here, and loaded again on any device. GitHub works the same way (OAuth app; the profile
and, when it is private, the primary verified email come from GitHub's API with the one-time access token).

* Sign-in is Google's OAuth 2.0 authorization-code flow with PKCE. A signed, short-lived cookie carries the state and
  the code verifier, and the ID token comes straight from Google's token endpoint over TLS, so its claims (issuer,
  audience, expiry) are checked without a signature check (OpenID Connect Core 3.1.3.7).
* The session is an HMAC-signed cookie (HttpOnly, SameSite=Lax, Secure on HTTPS) holding the account id, the account's
  random session epoch and a time. Signing out or deleting the account changes or removes the epoch, so every earlier
  cookie stops working at once; ids are never reused. No password is ever stored.
* Stored per account: Google's subject id, email, name and picture URL, and the progress keys the page syncs
  (SYNCED_KEYS). Deleting the account deletes all of it.
"""
import base64
import datetime as dt
import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import closing
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from . import config
from .learn import sign, unsign

router = APIRouter()
transport: httpx.AsyncBaseTransport | None = None    # tests put a fake Google here

SESSION_COOKIE, STATE_COOKIE = "pathai_session", "pathai_oauth"
SESSION_DAYS = 30
STATE_TTL = 600                                       # seconds to finish signing in at Google
SYNCED_KEYS = {"profile", "origin", "tiles", "progress", "learned", "certs", "certName", "coach", "next", "focusRole"}
MAX_VALUE = 200_000                                   # characters of JSON per key
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GITHUB_AUTH = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_API = "https://api.github.com"


def google_ready() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def github_ready() -> bool:
    return bool(config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET)


# ---------------------------------------------------------------- storage

def _db() -> sqlite3.Connection:
    config.ACCOUNTS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.ACCOUNTS_DB, timeout=5)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, subject TEXT NOT NULL,
                   email TEXT, name TEXT, picture TEXT, session_epoch TEXT, created_at TEXT, last_login TEXT, UNIQUE(provider, subject))""")
    if "session_epoch" not in {row[1] for row in con.execute("PRAGMA table_info(users)")}:     # a database from before epochs
        con.execute("ALTER TABLE users ADD COLUMN session_epoch TEXT")
    con.execute("""CREATE TABLE IF NOT EXISTS user_state (user_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                   updated_at TEXT, PRIMARY KEY (user_id, key))""")
    return con


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def upsert_user(provider: str, subject: str, email: str | None, name: str | None, picture: str | None) -> tuple[int, str]:
    """(account id, session epoch). Signing in again keeps the epoch, so the person's other devices stay signed in."""
    with closing(_db()) as con, con:
        con.execute("""INSERT INTO users (provider, subject, email, name, picture, session_epoch, created_at, last_login)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(provider, subject) DO UPDATE SET email=excluded.email, name=excluded.name, picture=excluded.picture,
                       session_epoch=COALESCE(users.session_epoch, excluded.session_epoch), last_login=excluded.last_login""",
                    (provider, subject, email, name, picture, secrets.token_urlsafe(16), _now(), _now()))
        return con.execute("SELECT id, session_epoch FROM users WHERE provider=? AND subject=?", (provider, subject)).fetchone()


def _revoke_sessions(user_id: int) -> None:
    """A new epoch: every cookie issued before stops working, on every device."""
    with closing(_db()) as con, con:
        con.execute("UPDATE users SET session_epoch=? WHERE id=?", (secrets.token_urlsafe(16), user_id))


def _user(user_id: int) -> dict | None:
    with closing(_db()) as con:
        row = con.execute("SELECT name, email, picture FROM users WHERE id=?", (user_id,)).fetchone()
    return {"name": row[0], "email": row[1], "picture": row[2]} if row else None


def _state(user_id: int) -> dict:
    with closing(_db()) as con:
        return {k: json.loads(v) for k, v in con.execute("SELECT key, value FROM user_state WHERE user_id=?", (user_id,))}


# ---------------------------------------------------------------- sessions

def _secure(request: Request) -> bool:
    return request.url.scheme == "https"


def session_user(request: Request) -> int | None:
    data = unsign("session", request.cookies.get(SESSION_COOKIE))
    if not data or time.time() - data.get("t", 0) > SESSION_DAYS * 86400 or not isinstance(data.get("u"), int):
        return None
    with closing(_db()) as con:
        row = con.execute("SELECT session_epoch FROM users WHERE id=?", (data["u"],)).fetchone()
    if not row or not row[0] or not secrets.compare_digest(str(row[0]), str(data.get("e", ""))):
        return None                       # signed out, deleted, or a cookie from before
    return data["u"]


def _safe_next(target: str | None) -> str:
    """Only a path on this site: a sign-in link must not send anyone elsewhere afterwards."""
    return target if target and target.startswith("/") and not target.startswith("//") and "\\" not in target else "/"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _claims(id_token: str) -> dict:
    payload = id_token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def _begin(request: Request, provider: str, auth_url: str, params: dict, next_path: str) -> RedirectResponse:
    """Off to the provider: a fresh state and PKCE verifier ride in a signed, short-lived cookie."""
    nonce, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(48)
    query = {**params, "state": nonce, "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
    resp = RedirectResponse(f"{auth_url}?{urlencode(query)}", status_code=303)
    resp.set_cookie(STATE_COOKIE, sign("oauth", {"p": provider, "n": nonce, "v": verifier, "r": _safe_next(next_path), "t": int(time.time())}),
                    max_age=STATE_TTL, httponly=True, secure=_secure(request), samesite="lax", path="/auth")
    return resp


def _check_state(request: Request, provider: str, state: str) -> dict:
    data = unsign("oauth", request.cookies.get(STATE_COOKIE))
    if (not data or data.get("p") != provider or time.time() - data.get("t", 0) > STATE_TTL
            or not secrets.compare_digest(str(data.get("n")), state)):
        raise HTTPException(400, "This sign-in link has expired. Please try again.")
    return data


def _signed_in(request: Request, back: str, provider: str, subject: str, email: str | None, name: str | None, picture: str | None):
    user_id, epoch = upsert_user(provider, subject, email, name, picture)
    out = RedirectResponse(back, status_code=303)
    out.set_cookie(SESSION_COOKIE, sign("session", {"u": user_id, "e": epoch, "t": int(time.time())}), max_age=SESSION_DAYS * 86400,
                   httponly=True, secure=_secure(request), samesite="lax", path="/")
    out.delete_cookie(STATE_COOKIE, path="/auth")
    return out


@router.get("/auth/google")
def google_start(request: Request, next: str = "/"):
    if not google_ready():
        raise HTTPException(404, "Sign-in with Google is not set up on this server.")
    return _begin(request, "google", GOOGLE_AUTH, {"client_id": config.GOOGLE_CLIENT_ID, "redirect_uri": str(request.url_for("google_callback")),
                                                     "response_type": "code", "scope": "openid email profile", "prompt": "select_account"}, next)


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    data = _check_state(request, "google", state)
    back = data.get("r", "/")
    if error or not code:                                 # the person cancelled at Google
        return RedirectResponse(back, status_code=303)
    async with httpx.AsyncClient(timeout=15, transport=transport) as client:
        resp = await client.post(GOOGLE_TOKEN, data={"code": code, "client_id": config.GOOGLE_CLIENT_ID, "client_secret": config.GOOGLE_CLIENT_SECRET,
                                                      "redirect_uri": str(request.url_for("google_callback")), "grant_type": "authorization_code",
                                                      "code_verifier": data.get("v", "")})
    if resp.status_code != 200 or "id_token" not in resp.json():
        raise HTTPException(400, "Google did not confirm the sign-in. Please try again.")
    claims = _claims(resp.json()["id_token"])
    if claims.get("iss") not in GOOGLE_ISSUERS or claims.get("aud") != config.GOOGLE_CLIENT_ID or claims.get("exp", 0) < time.time() or not claims.get("sub"):
        raise HTTPException(400, "Google's answer did not check out. Please try again.")
    return _signed_in(request, back, "google", claims["sub"], claims.get("email"), claims.get("name"), claims.get("picture"))


@router.get("/auth/github")
def github_start(request: Request, next: str = "/"):
    if not github_ready():
        raise HTTPException(404, "Sign-in with GitHub is not set up on this server.")
    return _begin(request, "github", GITHUB_AUTH, {"client_id": config.GITHUB_CLIENT_ID, "redirect_uri": str(request.url_for("github_callback")),
                                                     "scope": "read:user user:email", "allow_signup": "true"}, next)


@router.get("/auth/github/callback", name="github_callback")
async def github_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    data = _check_state(request, "github", state)
    back = data.get("r", "/")
    if error or not code:                                 # the person cancelled at GitHub
        return RedirectResponse(back, status_code=303)
    async with httpx.AsyncClient(timeout=15, transport=transport) as client:
        tok = await client.post(GITHUB_TOKEN, headers={"Accept": "application/json"},
                                data={"client_id": config.GITHUB_CLIENT_ID, "client_secret": config.GITHUB_CLIENT_SECRET, "code": code,
                                      "redirect_uri": str(request.url_for("github_callback")), "code_verifier": data.get("v", "")})
        token = tok.json().get("access_token") if tok.status_code == 200 else None
        if not token:
            raise HTTPException(400, "GitHub did not confirm the sign-in. Please try again.")
        auth = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        user = (await client.get(f"{GITHUB_API}/user", headers=auth)).json()
        email = user.get("email")
        if not email:                                     # a private email: the primary verified one
            listed = await client.get(f"{GITHUB_API}/user/emails", headers=auth)
            if listed.status_code == 200:
                email = next((e.get("email") for e in listed.json() if e.get("primary") and e.get("verified")), None)
    if not user.get("id"):
        raise HTTPException(400, "GitHub's answer did not check out. Please try again.")
    return _signed_in(request, back, "github", str(user["id"]), email, user.get("name") or user.get("login"), user.get("avatar_url"))


@router.post("/auth/logout")
def logout(request: Request):
    user_id = session_user(request)
    if user_id is not None:
        _revoke_sessions(user_id)           # a copied cookie stops working too
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


# ---------------------------------------------------------------- the person's saved progress

class StateUpdate(BaseModel):
    state: dict[str, object] = Field(max_length=len(SYNCED_KEYS))


@router.get("/api/me")
def me(request: Request) -> dict:
    user_id = session_user(request)
    providers = {"google": google_ready(), "github": github_ready()}
    if user_id is None:
        return {"user": None, "state": {}, "providers": providers}
    return {"user": _user(user_id), "state": _state(user_id), "providers": providers}


@router.put("/api/me/state")
def save_state(request: Request, body: StateUpdate) -> dict:
    user_id = session_user(request)
    if user_id is None:
        raise HTTPException(401, "Sign in to save your progress.")
    rows = []
    for key, value in body.state.items():
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if key not in SYNCED_KEYS or len(text) > MAX_VALUE:
            raise HTTPException(422, f"Cannot save {key!r}.")
        rows.append((user_id, key, text, _now()))
    with closing(_db()) as con, con:
        con.executemany("""INSERT INTO user_state (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
                           ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""", rows)
    return {"saved": len(rows)}


@router.delete("/api/me")
def delete_account(request: Request):
    user_id = session_user(request)
    if user_id is None:
        raise HTTPException(401, "Not signed in.")
    with closing(_db()) as con, con:
        con.execute("DELETE FROM user_state WHERE user_id=?", (user_id,))
        con.execute("DELETE FROM users WHERE id=?", (user_id,))
    resp = JSONResponse({"deleted": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp
