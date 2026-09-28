# MCP — transcription as agent tools

This exposes the transcriber over the **Model Context Protocol**, so an agent
(Claude Desktop, Claude Code, or anything else speaking MCP) can transcribe
audio as a tool call instead of you running a command.

Verified against **MCP SDK 2.2.0**, protocol revision **2025-11-25**.

## Transports, and why the default is stdio

Three are available. The choice is not cosmetic.

| transport | how it runs | use it for |
|---|---|---|
| **stdio** (default) | the client spawns this process; JSON-RPC over stdin/stdout | your own laptop |
| **streamable-http** | a long-running server on a port | one machine serving several people |
| **sse** | HTTP + Server-Sent Events | **deprecated** — legacy clients only |

```bash
python mcp_server/server.py                                    # stdio
python mcp_server/server.py --transport streamable-http --port 8080
```

**stdio is the default because this tool's entire premise is that audio never
leaves the machine.** There is no port, no listener, and nothing to
authenticate — the client already started the process, so it already has that
access. Opening an HTTP listener by default would contradict the product.

#### SSE is not dead — the two-endpoint transport is

A distinction worth getting right, because "SSE is deprecated" is a misleading
shorthand:

| | status |
|---|---|
| **SSE the technology** (`text/event-stream`) | **alive** — Streamable HTTP uses it internally |
| **HTTP+SSE the transport** (two endpoints) | **deprecated**, replaced in revision 2025-03-26 |

**The old transport used two endpoints.** The client opened `GET /sse` and held
it open indefinitely; the server replied down that long-lived stream while the
client posted requests to a *separate* `POST /messages/`. Two connections that
had to stay correlated — so if the stream dropped the session died, and it could
not survive a load balancer routing the two endpoints to different servers.

**Streamable HTTP uses one endpoint.** `POST /mcp` carries the request, and the
server answers with either `application/json` or `text/event-stream` depending
on whether it needs to stream. Same URL, same request. SSE is still there; it is
a *response mode* now rather than a connection you maintain.

You can see it in the SDK: `mcp/server/streamable_http.py` defines
`CONTENT_TYPE_SSE = "text/event-stream"`, while the deprecated transport lives
separately in `mcp/server/sse.py` with its `Route("/sse")` plus
`Mount("/messages/")` pair.

So: use `streamable-http`. The `sse` option here exists only for clients that
have not migrated, and prints a deprecation warning.

## Authentication

The MCP specification's model is **OAuth 2.1 bearer tokens**. How you obtain the
token is left open, so several approaches are valid:

| | what it is | here? |
|---|---|---|
| **none** | stdio only — the client already spawned the process | ✅ stdio |
| **static shared secret** | one key, one identity, never expires | — |
| **self-issued JWT** | per-subject, expiring, scoped, no external provider | ✅ **HTTP** |
| **full OAuth 2.1** | authorization server, discovery, dynamic client registration | SDK supports it; not used here |
| **mTLS or proxy auth** | handled at the reverse proxy, outside MCP entirely | valid, not implemented |

This project uses **self-issued JWTs**: real expiry and per-client identity
without depending on an external provider — which suits a tool whose whole point
is running offline.

**stdio: none, deliberately.** The client spawned the process.

**HTTP transports: a JWT bearer token, and the server refuses to start without a
secret.** An open transcription endpoint on a network is not a reasonable
default, so this is a hard failure rather than a warning:

```
$ python mcp_server/server.py --transport streamable-http
MCP_JWT_SECRET is not set.
  Generate one:  python scripts/mcp_token.py --new-secret
```

### Who generates the key — nobody central

There is no signing authority, no registration and no key server. **The person
running the server generates the secret on their own machine**, and the same
process signs and verifies.

```bash
python scripts/mcp_token.py --new-secret     # 64 random chars, generated locally
export MCP_JWT_SECRET='...'
```

HS256 is **symmetric**: one secret both signs and checks. The server handing out
a token is the server validating it, which is why there is no registration step
— it is talking to itself.

