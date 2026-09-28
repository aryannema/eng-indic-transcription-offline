#!/usr/bin/env python3
"""
Transcription as agent tools, over MCP.

Transports
----------
Three are available; the default is stdio and the reason is not inertia.

  stdio            The client spawns this process and talks over stdin/stdout.
                   No port, no listener, no authentication to get wrong, and
                   nothing reachable from the network. For a tool whose entire
                   premise is that audio never leaves the machine, opening an
                   HTTP listener would contradict the product.

  streamable-http  One server, many clients, reachable over a network. This is
                   what you want for a hosted service -- a GPU box transcribing
                   for several people.

  sse              DEPRECATED. The MCP specification replaced HTTP+SSE with
                   Streamable HTTP in revision 2025-03-26. It is here only for
                   clients that have not migrated. Do not build against it.

    python mcp/server.py                                  # stdio (default)
    python mcp/server.py --transport streamable-http --port 8080
    python mcp/server.py --transport sse --port 8080       # legacy clients only

Tool design
-----------
An agent picks tools by reading their descriptions, so each one says what it is
for AND when not to use it. `transcribe_with_speakers` costs several times what
plain transcription costs, so its description says so; otherwise an agent reaches
for the richest tool every time.

Errors are returned as text, not raised. A message an agent can read ("that file
is 8 kHz, convert it") lets it recover; a protocol exception just ends the call.

Requires mcp >= 2.0 (FastMCP was renamed MCPServer in 2.x).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

try:
    from mcp.server.mcpserver import MCPServer
except ImportError as e:
    sys.exit("needs mcp >= 2.0:  pip install 'mcp>=2'\n"
             f"({e})")

ROOT = Path(__file__).resolve().parent.parent
# Our package is mcp_server, not mcp: a local directory named "mcp" shadows the
# SDK of the same name, and "from mcp.auth import ..." then resolves to
# site-packages instead of this repo. Confusing enough to be worth avoiding.
sys.path.insert(0, str(ROOT))
MODELS = ROOT / "models" / "asr" / "indic"
DIARIZE = ROOT / "models" / "diarize"

server = MCPServer(
    name="indic-transcribe",
    version="1.0.0",
    instructions=(
        "Offline speech-to-text for 22 Indian languages. Everything runs on this "
        "machine: no audio is uploaded and no network is used after the model is "
        "downloaded.\n\n"
        "Pick transcribe_file for a local recording, transcribe_youtube for a URL, "
        "and transcribe_with_speakers only when you actually need to know who "
        "spoke -- it costs several times more.\n\n"
        "Two limits worth knowing before you report results. English words inside "
        "Indic audio come out transliterated into the Indic script, because the "
        "vocabulary has no Latin characters -- that is expected, not an error. And "
        "where two people talk at once the words are marked 'crosstalk - "
        "attribution uncertain' rather than attributed; do not resolve that "
        "ambiguity by guessing."
    ),
)

# Built once and kept: loading the graphs takes ~1.9 s, which would otherwise
# dominate every short request.
_transcriber = None
_diarizer = None
_language: str | None = None


def _lang() -> str:
    """The language chosen at install time. Declared, never guessed."""
    global _language
    if _language is None:
        f = MODELS / "language.json"
        _language = (json.loads(f.read_text()).get("language")
                     if f.exists() else None) or "hi"
    return _language


def _load():
    global _transcriber
    if _transcriber is None:
        from asr import Transcriber
        _transcriber = Transcriber(
            MODELS, language=_lang(),
            threads=int(os.environ.get("TRANSCRIBE_THREADS", "4")))
    return _transcriber


def _load_diarizer():
    global _diarizer
    if _diarizer is None:
        from diarize import Diarizer
        _diarizer = Diarizer(
            DIARIZE, threads=int(os.environ.get("TRANSCRIBE_THREADS", "4")))
    return _diarizer


def _to_wav16k(src: Path) -> tuple[Path, bool]:
    """
    Returns (path, is_temp). Wrong sample rate does not raise inside the model,
    it produces plausible nonsense, so convert rather than trust the input.
    """
    if src.suffix.lower() == ".wav":
        with wave.open(str(src)) as wf:
            if wf.getframerate() == 16000 and wf.getnchannels() == 1:
                return src, False
    if not shutil.which("ffmpeg"):
        raise RuntimeError(f"{src.name} is not 16 kHz mono and ffmpeg is not installed")
    tmp = Path(tempfile.mkdtemp()) / "audio.16k.wav"
    r = subprocess.run(["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1",
                        "-ar", "16000", str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().split("\n")[-4:])
        raise RuntimeError(f"ffmpeg failed on {src.name}:\n{tail}")
    return tmp, True


def _transcribe(path: Path) -> dict:
    from asr import read_wav16k
    wav, is_temp = _to_wav16k(path)
    try:
        samples = read_wav16k(wav)
        tr = _load()
        t0 = time.time()
        res = tr.transcribe(samples)
        el = max(time.time() - t0, 1e-6)
        res.pop("tokens", None)
        res.pop("timestamps", None)
        res.update({"decode_sec": round(el, 2),
                    "realtime_factor": round(res["duration_sec"] / el, 1),
                    "source": path.name})
        return res
    finally:
        if is_temp:
            shutil.rmtree(wav.parent, ignore_errors=True)


def _transcribe_diarized(path: Path, num_speakers: int = -1) -> dict:
    from asr import read_wav16k
    from diarize import label
    wav, is_temp = _to_wav16k(path)
    try:
        samples = read_wav16k(wav)
        tr, dz = _load(), _load_diarizer()
        t0 = time.time(); res = tr.transcribe(samples); asr_s = time.time() - t0
        t0 = time.time(); turns = dz.turns(samples, num_speakers=num_speakers)
        diar_s = time.time() - t0
        out = label(res, turns)
        out.update({"asr_sec": round(asr_s, 2),
                    "diarization_sec": round(diar_s, 2),
                    "source": path.name})
        return out
    finally:
        if is_temp:
            shutil.rmtree(wav.parent, ignore_errors=True)


def _fail(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------ the tools

@server.tool()
async def transcribe_file(path: str) -> str:
    """
    Transcribe an audio or video file on this machine. Returns JSON with the
    text, duration and how fast it ran.

    Any format ffmpeg can read. Files of any length: audio over 45 seconds is
    split automatically, because a single long pass through this model silently
    returns a truncated transcript rather than failing.

    Use this unless you specifically need speaker labels.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return f"no such file: {p}"
    try:
        r = await asyncio.to_thread(_transcribe, p)
        return json.dumps(r, ensure_ascii=False, indent=2)
    except Exception as e:
        return _fail(e)


