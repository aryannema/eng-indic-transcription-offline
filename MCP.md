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

**SSE is deprecated, and that is the specification's position, not a preference.**
MCP replaced HTTP+SSE with Streamable HTTP in revision **2025-03-26**. SSE
remains here only for clients that have not migrated. Do not build against it.
If you want network access, use `streamable-http`.

## Authentication

**stdio: none, deliberately.** The client spawned the process.

**HTTP transports: a JWT bearer token, and the server refuses to start without a
secret.** An open transcription endpoint on a network is not a reasonable
default, so this is a hard failure rather than a warning:

```
$ python mcp_server/server.py --transport streamable-http
MCP_JWT_SECRET is not set.
  Generate one:  python scripts/mcp_token.py --new-secret
```

### Issuing tokens

```bash
python scripts/mcp_token.py --new-secret        # 64 chars
export MCP_JWT_SECRET='...'

python scripts/mcp_token.py --issue aryan --days 7
python scripts/mcp_token.py --inspect <token>
```

The client sends `Authorization: Bearer <token>`.

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