| | who sets it | what it is for |
|---|---|---|
| `MCP_JWT_SECRET` | you, via `--new-secret` | signs and verifies |
| `MCP_JWT_ISSUER` | defaults to `indic-transcribe` | which system minted this |
| `MCP_JWT_AUDIENCE` | defaults to `indic-transcribe-mcp` | which system may accept it |

`iss` and `aud` earn their keep when you run **several** services from one
secret: if two services shared a key and neither checked `aud`, a token for one
would open the other. Give each service its own `MCP_JWT_AUDIENCE` and it
cannot. Running a single server? The defaults are correct and you never touch
them.

**Every clone of this repository gets its own isolated authentication.** Your
secret is yours; a token minted against it works on your server and nowhere
else. There is no shared secret in the repository, no default, and nothing to
leak when it is published — which is also why the server **refuses to start**
without one rather than falling back. A shipped default would mean every
deployment on earth shared one key: the appearance of security with none of it.

When you would outgrow this: HS256 shares the secret between whoever mints
tokens and whoever checks them. If tokens must be minted somewhere you would not
trust with a signing key, switch to **RS256** — the minter keeps the private
key, this server needs only the public half. Only the verifier changes.

### Issuing tokens

```bash
python scripts/mcp_token.py --new-secret        # 64 chars
export MCP_JWT_SECRET='...'

python scripts/mcp_token.py --issue aryan       # a PAIR
python scripts/mcp_token.py --inspect <token>
```

`--issue` returns two tokens:

```json
{
  "access_token":  "…",
  "refresh_token": "…",
  "token_type": "Bearer",
  "expires_in": 900
}
```

The client sends `Authorization: Bearer <access_token>`.

### Access and refresh

| | lifetime | what it can do |
|---|---|---|
| **access** | 15 min | call tools |
| **refresh** | 30 days | obtain a new access token — **nothing else** |

A long-lived access token that leaks is usable until it expires, and you cannot
tell it leaked. A 15-minute one caps that window, and the refresh token is sent
only when refreshing rather than on every call, so it spends far less time in
transit and in logs.

```bash
# over HTTP
curl -X POST http://127.0.0.1:8080/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"…"}'

# or locally
python scripts/mcp_token.py --refresh <refresh-token>
```

Refresh sits on its own route rather than being an MCP tool, because a tool call
needs a valid access token to reach it — an expired client could never refresh.

Lifetimes are `MCP_JWT_ACCESS_MINUTES` and `MCP_JWT_REFRESH_DAYS`.

### The type check that makes this worth doing

Decode both tokens from one `--issue` and compare them:

```
claim    | ACCESS               | REFRESH              | same?
---------|----------------------|----------------------|--------
iss      | indic-transcribe     | indic-transcribe     | YES
aud      | indic-transcribe-mcp | indic-transcribe-mcp | YES
sub      | aryan                | aryan                | YES
scopes   | ['transcribe']       | ['transcribe']       | YES
typ      | access               | refresh              | ** NO **
exp      | +15 min              | +30 days             | ** NO **
```

Same key, same algorithm, same everything — **except `typ` and expiry**. Delete
the `typ` check and the two become literally interchangeable: a 30-day refresh
token would pass every other test a valid access token passes.

So it is checked in both directions:

```
refresh token presented as an access token  ->  rejected
access token presented as a refresh token   ->  rejected
```

Without the first, a 30-day refresh token would call tools and the short access
lifetime would be decoration. Without the second, a leaked access token could
mint replacements forever. Tested both ways.

### What is deliberately NOT implemented: rotation

Rotation — issuing a new refresh token on every exchange and invalidating the
old one — is stronger, because it **detects theft**: if a thief and the
legitimate client both use the same refresh token, one of them presents a
superseded one and you know.

But detecting that needs **server-side state**, a record of which tokens have
been used. This server is deliberately stateless. A rotation with nothing to
compare against would look like protection while providing none, so it is not
here. If you need rotation, you need a token store first.

### What is implemented, and what is not

Implemented: HS256 signatures, `exp`/`iat`/`sub` **required** (a token with no
expiry is rejected rather than treated as eternal), issuer and audience checked,
and a `transcribe` scope the server requires.