@server.tool()
async def transcribe_with_speakers(path: str, num_speakers: int = -1) -> str:
    """
    Transcribe AND label who spoke. For interviews, meetings and calls.

    Costs roughly the same again in time as plain transcription, so prefer
    transcribe_file when speaker identity does not matter.

    Pass num_speakers whenever you know it. Letting the clusterer decide is the
    main failure mode: on a real 5-person debate, automatic detection returned
    27 speakers, because a segment where two people talk at once does not
    resemble either of them and becomes its own phantom speaker.

    Regions where people talk over each other are marked "crosstalk -
    attribution uncertain". That is a real limit, not missing polish: one mixed
    waveform cannot be split into two transcripts without separating the voices
    first. Report the marking; do not guess who said what.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return f"no such file: {p}"
    try:
        r = await asyncio.to_thread(_transcribe_diarized, p, num_speakers)
        return json.dumps(r, ensure_ascii=False, indent=2)
    except Exception as e:
        return _fail(e)


@server.tool()
async def transcribe_youtube(url: str) -> str:
    """
    Download the audio from a video URL and transcribe it.

    Needs yt-dlp (a Python package: pip install yt-dlp). The audio is fetched to
    a temporary directory and deleted afterwards; only the transcript is kept.

    This is the one tool here that uses the network, and only to fetch the
    media -- transcription itself stays local.
    """
    if not shutil.which("yt-dlp"):
        return "yt-dlp not installed: pip install yt-dlp"
    work = Path(tempfile.mkdtemp())
    try:
        r = subprocess.run(
            ["yt-dlp", "--no-playlist", "-f", "bestaudio", "-x",
             "--audio-format", "wav", "--postprocessor-args", "-ac 1 -ar 16000",
             "-o", str(work / "audio.%(ext)s"), url],
            capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            return "yt-dlp failed:\n" + "\n".join(r.stderr.strip().split("\n")[-5:])
        wavs = list(work.glob("*.wav"))
        if not wavs:
            return "yt-dlp produced no audio file"
        out = await asyncio.to_thread(_transcribe, wavs[0])
        out["source"] = url
        return json.dumps(out, ensure_ascii=False, indent=2)
    except Exception as e:
        return _fail(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


@server.tool()
async def transcription_info() -> str:
    """
    What is installed and what it can do: the language, whether speaker labels
    are available, model precision, and thread count.

    Call this first if a transcription attempt failed — it distinguishes "the
    model is not downloaded" from "that file is the wrong format".
    """
    info: dict = {
        "language": _lang(),
        "model_dir": str(MODELS),
        "model_present": (MODELS / "encoder.onnx").exists()
                         or (MODELS / "encoder.int8.onnx").exists(),
        "precision": "int8" if (MODELS / "encoder.int8.onnx").exists() else "fp32",
        "speaker_labels_available": (DIARIZE / "segmentation.onnx").exists(),
        "threads": int(os.environ.get("TRANSCRIBE_THREADS", "4")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "runs_offline": True,
        "notes": [
            "English inside Indic audio is transliterated — the vocabulary has no Latin.",
            "Not streaming: faster than real time, but not live captioning.",
            "Overlapping speech is marked, not separated into per-speaker transcripts.",
        ],
    }
    if not info["model_present"]:
        info["fix"] = ("python scripts/fetch_models.py --indic hi "
                       "(the model is gated: see README)")
    return json.dumps(info, ensure_ascii=False, indent=2)


# The same tools, reused by the authenticated instance rather than redefined --
# two definitions would drift and one of them would quietly lack a fix.
_TOOLS = [transcribe_file, transcribe_with_speakers, transcribe_youtube,
          transcription_info]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transport", default="stdio",
                    choices=["stdio", "streamable-http", "sse"],
                    help="stdio (default, local); streamable-http (hosted); "
                         "sse (DEPRECATED, legacy clients only)")
    ap.add_argument("--host", default="127.0.0.1",
                    help="HTTP transports only. Defaults to loopback on purpose — "
                         "binding 0.0.0.0 exposes transcription to your network.")
    ap.add_argument("--port", type=int, default=8080, help="HTTP transports only")
    a = ap.parse_args()

    if a.transport == "sse":
        print("warning: SSE is deprecated in the MCP spec (superseded by "
              "Streamable HTTP in revision 2025-03-26). Use "
              "--transport streamable-http unless a client requires SSE.",
              file=sys.stderr)

    if a.transport == "stdio":
        # No authentication, deliberately: the client started this process and
        # there is no socket for anyone else to reach.
        server.run(transport="stdio")
        return

    # HTTP transports authenticate, and refuse to start if they cannot. An open
    # transcription endpoint on a network is not a reasonable default.
    try:
        from mcp_server.auth import JWTVerifier
        from mcp.server.auth.settings import AuthSettings
    except ImportError as e:
        sys.exit(f"HTTP transports need: pip install 'mcp>=2' pyjwt\n({e})")

    try:
        verifier = JWTVerifier(required_scopes=["transcribe"])
    except Exception as e:
        sys.exit(str(e))

    # Refresh lives on a custom route rather than as an MCP tool, on purpose:
    # a tool call needs a valid access token to reach it, so an expired client
    # could never refresh. It has to sit outside the authenticated surface.
    from mcp_server.auth import refresh as do_refresh

    async def refresh_route(request):
        from starlette.responses import JSONResponse
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "body is not valid JSON"}, status_code=400)
        tok = (body or {}).get("refresh_token")
        if not isinstance(tok, str) or not tok:
            return JSONResponse(
                {"error": 'send {"refresh_token": "<token>"}'}, status_code=400)
        issued = do_refresh(tok)
        if not issued:
            # Expired, wrong signature, and "that is an access token" are one
            # answer here and three different lines in the log.
            return JSONResponse(
                {"error": "refresh token not accepted; obtain a new pair"},
                status_code=401)
        # A token is not cacheable by anything, ever.
        return JSONResponse(issued, headers={"Cache-Control": "no-store"})

    base = f"http://{a.host}:{a.port}"
    authed = MCPServer(
        name=server.name, version=server.version, instructions=server.instructions,
        token_verifier=verifier,
        auth=AuthSettings(issuer_url=base, resource_server_url=base,
                          required_scopes=["transcribe"]),
    )
    for t in _TOOLS:
        authed.add_tool(t)

    try:
        authed.custom_route("/refresh", methods=["POST"])(refresh_route)
    except Exception as e:                                  # noqa: BLE001
        print(f"note: refresh route unavailable ({e}); use scripts/mcp_token.py "
              f"--refresh instead", file=sys.stderr)

    if a.host == "0.0.0.0":
        print("warning: binding 0.0.0.0 exposes transcription to every host that "
              "can reach this machine. A valid token is then the only thing "
              "between them and your audio.", file=sys.stderr)
    print(f"serving MCP over {a.transport} on {base} (bearer token required)",
          file=sys.stderr)
    print(f"  refresh: POST {base}/refresh  {{'refresh_token': '...'}}",
          file=sys.stderr)
    authed.run(transport=a.transport, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
