# Auth CLI

A generic Python CLI that authenticates to any OpenID Connect provider using
the OAuth 2.0 **Device Authorization Grant** ([RFC 8628](https://datatracker.ietf.org/doc/html/rfc8628)).

Stdlib only — no `pip install` required. Tested against Zitadel; should also
work with Auth0, Keycloak, Okta, Microsoft Entra, and Google.

## Install

```sh
chmod +x cli/auth.py
ln -s "$PWD/cli/auth.py" /usr/local/bin/auth   # optional
```

Or just run as `./cli/auth.py ...` / `python3 cli/auth.py ...`.

## Usage

```sh
auth login \
  --issuer https://<host>.us1.zitadel.cloud \
  --client-id 373933063840786304

auth whoami
auth token                              # prints a valid access token
auth call http://api.example.local/api/hello
auth logout
```

Flags can also be set via env vars: `AUTH_ISSUER`, `AUTH_CLIENT_ID`,
`AUTH_CLIENT_SECRET`, `AUTH_SCOPE`.

After the first `login`, the issuer and client id are remembered in the
profile, so later `auth login` calls don't need them again.

## Profiles

Multiple identities/providers via `--profile`:

```sh
auth --profile work login --issuer ... --client-id ...
auth --profile work whoami

auth --profile personal login --issuer ... --client-id ...
auth --profile personal token
```

Tokens are stored under `$XDG_CONFIG_HOME/auth-cli/<profile>.json` (mode 0600).

## How it works

1. `GET {issuer}/.well-known/openid-configuration` — discover endpoints.
2. `POST` to `device_authorization_endpoint` with `client_id` and `scope`.
3. Print the `user_code` + `verification_uri`; open
   `verification_uri_complete` in the browser if provided.
4. Poll `token_endpoint` with `grant_type=urn:ietf:params:oauth:grant-type:device_code`,
   honoring `authorization_pending` / `slow_down` / `expires_in`.
5. Persist tokens. Subsequent `token` / `whoami` / `call` invocations refresh
   automatically using `refresh_token` when the access token is near expiry.

## Troubleshooting

**`CERTIFICATE_VERIFY_FAILED` on macOS**: the python.org installer doesn't wire
up the system trust store. Run once:

```sh
/Applications/Python\ 3.*/Install\ Certificates.command
```

Or use the Homebrew / system Python instead.

## Provider notes

- **Zitadel**: the application's grant types must include "Device
  Authorization". For an SPA/native client (no client secret), omit
  `--client-secret`. Include `offline_access` in the scope to get a refresh
  token (default scope already does).
- **Auth0**: requires an API audience for access tokens; pass it via
  `--scope "openid offline_access ..." ` along with an `audience` param —
  Auth0 needs the `audience` form field on the device authorization request.
  This CLI does not yet pass `audience`; add it if you target Auth0.
