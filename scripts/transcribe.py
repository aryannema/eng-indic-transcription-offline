#!/usr/bin/env python3
"""
transcribe.py — speech to text on a CPU, no GPU, no network.

Uses AI4Bharat's Indic Conformer quantised to int8 (197 MB) through the
sherpa-onnx runtime. Measured on an ordinary CPU: 45 seconds of audio decoded
in 3.2 seconds on ONE thread — fourteen times faster than the audio plays.

Usage:
    transcribe.py recording.wav
    transcribe.py recording.wav --threads 1
    transcribe.py *.wav --format srt
    transcribe.py meeting.mp3            # converted automatically if ffmpeg exists

Output formats: txt (default), srt, vtt, json, md
"""

import argparse
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

MODELS = Path(__file__).resolve().parent.parent / "models" / "asr" / "indic"


# ── time formatting ──────────────────────────────────────────────────────────
# SRT puts a comma before the milliseconds, WebVTT a dot. Swap them and you get
# a file that looks right and that no player will load.

def ts_srt(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02},{int((t % 1) * 1000):03}"


def ts_vtt(t: float) -> str:
    return ts_srt(t).replace(",", ".")


def ts_short(t: float) -> str:
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}" if h else f"{m:02}:{s:02}"


# ── audio ────────────────────────────────────────────────────────────────────

def load_audio(path: str, keep_temp: bool = False):
    """
    Every ASR model on earth wants the same thing: 16 kHz, mono, float32 in
    [-1.0, 1.0]. Not mp3, not stereo, not 44.1 kHz, and NOT int16 — feeding
    int16 straight in produces silence or noise rather than an error, which is
    the most common reason a model "does not work".
    """
    import numpy as np

    src = Path(path)
    tmp = None

    needs_convert = src.suffix.lower() != ".wav"
    if not needs_convert:
        with wave.open(str(src)) as wf:
            needs_convert = wf.getframerate() != 16000 or wf.getnchannels() != 1

    if needs_convert:
        tmp = src.with_suffix(".16k.wav")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(tmp)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            tail = "\n".join(r.stderr.strip().split("\n")[-5:])
            raise SystemExit(f"ffmpeg could not convert {src}:\n{tail}")
        src = tmp

    with wave.open(str(src)) as wf:
        frames = wf.readframes(wf.getnframes())
        rate = wf.getframerate()

    # int16 spans ±32768; models want ±1.0. That division IS the conversion.
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    if tmp and not keep_temp:
        tmp.unlink(missing_ok=True)

    return samples, rate


# ── writers ──────────────────────────────────────────────────────────────────

def write_txt(path, segs, **_):
    Path(path).write_text("\n".join(s["text"] for s in segs) + "\n", encoding="utf-8")


def write_srt(path, segs, **_):
    out = []
    for s in segs:
        out.append(f"{s['id']}\n{ts_srt(s['start'])} --> {ts_srt(s['end'])}\n{s['text']}\n")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def write_vtt(path, segs, **_):
    out = ["WEBVTT", ""]
    for s in segs:
        out.append(f"{s['id']}\n{ts_vtt(s['start'])} --> {ts_vtt(s['end'])}\n{s['text']}\n")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def write_json(path, segs, *, meta, **_):
    Path(path).write_text(
        json.dumps({**meta, "segments": segs}, ensure_ascii=False, indent=1),
        encoding="utf-8")


def write_md(path, segs, *, meta, **_):
    """
    Subtitle blocks are unreadable as a document, so group into paragraphs of
    roughly two minutes each.
    """
    lines = [f"# {meta.get('source', 'Transcript')}", ""]
    bits = [f"{meta['duration'] / 60:.1f} min" if meta.get("duration") else None,
            meta.get("language"), f"{len(segs)} segments"]
    lines += [" · ".join(b for b in bits if b), "",
              "Machine transcript — unedited. Check any wording against the audio "
              "before quoting it.", "", "---", ""]

    para, start = [], None
    for s in segs:
        if start is None:
            start = s["start"]
        if para and s["start"] - start >= 120:
            lines += [f"**[{ts_short(start)}]** {' '.join(para)}", ""]
            para, start = [], s["start"]
        para.append(s["text"])
    if para:
        lines.append(f"**[{ts_short(start)}]** {' '.join(para)}")

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


