#!/usr/bin/env python3
"""
MCP server — transcription as a tool an agent can call.

Exposes local, offline speech-to-text over the Model Context Protocol so Claude
(or any MCP client) can transcribe a file or a YouTube URL without the audio
leaving the machine.

The privacy property is the point: an agent that can transcribe through this
server never uploads the audio anywhere, and the one network call in the whole
surface — fetching a YouTube video — is explicit in the tool name rather than
hidden inside something that sounds local.

Run:
    python mcp/server.py

Register with Claude Code (~/.claude.json or project .mcp.json):
    {
      "mcpServers": {
        "transcribe": {
          "command": "python",
          "args": ["/abs/path/to/mcp/server.py"]
        }
      }
    }
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:
    sys.exit("pip install mcp")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MODELS = ROOT / "models" / "asr" / "indic"
DIARIZE = ROOT / "models" / "diarize"

server = Server("indic-transcribe")

# Built on first use and kept. Loading the two graphs takes ~1.9s; rebuilding
# per call would dominate the runtime of short utterances.
_transcriber = None
_diarizer = None
_language = None


def _lang() -> str:
    """The language chosen at install time. Declared, never guessed."""
    global _language
    if _language is None:
        f = MODELS / "language.json"
        _language = (json.loads(f.read_text()).get("language")
                     if f.exists() else None) or "hi"
    return _language


def _load():
    """
    AI4Bharat's official ONNX export, run on onnxruntime directly.

    sherpa-onnx is not used for recognition: its from_nemo_ctc wants one file
    with vocab_size in the graph metadata, while this export ships the
    vocabulary as vocab.json beside the graphs. Reading the pieces is simpler
    than repackaging the model to suit a wrapper, and it means all 22 languages
    work as published with no conversion step.
    """
    global _transcriber
    if _transcriber is None:
        from asr import Transcriber
        _transcriber = Transcriber(
            MODELS, language=_lang(),
            # 4 threads is the knee of the curve: 8 buys only ~20% more.
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
    Returns (path, is_temp). Every ASR model wants 16 kHz mono; anything else
    produces silence or noise rather than an error, so convert rather than
    trusting the input.
    """
    if src.suffix.lower() == ".wav":
        with wave.open(str(src)) as wf:
            if wf.getframerate() == 16000 and wf.getnchannels() == 1:
                return src, False

    if not shutil.which("ffmpeg"):
        raise RuntimeError(f"{src.name} is not 16kHz mono and ffmpeg is not installed")

    tmp = Path(tempfile.mkdtemp()) / "audio.16k.wav"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(tmp)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        tail = "\n".join(r.stderr.strip().split("\n")[-4:])
        raise RuntimeError(f"ffmpeg failed on {src.name}:\n{tail}")
    return tmp, True


def _transcribe(path: Path) -> dict:
    import time
    from asr import read_wav16k

    wav, is_temp = _to_wav16k(path)
    try:
        samples = read_wav16k(wav)
        tr = _load()
        t0 = time.time()
        res = tr.transcribe(samples)
        elapsed = max(time.time() - t0, 1e-6)

        res.pop("tokens", None)
        res.pop("timestamps", None)
        res.update({"decode_sec": round(elapsed, 2),
                    "realtime_factor": round(res["duration_sec"] / elapsed, 1),
                    "source": path.name})
        return res
    finally:
        if is_temp:
            shutil.rmtree(wav.parent, ignore_errors=True)


DIARIZE = ROOT / "models" / "diarize"


