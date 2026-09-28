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
                options={"require": ["exp", "iat", "sub"]},
            )
        except Exception as e:                      # noqa: BLE001 — see docstring
            print(f"auth: rejected token ({type(e).__name__}: {e})", flush=True)
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


def issue(subject: str, days: int = 30, scopes: list[str] | None = None) -> str:
    """Mint a token. Used by scripts/mcp_token.py; kept here so the claim set
    lives in the same file as the code that checks it."""
    if jwt is None:
        raise RuntimeError("pip install pyjwt")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": subject,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + days * 86400,
            "scopes": scopes or ["transcribe"],
        },
        secret(), algorithm=ALGORITHM,
    )
