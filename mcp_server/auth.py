"""
JWT bearer authentication for the HTTP transports.

Why this exists: stdio needs no authentication, because the client spawned the
process and already has whatever access that implies. The moment you switch to
streamable-http you are listening on a socket, and anything that can reach it
can transcribe. The MCP specification's answer is OAuth 2.1 bearer tokens; this
implements the verification half with self-issued JWTs, which is the right size
for a service you host yourself.

Verification only. There is no authorisation server here, no dynamic client
registration and no refresh flow — you mint tokens with scripts/mcp_token.py and
hand them out. If you later need real OAuth, `MCPServer` also accepts an
`auth_server_provider`, and this verifier can be replaced without touching the
tools.

Algorithm: HS256 by default — one shared secret, which is appropriate when the
same person runs the server and issues the tokens. If tokens must be issued
somewhere the server does not trust with a signing key, switch to RS256 and give
the verifier only the public key.
"""
from __future__ import annotations

import os
import time

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None

from mcp.server.auth.provider import AccessToken, TokenVerifier

# Two token types, and they must never be interchangeable.
#
#   access   short-lived, carries the scopes that let it call tools
#   refresh  long-lived, carries NOTHING but the right to mint a new access
#            token — it cannot call a tool
#
# Why bother: a long-lived access token that leaks is usable until it expires,
# and you cannot tell it has leaked. A short one limits that window to minutes,
# and the refresh token that replaces it is sent only when refreshing, not on
# every call, so it spends far less time in transit and in logs.
#
# The classic bug here is TYPE CONFUSION: if the two are only distinguished by
# their scopes, a caller can present a refresh token as an access token and the
# verifier, seeing a valid signature, accepts it. So the type is an explicit
# `typ` claim and is checked on every path.
TYP_ACCESS = "access"
TYP_REFRESH = "refresh"

ACCESS_MINUTES = int(os.environ.get("MCP_JWT_ACCESS_MINUTES", "15"))
REFRESH_DAYS = int(os.environ.get("MCP_JWT_REFRESH_DAYS", "30"))

ISSUER = os.environ.get("MCP_JWT_ISSUER", "indic-transcribe")
AUDIENCE = os.environ.get("MCP_JWT_AUDIENCE", "indic-transcribe-mcp")
ALGORITHM = os.environ.get("MCP_JWT_ALG", "HS256")
SECRET_ENV = "MCP_JWT_SECRET"


class MissingSecret(RuntimeError):
    pass


def secret() -> str:
    """
    The signing/verification key, from the environment only.

    Never read from a file in the repository and never defaulted. A default
    secret is worse than no authentication, because it looks like security.
    """
    s = os.environ.get(SECRET_ENV, "").strip()
    if not s:
        raise MissingSecret(
            f"{SECRET_ENV} is not set.\n"
            f"  Generate one:  python scripts/mcp_token.py --new-secret\n"
            f"  Then:          export {SECRET_ENV}='...'\n"
            f"HTTP transports refuse to start without it — an open transcription\n"
            f"endpoint on your network is not a reasonable default.")
    if ALGORITHM.startswith("HS") and len(s) < 32:
        raise MissingSecret(
            f"{SECRET_ENV} is {len(s)} characters; HS256 needs at least 32. "
            f"Generate one with: python scripts/mcp_token.py --new-secret")
    return s