def _transcribe_diarized(path: Path, num_speakers: int = -1) -> dict:
    """
    Transcribe, then label who spoke — marking overlap rather than guessing.

    Diarization is independent of the recogniser: the segmentation and embedding
    models read the raw waveform and return speaker turns, never seeing the
    transcript. Only the alignment step touches both.

    Turns may overlap, because pyannote-3.0 predicts concurrent speech as a
    native output class. Where two people talk at once the words are MARKED
    uncertain rather than attributed — the recogniser sees one mixed waveform
    and cannot separate them, and putting a sentence in the wrong person's
    mouth is the most damaging error this tool can make.
    """
    import time
    from asr import read_wav16k
    from diarize import label

    wav, is_temp = _to_wav16k(path)
    try:
        samples = read_wav16k(wav)

        tr = _load()
        t0 = time.time()
        res = tr.transcribe(samples)
        asr_sec = time.time() - t0

        dz = _load_diarizer()
        t0 = time.time()
        turns = dz.turns(samples, num_speakers=num_speakers)
        diar_sec = time.time() - t0

        out = label(res, turns)
        out.update({"asr_sec": round(asr_sec, 2),
                    "diarization_sec": round(diar_sec, 2),
                    "source": path.name})
        return out
    finally:
        if is_temp:
            shutil.rmtree(wav.parent, ignore_errors=True)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="transcribe_file",
            description=(
                "Transcribe a local audio or video file to text. Runs entirely on this "
                "machine — the audio is never uploaded. Any format ffmpeg can read. "
                "Returns the text plus how fast it decoded."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "absolute path to the file"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="transcribe_youtube",
            description=(
                "Download a YouTube video's audio and transcribe it locally. This is the "
                "ONLY tool here that touches the network, and only to fetch the video — "
                "the audio is transcribed on this machine and never uploaded. "
                "Requires yt-dlp."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube URL"},
                    "keep_audio": {
                        "type": "boolean",
                        "description": "keep the downloaded .m4a (default false)",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="transcribe_with_speakers",
            description=(
                "Transcribe AND label who spoke — for interviews, meetings and calls. "
                "Runs locally like the others. Costs roughly 6x the time of plain "
                "transcription, so use transcribe_file when the speaker does not matter. "
                "Pass num_speakers when you know it: letting the clusterer guess is the "
                "main cause of one person being split into several."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "absolute path to the file"},
                    "num_speakers": {
                        "type": "integer",
                        "description": "how many people are speaking. Omit to auto-detect.",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="transcription_info",
            description=(
                "What this install can do: which language is configured, whether the model "
                "is present, and the measured speed. Call this first if a transcription fails."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "transcription_info":
            model = MODELS / "model.int8.onnx"
            lang_file = MODELS / "language.json"
            info = {
                "model_present": model.exists(),
                "model_path": str(model),
                "model_mb": round(model.stat().st_size / 1e6) if model.exists() else None,
                "language": (json.loads(lang_file.read_text()).get("language")
                             if lang_file.exists() else None),
                "threads": int(os.environ.get("TRANSCRIBE_THREADS", "4")),
                "ffmpeg": bool(shutil.which("ffmpeg")),
                "yt_dlp": bool(shutil.which("yt-dlp")),
                "note": ("Offline. Nothing is uploaded. transcribe_youtube is the only "
                         "tool that reaches the network, and only to fetch the video."),
            }
            if not info["model_present"]:
                info["fix"] = "python scripts/fetch_models.py --indic hi"
            return [TextContent(type="text", text=json.dumps(info, indent=2))]

        if name == "transcribe_file":
            path = Path(arguments["path"]).expanduser()
            if not path.exists():
                return [TextContent(type="text", text=f"no such file: {path}")]
            result = await asyncio.to_thread(_transcribe, path)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        if name == "transcribe_with_speakers":
            path = Path(arguments["path"]).expanduser()
            if not path.exists():
                return [TextContent(type="text", text=f"no such file: {path}")]
            result = await asyncio.to_thread(
                _transcribe_diarized, path, arguments.get("num_speakers", -1))
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        if name == "transcribe_youtube":
            if not shutil.which("yt-dlp"):
                return [TextContent(type="text", text="yt-dlp is not installed: pip install yt-dlp")]

            workdir = Path(tempfile.mkdtemp())
            try:
                r = await asyncio.to_thread(
                    subprocess.run,
                    ["yt-dlp", "-q", "--no-warnings", "-f", "bestaudio",
                     "-x", "--audio-format", "m4a",
                     "-o", str(workdir / "audio.%(ext)s"), arguments["url"]],
                    capture_output=True, text=True,
                )
                if r.returncode != 0:
                    tail = "\n".join((r.stderr or "").strip().split("\n")[-4:])
                    return [TextContent(type="text", text=f"yt-dlp failed:\n{tail}")]

                audio = next(workdir.glob("audio.*"), None)
                if audio is None:
                    return [TextContent(type="text", text="yt-dlp produced no audio file")]

                result = await asyncio.to_thread(_transcribe, audio)
                result["url"] = arguments["url"]

                if arguments.get("keep_audio"):
                    kept = Path.cwd() / audio.name
                    shutil.copy2(audio, kept)
                    result["audio_kept_at"] = str(kept)

                return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
            finally:
                shutil.rmtree(workdir, ignore_errors=True)

        return [TextContent(type="text", text=f"unknown tool: {name}")]

    except Exception as e:
        # Return the error as content rather than raising: an agent can read a
        # message and correct course, but a protocol-level exception just ends
        # the call with nothing useful.
        return [TextContent(type="text", text=f"{type(e).__name__}: {e}")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
