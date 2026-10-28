"""Optional accounts: sign in with Google (a fake Google stands in), keep progress in the account, sign out, delete it.
Guests need no account at all."""
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts, config
from app.main import app


def fake_id_token(**claims) -> str:
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{part({'alg': 'RS256'})}.{part(claims)}.sig"


@pytest.fixture
def google(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "client-123.apps.googleusercontent.com")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setattr(config, "ACCOUNTS_DB", tmp_path / "accounts.sqlite3")
    seen = {"claims": {"iss": "https://accounts.google.com", "aud": "client-123.apps.googleusercontent.com", "sub": "1001",
                       "email": "aisyah@example.com", "name": "Aisyah", "picture": "https://example.com/a.png", "exp": time.time() + 600}}

    def token_endpoint(request: httpx.Request) -> httpx.Response:
        seen["form"] = parse_qs(request.content.decode())
        return httpx.Response(200, json={"id_token": fake_id_token(**seen["claims"]), "access_token": "x"})

    monkeypatch.setattr(accounts, "transport", httpx.MockTransport(token_endpoint))
    return seen


def sign_in(client: TestClient, next_path="/#/learn") -> str:
    start = client.get("/auth/google", params={"next": next_path}, follow_redirects=False)
    assert start.status_code == 303 and start.headers["location"].startswith(accounts.GOOGLE_AUTH)
    q = parse_qs(urlparse(start.headers["location"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["scope"] == ["openid email profile"]
    back = client.get("/auth/google/callback", params={"code": "c0de", "state": q["state"][0]}, follow_redirects=False)
    return back


def test_guests_need_no_account():
    client = TestClient(app)
    assert client.get("/api/me").json()["user"] is None
    assert client.put("/api/me/state", json={"state": {"profile": {}}}).status_code == 401


def test_sign_in_keeps_progress_in_the_account(google):
    client = TestClient(app)
    back = sign_in(client)
    assert back.status_code == 303 and back.headers["location"] == "/#/learn"
    assert google["form"]["code_verifier"][0] and google["form"]["grant_type"] == ["authorization_code"]
    me = client.get("/api/me").json()
    assert {k: me["user"][k] for k in ("name", "email", "picture", "provider")} == {
        "name": "Aisyah", "email": "aisyah@example.com", "picture": "https://example.com/a.png", "provider": "google"}
    assert len(me["user"]["since"]) == 10                       # the day the account was made
    progress = {"data_analyst": {"sql": True}}
    assert client.put("/api/me/state", json={"state": {"progress": progress, "lang": "ms"}}).status_code == 422   # only progress keys
    assert client.put("/api/me/state", json={"state": {"progress": progress}}).json() == {"saved": 1}
    other_device = TestClient(app)                     # signing in again elsewhere brings the progress back
    sign_in(other_device)
    assert other_device.get("/api/me").json()["state"] == {"progress": progress}
    assert client.post("/auth/logout").json() == {"ok": True}
    assert client.get("/api/me").json()["user"] is None


def test_deleting_the_account_deletes_its_data(google):
    client = TestClient(app)
    sign_in(client)
    client.put("/api/me/state", json={"state": {"coach": [{"role": "user", "content": "hi"}]}})
    assert client.delete("/api/me").json() == {"deleted": True}
    assert client.get("/api/me").json()["user"] is None
    again = TestClient(app)
    sign_in(again)
    assert again.get("/api/me").json()["state"] == {}               # a new, empty account


def test_a_forged_or_foreign_sign_in_is_refused(google):
    client = TestClient(app)
    client.get("/auth/google", follow_redirects=False)
    assert client.get("/auth/google/callback", params={"code": "c", "state": "not-ours"}, follow_redirects=False).status_code == 400
    google["claims"]["aud"] = "someone-elses-client"
    start = client.get("/auth/google", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    assert client.get("/auth/google/callback", params={"code": "c", "state": state}, follow_redirects=False).status_code == 400
    assert client.get("/api/me").json()["user"] is None


def test_after_sign_in_only_pages_on_this_site(google):
    client = TestClient(app)
    assert sign_in(client, next_path="https://evil.example/").headers["location"] == "/"
    assert sign_in(TestClient(app), next_path="//evil.example").headers["location"] == "/"


def test_without_google_keys_sign_in_is_off(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    client = TestClient(app)
    assert client.get("/auth/google", follow_redirects=False).status_code == 404
    assert client.get("/api/me").json()["providers"]["google"] is False


def test_an_old_cookie_never_opens_an_account(google):
    first = TestClient(app)
    sign_in(first)
    copied = first.cookies.get(accounts.SESSION_COOKIE)              # e.g. still on another device
    first.delete("/api/me")
    google["claims"]["sub"] = "2002"                                 # a new person signs up after the deletion
    newcomer = TestClient(app)
    sign_in(newcomer)
    assert newcomer.get("/api/me").json()["user"]["email"] == "aisyah@example.com"
    stale = TestClient(app, cookies={accounts.SESSION_COOKIE: copied})
    assert stale.get("/api/me").json()["user"] is None               # the deleted account's cookie opens nothing


def test_signing_out_revokes_every_copy_of_the_cookie(google):
    client = TestClient(app)
    sign_in(client)
    copied = client.cookies.get(accounts.SESSION_COOKIE)
    client.post("/auth/logout")
    assert TestClient(app, cookies={accounts.SESSION_COOKIE: copied}).get("/api/me").json()["user"] is None



@pytest.fixture
def github(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GITHUB_CLIENT_ID", "Iv1.github-client")
    monkeypatch.setattr(config, "GITHUB_CLIENT_SECRET", "gh-secret")
    monkeypatch.setattr(config, "ACCOUNTS_DB", tmp_path / "accounts.sqlite3")
    seen = {"user": {"id": 1001, "login": "aisyah-dev", "name": None, "email": None, "avatar_url": "https://avatars.example/a.png"}}

    def github_api(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            seen["form"] = parse_qs(request.content.decode())
            return httpx.Response(200, json={"access_token": "gho_token", "token_type": "bearer"})
        assert request.headers["authorization"] == "Bearer gho_token"
        if request.url.path == "/user":
            return httpx.Response(200, json=seen["user"])
        return httpx.Response(200, json=[{"email": "old@example.com", "primary": False, "verified": True},
                                         {"email": "aisyah@users.example", "primary": True, "verified": True}])

    monkeypatch.setattr(accounts, "transport", httpx.MockTransport(github_api))
    return seen


def test_sign_in_with_github_finds_a_private_email(github):
    client = TestClient(app)
    start = client.get("/auth/github", params={"next": "/#/chat"}, follow_redirects=False)
    assert start.headers["location"].startswith(accounts.GITHUB_AUTH)
    q = parse_qs(urlparse(start.headers["location"]).query)
    assert q["scope"] == ["read:user user:email"] and q["code_challenge_method"] == ["S256"]
    back = client.get("/auth/github/callback", params={"code": "c0de", "state": q["state"][0]}, follow_redirects=False)
    assert back.status_code == 303 and back.headers["location"] == "/#/chat" and github["form"]["code_verifier"][0]
    user = client.get("/api/me").json()["user"]
    assert (user["name"], user["email"], user["picture"], user["provider"]) == ("aisyah-dev", "aisyah@users.example", "https://avatars.example/a.png", "github")


def test_a_state_from_one_provider_does_not_work_for_another(github, google):
    client = TestClient(app)
    start = client.get("/auth/google", follow_redirects=False)                # the state was made for Google...
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    assert client.get("/auth/github/callback", params={"code": "c", "state": state}, follow_redirects=False).status_code == 400


@pytest.fixture
def apple(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    (tmp_path / "key.p8").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    for name, value in (("APPLE_CLIENT_ID", "lol.pathai.signin"), ("APPLE_TEAM_ID", "TEAM123456"), ("APPLE_KEY_ID", "KEY1234567"),
                        ("APPLE_PRIVATE_KEY", ""), ("APPLE_PRIVATE_KEY_FILE", tmp_path / "key.p8"), ("ACCOUNTS_DB", tmp_path / "accounts.sqlite3")):
        monkeypatch.setattr(config, name, value)
    seen = {"public": key.public_key()}

    def token_endpoint(request: httpx.Request) -> httpx.Response:
        seen["secret"] = parse_qs(request.content.decode())["client_secret"][0]
        return httpx.Response(200, json={"id_token": fake_id_token(iss="https://appleid.apple.com", aud="lol.pathai.signin", sub="001234.apple",
                                                                    email="x@privaterelay.appleid.com", exp=time.time() + 600, nonce=seen.get("nonce", ""))})

    monkeypatch.setattr(accounts, "transport", httpx.MockTransport(token_endpoint))
    return seen


def verify_es256(token: str, public_key) -> tuple[dict, dict]:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    pad = lambda x: x + "=" * (-len(x) % 4)
    head, body, sig = token.split(".")
    raw = base64.urlsafe_b64decode(pad(sig))
    public_key.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), f"{head}.{body}".encode(),
                      ec.ECDSA(hashes.SHA256()))                                  # raises if the signature is wrong
    return json.loads(base64.urlsafe_b64decode(pad(head))), json.loads(base64.urlsafe_b64decode(pad(body)))


def apple_sign_in(client: TestClient, seen: dict, user: dict | None = None):
    start = client.get("/auth/apple", params={"next": "/#/me"}, follow_redirects=False)
    q = parse_qs(urlparse(start.headers["location"]).query)
    assert q["response_mode"] == ["form_post"] and q["scope"] == ["name email"] and "code_challenge" not in q
    cookie = start.headers["set-cookie"].lower()
    assert "samesite=none" in cookie and "secure" in cookie                      # Apple posts back from its own site
    seen["nonce"] = q["nonce"][0]
    form = {"code": "c0de", "state": q["state"][0], **({"user": json.dumps(user)} if user else {})}
    return client.post("/auth/apple/callback", data=form, follow_redirects=False)


def test_sign_in_with_apple_keeps_the_name_it_sends_once(apple):
    client = TestClient(app, base_url="https://testserver")
    back = apple_sign_in(client, apple, user={"name": {"firstName": "Aisyah", "lastName": "Rahman"}})
    assert back.status_code == 303 and back.headers["location"] == "/#/me"
    head, body = verify_es256(apple["secret"], apple["public"])
    assert head == {"alg": "ES256", "kid": "KEY1234567"}
    assert (body["iss"], body["sub"], body["aud"]) == ("TEAM123456", "lol.pathai.signin", "https://appleid.apple.com") and body["exp"] - body["iat"] <= 600
    user = client.get("/api/me").json()["user"]
    assert (user["name"], user["email"], user["provider"]) == ("Aisyah Rahman", "x@privaterelay.appleid.com", "apple")
    again = TestClient(app, base_url="https://testserver")
    apple_sign_in(again, apple)                                                    # no name this time
    assert again.get("/api/me").json()["user"]["name"] == "Aisyah Rahman"


def test_an_apple_answer_for_another_nonce_is_refused(apple):
    client = TestClient(app, base_url="https://testserver")
    start = client.get("/auth/apple", follow_redirects=False)
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    apple["nonce"] = "someone-elses-nonce"
    assert client.post("/auth/apple/callback", data={"code": "c", "state": state}, follow_redirects=False).status_code == 400
