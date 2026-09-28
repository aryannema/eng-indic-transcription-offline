#!/usr/bin/env python3
"""
Mint and inspect JWT tokens for the MCP HTTP transports.

stdio needs none of this — the client spawns the process. Tokens exist because
`--transport streamable-http` listens on a socket, and anything that can reach
the socket can transcribe.

    python scripts/mcp_token.py --new-secret
    export MCP_JWT_SECRET='...'

    python scripts/mcp_token.py --issue aryan --days 30
    python scripts/mcp_token.py --inspect <token>

The secret lives in the environment and nowhere else. It is never written into
the repository, and there is no default — a shipped default secret looks like
security while providing none.
"""
import argparse
import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--new-secret", action="store_true",
                   help="print a fresh 64-character secret")
    g.add_argument("--issue", metavar="SUBJECT",
                   help="mint a token for this subject (a person or a service)")
    g.add_argument("--inspect", metavar="TOKEN",
                   help="decode and verify a token")
    ap.add_argument("--days", type=int, default=30,
                    help="lifetime (default 30). Short is better: revocation is "
                         "not implemented, so expiry IS the revocation mechanism.")
    ap.add_argument("--scopes", default="transcribe",
                    help="space-separated scopes (default: transcribe)")
    a = ap.parse_args()

    if a.new_secret:
        print(secrets.token_urlsafe(48))
        print("\n  export MCP_JWT_SECRET='<the line above>'", file=sys.stderr)
        print("  Put it in the shell profile of the account running the server.",
              file=sys.stderr)
        print("  Do NOT commit it. Rotating is cheap; a leaked secret is not made",
              file=sys.stderr)
        print("  safe by deleting the commit that contained it.", file=sys.stderr)
        return 0

    try:
        from mcp_server.auth import issue, MissingSecret, ISSUER, AUDIENCE, ALGORITHM
    except ImportError as e:
        print(f"needs mcp and pyjwt: pip install 'mcp>=2' pyjwt\n({e})", file=sys.stderr)
        return 1

    if a.issue:
        try:
            tok = issue(a.issue, days=a.days, scopes=a.scopes.split())
        except MissingSecret as e:
            print(e, file=sys.stderr)
            return 1
        print(tok)
        print(f"\n  subject {a.issue} · {a.days} days · scopes: {a.scopes}",
              file=sys.stderr)
        print("  Client sends it as:  Authorization: Bearer <token>", file=sys.stderr)
        return 0

    # --inspect
    try:
        import jwt
        from mcp_server.auth import secret
        claims = jwt.decode(a.inspect, secret(), algorithms=[ALGORITHM],
                            audience=AUDIENCE, issuer=ISSUER)
        left = int(claims["exp"]) - int(time.time())
        print(json.dumps(claims, indent=2))
        print(f"\n  valid · expires in {left // 86400}d {left % 86400 // 3600}h",
              file=sys.stderr)
        return 0
    except Exception as e:
        print(f"INVALID: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