class JWTVerifier(TokenVerifier):
    """
    Verifies a bearer token and returns what it is allowed to do.

    Returning None means rejected. The SDK turns that into a 401; the reason is
    deliberately not sent to the caller, because "signature invalid" versus
    "expired" versus "wrong audience" is useful to an attacker and useless to a
    legitimate client, whose token either works or needs reissuing. The reason
    IS logged server-side.
    """

    def __init__(self, required_scopes: list[str] | None = None) -> None:
        if jwt is None:
            raise RuntimeError("HTTP transports need PyJWT: pip install pyjwt")
        self._secret = secret()
        self._required = set(required_scopes or [])

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(
                token, self._secret, algorithms=[ALGORITHM],
                audience=AUDIENCE, issuer=ISSUER,
                # exp and iat are verified; a token without exp is rejected
                # rather than treated as eternal.
                options={"require": ["exp", "iat", "sub", "typ"]},
            )
        except Exception as e:                      # noqa: BLE001 — see docstring
            print(f"auth: rejected token ({type(e).__name__}: {e})", flush=True)
            return None

        # A refresh token is not an access token. Without this check a caller
        # could present their long-lived refresh token to call tools, which
        # would defeat the entire reason for having a short access lifetime.
        if claims.get("typ") != TYP_ACCESS:
            print(f"auth: rejected {claims.get('typ')!r} token where access was required",
                  flush=True)
            return None

        scopes = claims.get("scopes") or []
        if isinstance(scopes, str):
            scopes = scopes.split()
        if self._required and not self._required.issubset(set(scopes)):
            print(f"auth: token for {claims.get('sub')!r} lacks "
                  f"{sorted(self._required - set(scopes))}", flush=True)
            return None

        return AccessToken(
            token=token,
            client_id=str(claims.get("sub")),
            subject=str(claims.get("sub")),
            scopes=list(scopes),
            expires_at=int(claims["exp"]),
            claims=claims,
        )


def _encode(subject: str, typ: str, seconds: int, scopes: list[str]) -> str:
    if jwt is None:
        raise RuntimeError("pip install pyjwt")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": subject,
            "typ": typ,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + seconds,
            "scopes": scopes,
        },
        secret(), algorithm=ALGORITHM,
    )


def issue_access(subject: str, minutes: int | None = None,
                 scopes: list[str] | None = None) -> str:
    """Short-lived, and the only kind that may call a tool."""
    return _encode(subject, TYP_ACCESS,
                   (minutes if minutes is not None else ACCESS_MINUTES) * 60,
                   scopes or ["transcribe"])


def issue_refresh(subject: str, days: int | None = None,
                  scopes: list[str] | None = None) -> str:
    """
    Long-lived, and deliberately useless on its own.

    The scopes are carried so `refresh()` can reissue an access token with the
    same ones, but `typ` keeps this token out of the tool path entirely.
    """
    return _encode(subject, TYP_REFRESH,
                   (days if days is not None else REFRESH_DAYS) * 86400,
                   scopes or ["transcribe"])


def issue_pair(subject: str, scopes: list[str] | None = None) -> dict:
    """Both tokens, as a client would receive them."""
    return {
        "access_token": issue_access(subject, scopes=scopes),
        "refresh_token": issue_refresh(subject, scopes=scopes),
        "token_type": "Bearer",
        "expires_in": ACCESS_MINUTES * 60,
    }


def refresh(refresh_token: str) -> dict | None:
    """
    Exchange a refresh token for a new access token.

    Returns None on any failure, for the same reason verify_token does: the
    caller learns whether it worked, not why.

    What this deliberately does NOT do is rotate the refresh token. Rotation —
    issuing a new refresh token on every exchange and invalidating the old one —
    is the stronger design, because it detects theft: if both the thief and the
    legitimate client use the same refresh token, one of them presents a
    superseded one and you know. But detecting that requires SERVER-SIDE STATE
    (a store of which tokens have been used), and this server is deliberately
    stateless. Adding a half-rotation with nothing to compare against would look
    like protection while providing none. If you need rotation, you need a
    token store first.
    """
    if jwt is None:
        raise RuntimeError("pip install pyjwt")
    try:
        claims = jwt.decode(
            refresh_token, secret(), algorithms=[ALGORITHM],
            audience=AUDIENCE, issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "typ"]},
        )
    except Exception as e:                          # noqa: BLE001
        print(f"auth: refresh rejected ({type(e).__name__}: {e})", flush=True)
        return None

    # An access token must not be usable to mint more access tokens — that would
    # make a leaked access token effectively permanent.
    if claims.get("typ") != TYP_REFRESH:
        print(f"auth: refresh rejected — {claims.get('typ')!r} token, not a refresh token",
              flush=True)
        return None

    scopes = claims.get("scopes") or ["transcribe"]
    if isinstance(scopes, str):
        scopes = scopes.split()
    return {
        "access_token": issue_access(str(claims["sub"]), scopes=scopes),
        "token_type": "Bearer",
        "expires_in": ACCESS_MINUTES * 60,
    }