WRITERS = {"txt": write_txt, "srt": write_srt, "vtt": write_vtt,
           "json": write_json, "md": write_md}


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="audio or video files")
    ap.add_argument("--threads", type=int, default=4,
                    help="CPU threads (default 4). Even 1 gives ~14x realtime.")
    ap.add_argument("--format", default="txt",
                    help="comma-separated: txt,srt,vtt,json,md")
    ap.add_argument("--models", default=str(MODELS))
    ap.add_argument("--keep-wav", action="store_true",
                    help="keep the converted 16 kHz file")
    args = ap.parse_args()

    formats = [f.strip() for f in args.format.split(",") if f.strip()]
    unknown = [f for f in formats if f not in WRITERS]
    if unknown:
        print(f"unknown format(s): {', '.join(unknown)}. "
              f"Known: {', '.join(WRITERS)}", file=sys.stderr)
        return 2

    model_dir = Path(args.models)
    model = model_dir / "model.int8.onnx"
    tokens = model_dir / "tokens.txt"
    if not model.exists():
        print(f"no model at {model}\n"
              f"  run:  python scripts/fetch_models.py --indic hi", file=sys.stderr)
        return 2

    try:
        import sherpa_onnx
    except ImportError:
        print("sherpa-onnx is not installed.\n"
              "  uv pip install sherpa-onnx numpy", file=sys.stderr)
        return 2

    # The language chosen at setup is recorded beside the weights rather than
    # guessed per file — Hindi and Urdu are near-identical acoustically, and a
    # model made to choose writes the wrong SCRIPT silently rather than erroring.
    lang_file = model_dir / "language.json"
    language = None
    if lang_file.exists():
        language = json.loads(lang_file.read_text()).get("language")

    t0 = time.time()
    recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
        model=str(model), tokens=str(tokens), num_threads=args.threads)
    print(f"  model loaded in {time.time() - t0:.1f}s  "
          f"({args.threads} thread{'s' if args.threads != 1 else ''}"
          f"{', ' + language if language else ''})")

    failed = 0
    for path in args.inputs:
        if not os.path.exists(path):
            print(f"  {path}: no such file")
            failed += 1
            continue

        try:
            samples, rate = load_audio(path, args.keep_wav)
        except SystemExit as e:
            print(f"  {e}")
            failed += 1
            continue

        duration = len(samples) / rate

        t0 = time.time()
        stream = recognizer.create_stream()
        stream.accept_waveform(rate, samples)
        recognizer.decode_stream(stream)
        elapsed = max(time.time() - t0, 1e-6)

        result = stream.result
        text = result.text.strip()

        # This model is CTC, which has no notion of sentences. Timestamps exist
        # per token; one segment spanning the clip is the honest representation
        # rather than inventing sentence boundaries that were never detected.
        segs = [{"id": 1, "start": 0.0, "end": round(duration, 2), "text": text}]

        meta = {
            "source": os.path.basename(path),
            "duration": round(duration, 2),
            "language": language,
            "model": "ai4bharat-indic-conformer-int8",
            "threads": args.threads,
        }

        base = os.path.splitext(path)[0]
        for fmt in formats:
            WRITERS[fmt](f"{base}.{fmt}", segs, meta=meta)

        print(f"  {os.path.basename(path)}: {duration:.0f}s decoded in "
              f"{elapsed:.2f}s ({duration / elapsed:.0f}x realtime) "
              f"-> {', '.join(f'.{f}' for f in formats)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
