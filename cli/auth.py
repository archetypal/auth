#!/usr/bin/env python3
"""
Generic OIDC CLI using the OAuth 2.0 Device Authorization Grant (RFC 8628).

Works with any OpenID Connect provider that advertises a
device_authorization_endpoint via well-known discovery (Zitadel, Auth0,
Keycloak, Okta, Microsoft Entra, Google, ...).

  auth login --issuer https://idp.example.com --client-id CID
  auth whoami
  auth token                  # prints a valid access token (refreshes if needed)
  auth call https://api/foo   # GET url with Bearer token
  auth logout                 # revoke tokens and clear profile
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_SCOPE = "openid profile email offline_access"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "auth-cli"


def profile_path(profile: str) -> Path:
    return CONFIG_DIR / f"{profile}.json"


def load_profile(profile: str) -> dict:
    p = profile_path(profile)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_profile(profile: str, data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    p = profile_path(profile)
    p.write_text(json.dumps(data, indent=2))
    p.chmod(0o600)


def http_post(url: str, form: dict, *, basic_auth: tuple[str, str] | None = None) -> dict:
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    if basic_auth:
        creds = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        payload = e.read().decode(errors="replace")
        try:
            return {"_status": e.code, **json.loads(payload)}
        except json.JSONDecodeError:
            return {"_status": e.code, "error": "http_error", "error_description": payload}


def http_get(url: str, *, bearer: str | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def discover(issuer: str) -> dict:
    status, body = http_get(f"{issuer.rstrip('/')}/.well-known/openid-configuration")
    if status != 200:
        raise SystemExit(f"OIDC discovery failed ({status}): {body}")
    return json.loads(body)


def now() -> int:
    return int(time.time())


def store_tokens(profile_data: dict, token_response: dict) -> dict:
    expires_in = int(token_response.get("expires_in", 0))
    tokens = {
        "access_token": token_response["access_token"],
        "token_type": token_response.get("token_type", "Bearer"),
        "expires_at": now() + expires_in if expires_in else 0,
        "scope": token_response.get("scope"),
    }
    if "refresh_token" in token_response:
        tokens["refresh_token"] = token_response["refresh_token"]
    if "id_token" in token_response:
        tokens["id_token"] = token_response["id_token"]
    profile_data["tokens"] = tokens
    return profile_data


def basic_for(cfg: dict) -> tuple[str, str] | None:
    secret = cfg.get("client_secret")
    return (cfg["client_id"], secret) if secret else None


def refresh_tokens(profile_data: dict) -> dict:
    tokens = profile_data.get("tokens", {})
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise SystemExit("Access token expired and no refresh token; run `auth login` again.")
    cfg = profile_data["config"]
    disc = profile_data["discovery"]
    resp = http_post(
        disc["token_endpoint"],
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": cfg["client_id"],
        },
        basic_auth=basic_for(cfg),
    )
    if "access_token" not in resp:
        raise SystemExit(f"Token refresh failed: {resp}. Run `auth login` again.")
    return store_tokens(profile_data, resp)


def ensure_fresh(profile_data: dict, skew: int = 30) -> dict:
    tokens = profile_data.get("tokens", {})
    if tokens.get("expires_at", 0) - skew <= now():
        return refresh_tokens(profile_data)
    return profile_data


def require_login(profile: str) -> dict:
    data = load_profile(profile)
    if not data.get("tokens"):
        raise SystemExit(f"Not logged in (profile '{profile}'). Run `auth login`.")
    return data


def cmd_login(args) -> int:
    existing = load_profile(args.profile).get("config", {})
    issuer = args.issuer or os.environ.get("AUTH_ISSUER") or existing.get("issuer")
    client_id = args.client_id or os.environ.get("AUTH_CLIENT_ID") or existing.get("client_id")
    scope = args.scope or os.environ.get("AUTH_SCOPE") or existing.get("scope") or DEFAULT_SCOPE
    client_secret = (
        args.client_secret
        or os.environ.get("AUTH_CLIENT_SECRET")
        or existing.get("client_secret")
    )

    if not issuer or not client_id:
        raise SystemExit("--issuer and --client-id required (or set AUTH_ISSUER / AUTH_CLIENT_ID).")

    disc = discover(issuer)
    device_endpoint = disc.get("device_authorization_endpoint")
    token_endpoint = disc.get("token_endpoint")
    if not device_endpoint or not token_endpoint:
        raise SystemExit(f"Issuer {issuer} does not advertise device_authorization_endpoint.")

    cfg = {"issuer": issuer.rstrip("/"), "client_id": client_id, "scope": scope}
    if client_secret:
        cfg["client_secret"] = client_secret

    init = http_post(
        device_endpoint,
        {"client_id": client_id, "scope": scope},
        basic_auth=basic_for(cfg),
    )
    if "device_code" not in init:
        raise SystemExit(f"Device authorization request failed: {init}")

    user_code = init["user_code"]
    verification_uri = init.get("verification_uri") or init.get("verification_url", "")
    verification_uri_complete = init.get("verification_uri_complete")
    interval = int(init.get("interval", 5))
    expires_in = int(init.get("expires_in", 600))
    device_code = init["device_code"]

    print("To sign in, open this URL in your browser:")
    print(f"    {verification_uri}")
    print(f"and enter the code:  {user_code}")
    if verification_uri_complete:
        print(f"\nOr open the direct link (code pre-filled):\n    {verification_uri_complete}")
        try:
            webbrowser.open(verification_uri_complete, new=2)
        except webbrowser.Error:
            pass

    print(f"\nWaiting for authorization (expires in {expires_in}s)...", flush=True)
    deadline = now() + expires_in
    while now() < deadline:
        time.sleep(interval)
        resp = http_post(
            token_endpoint,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": client_id,
            },
            basic_auth=basic_for(cfg),
        )
        if "access_token" in resp:
            data = {"config": cfg, "discovery": disc}
            store_tokens(data, resp)
            save_profile(args.profile, data)
            print(f"Authenticated. Tokens saved to {profile_path(args.profile)}")
            return 0
        err = resp.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        raise SystemExit(f"Token exchange failed: {resp}")
    raise SystemExit("Device code expired before authorization.")


def cmd_logout(args) -> int:
    data = load_profile(args.profile)
    tokens = data.get("tokens", {})
    cfg = data.get("config", {})
    revoke_url = data.get("discovery", {}).get("revocation_endpoint")
    if revoke_url and tokens:
        for hint, tok in (
            ("refresh_token", tokens.get("refresh_token")),
            ("access_token", tokens.get("access_token")),
        ):
            if not tok:
                continue
            http_post(
                revoke_url,
                {"token": tok, "token_type_hint": hint, "client_id": cfg.get("client_id", "")},
                basic_auth=basic_for(cfg),
            )
    p = profile_path(args.profile)
    if p.exists():
        p.unlink()
    print(f"Logged out of profile '{args.profile}'.")
    return 0


def cmd_token(args) -> int:
    data = ensure_fresh(require_login(args.profile))
    save_profile(args.profile, data)
    print(data["tokens"]["access_token"])
    return 0


def cmd_whoami(args) -> int:
    data = ensure_fresh(require_login(args.profile))
    save_profile(args.profile, data)
    userinfo_url = data["discovery"].get("userinfo_endpoint")
    if not userinfo_url:
        raise SystemExit("Issuer does not advertise a userinfo_endpoint.")
    status, body = http_get(userinfo_url, bearer=data["tokens"]["access_token"])
    if status != 200:
        raise SystemExit(f"userinfo failed ({status}): {body}")
    print(body)
    return 0


def cmd_call(args) -> int:
    data = ensure_fresh(require_login(args.profile))
    save_profile(args.profile, data)
    status, body = http_get(args.url, bearer=data["tokens"]["access_token"])
    sys.stdout.write(body)
    if not body.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if status < 400 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auth", description="OIDC device-code CLI")
    parser.add_argument("--profile", default="default", help="Named credential profile (default: 'default')")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="Authenticate via device code flow")
    p_login.add_argument("--issuer", help="OIDC issuer base URL (env: AUTH_ISSUER)")
    p_login.add_argument("--client-id", help="OAuth client id (env: AUTH_CLIENT_ID)")
    p_login.add_argument("--client-secret", help="Only for confidential clients (env: AUTH_CLIENT_SECRET)")
    p_login.add_argument("--scope", help=f"OAuth scopes (env: AUTH_SCOPE, default: '{DEFAULT_SCOPE}')")
    p_login.set_defaults(func=cmd_login)

    sub.add_parser("logout", help="Revoke tokens and delete the profile").set_defaults(func=cmd_logout)
    sub.add_parser("token", help="Print a valid access token (refreshes if needed)").set_defaults(func=cmd_token)
    sub.add_parser("whoami", help="Call the userinfo endpoint").set_defaults(func=cmd_whoami)

    p_call = sub.add_parser("call", help="GET a URL with the Bearer token")
    p_call.add_argument("url")
    p_call.set_defaults(func=cmd_call)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