Not implemented: an authorisation server, dynamic client registration, refresh
flows, or a revocation list. **Expiry is the revocation mechanism**, which is why
`--days` defaults to 30 and shorter is better. If you outgrow this, `MCPServer`
also accepts an `auth_server_provider` and the verifier in `mcp_server/auth.py`
can be replaced without touching any tool.

Three deliberate choices worth knowing:

- **The secret is read from the environment only.** There is no default and no
  file in the repo. A shipped default secret looks like security while providing
  none.
- **HS256 needs ≥32 characters and this is enforced.** Use RS256 instead if
  tokens must be minted somewhere you would not trust with a signing key — the
  verifier then needs only the public half.
- **Rejection reasons go to the server log, not to the caller.** "Signature
  invalid" versus "expired" versus "wrong audience" is useful to an attacker and
  useless to a legitimate client, whose token either works or needs reissuing.

`--host` defaults to `127.0.0.1`. Passing `0.0.0.0` prints a warning, because a
valid token is then the only thing between the network and your audio.

## Wiring it into a client

### Claude Desktop / Claude Code — stdio

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "indic-transcribe": {
      "command": "/abs/path/to/.venv/bin/python",
      "args": ["/abs/path/to/mcp_server/server.py"],
      "env": { "TRANSCRIBE_THREADS": "8" }
    }
  }
}
```

Use the **absolute** path to the venv's Python. A bare `python` picks up
whatever the client's environment has, which is usually not the venv, and the
failure looks like a missing dependency.

### Streamable HTTP

```bash
export MCP_JWT_SECRET='...'
python mcp_server/server.py --transport streamable-http --host 127.0.0.1 --port 8080
```

Put it behind a reverse proxy with TLS if it leaves the machine. **A bearer token
over plain HTTP is a bearer token in cleartext.**

## The tools

| tool | required | returns |
|---|---|---|
| `transcribe_file` | `path` | text, duration, realtime factor |
| `transcribe_with_speakers` | `path`, *`num_speakers`* | lines with speakers and crosstalk marks |
| `transcribe_youtube` | `url` | transcript of a video's audio |
| `transcription_info` | — | what is installed and what it can do |

Schemas are generated from Python type hints by `@server.tool()`, so the
signature and the advertised schema cannot drift apart.

### Tool descriptions are part of the interface

An agent chooses tools by reading their descriptions, so each one says what it is
for **and when not to use it**:

- `transcribe_with_speakers` states that it costs roughly twice what plain
  transcription costs. Without that, an agent reaches for the richest tool every
  time.
- It also states that automatic speaker counting returned **27 speakers on a real
  5-person debate**, so an agent knows to pass `num_speakers` when it can.
- The server `instructions` warn that English inside Indic audio comes out
  transliterated — **expected, not an error** — so an agent does not report it as
  a bug.
- They warn that overlapping speech is marked `crosstalk - attribution
  uncertain`, and that the agent must **not** resolve that ambiguity by guessing.

### Errors are returned as text, not raised

```python
return f"{type(e).__name__}: {e}"
```

An agent can read *"that file is 8 kHz, convert it"* and correct course. A
protocol-level exception just ends the call with nothing to act on.

## Verifying it works

```bash
python -c "
import asyncio, sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
async def main():
    p = StdioServerParameters(command=sys.executable, args=['mcp_server/server.py'])
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            print((await s.initialize()).server_info)
            print([t.name for t in (await s.list_tools()).tools])
asyncio.run(main())"
```

Expected: `indic-transcribe 1.0.0` and the four tool names.

Note SDK 2.x uses **snake_case** on result objects — `protocol_version`,
`server_info`, `input_schema`. Code written against 1.x used camelCase and fails
with `AttributeError`.

## A naming trap

This package is **`mcp_server/`**, not `mcp/`. A local directory named `mcp`
shadows the installed SDK, so `from mcp.auth import ...` resolves to
site-packages rather than to your own file — and the error (`No module named
mcp.auth`) points at the dependency instead of at the collision.
