#!/usr/bin/env python3
"""
Tests that run without downloading 2.4 GB of weights.

They cover the logic that has actually broken during development: audio format
validation, the windowing that fixes silent truncation, and speaker alignment
around turn boundaries. Model accuracy is not tested here — that needs weights
and a reference transcript, and is measured by scripts/fleurs-wer.py.

    python -m tests.test_asr
"""
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}{('  — ' + detail) if detail and not cond else ''}")


def write_wav(path, samples, rate=16000, channels=1, width=2):
    with wave.open(str(path), "w") as w:
        w.setnchannels(channels); w.setsampwidth(width); w.setframerate(rate)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def tone(seconds, freq=220.0, rate=16000):
    t = np.arange(int(seconds * rate)) / rate
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


print("\n  Audio input\n")
from asr import read_wav16k

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    good = d / "good.wav"
    write_wav(good, tone(1.0))
    a = read_wav16k(good)
    check("16 kHz mono WAV reads", a.shape == (16000,), str(a.shape))
    check("scaled into [-1, 1]", float(np.abs(a).max()) <= 1.0)

    bad_rate = d / "8k.wav"
    write_wav(bad_rate, tone(1.0, rate=8000), rate=8000)
    try:
        read_wav16k(bad_rate); ok = False
    except ValueError as e:
        ok = "16000" in str(e)
    check("8 kHz is REFUSED, not resampled", ok,
          "silently resampling would degrade output with no warning")

    stereo = d / "stereo.wav"
    with wave.open(str(stereo), "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000)
        s = tone(1.0)
        w.writeframes(np.repeat((s * 32767).astype("<i2"), 2).tobytes())
    try:
        read_wav16k(stereo); ok = False
    except ValueError:
        ok = True
    check("stereo is refused", ok)

print("\n  Windowing — the silent-truncation fix\n")


class _Stub:
    """Exercises _windows without loading a model."""
    max_window_sec = 45.0
    _windows = None


from asr import Transcriber
_Stub._windows = Transcriber._windows

rate = 16000
# A pause placed INSIDE the search window. _windows targets 45 s and hunts +/-3 s,
# so a gap at 43-45 s is findable; one at 20 s is not, which is the real
# constraint: it finds the quietest point WITHIN 3 s, not the nearest real pause.
audio = np.concatenate([tone(43, 200), np.zeros(2 * rate, np.float32), tone(42, 300)])
wins = list(_Stub()._windows(audio))
total = sum(len(w) for _, w in wins)

check("long audio is split", len(wins) > 1, f"{len(wins)} window(s)")
check("no samples lost", total == len(audio), f"{total} vs {len(audio)}")
check("no window exceeds the ceiling",
      all(len(w) / rate <= 45.0 + 1e-6 for _, w in wins),
      f"max {max(len(w) for _, w in wins)/rate:.1f}s")
check("offsets are monotonic", all(b[0] >= a[0] for a, b in zip(wins, wins[1:])))
check("first offset is zero", wins[0][0] == 0.0)
check("short audio is NOT split", len(list(_Stub()._windows(tone(10)))) == 1)

cut = wins[1][0]
at_cut = float(np.abs(audio[int(cut * rate): int(cut * rate) + 1600]).mean())
mid_speech = float(np.abs(audio[10 * rate: 10 * rate + 1600]).mean())
check("a pause inside the search window IS found", at_cut < mid_speech / 5,
      f"cut energy {at_cut:.3f} vs speech {mid_speech:.3f}")

# And the honest converse: no pause nearby means it cuts mid-speech anyway,
# because a window that overruns the encoder ceiling is worse than a clipped word.
no_pause = tone(87, 250)
w2 = list(_Stub()._windows(no_pause))
check("no pause nearby -> still splits (a clipped word beats truncation)",
      len(w2) > 1 and all(len(w) / rate <= 45.0 + 1e-6 for _, w in w2))

print("\n  Speaker alignment\n")
from diarize import label, TOKEN_SEC

# two ADJACENT turns: nothing overlaps, so nothing may be flagged as crosstalk
res = {"tokens": ["a", "b", "c", "d"], "timestamps": [0.0, 0.9, 1.0, 1.9],
       "language": "hi", "duration_sec": 2.0, "text": "abcd"}
adjacent = [(0.0, 1.0, 0), (1.0, 2.0, 1)]
out = label(res, adjacent)
check("adjacent turns produce NO crosstalk", out["crosstalk_sec"] == 0.0,
      f"got {out['crosstalk_sec']}s — a token straddling a seam must not "
      f"read as two people talking")
check("both speakers are found", out["num_speakers"] == 2, str(out["speakers"]))

# genuinely concurrent turns
concurrent = [(0.0, 2.0, 0), (0.5, 1.5, 1)]
out2 = label(res, concurrent)
check("concurrent turns ARE flagged", out2["crosstalk_sec"] > 0,
      f"got {out2['crosstalk_sec']}s")
check("flagged lines carry a warning",
      all("note" in l for l in out2["lines"] if l.get("overlap")))
check("raw arrays are stripped from output",
      "tokens" not in out2 and "timestamps" not in out2)

out3 = label(res, [])
check("no turns -> speaker None, not a guess",
      all(l["speaker"] is None for l in out3["lines"]))

print("\n  Manifest\n")
import json
m = json.loads((Path(__file__).resolve().parent.parent / "models.json").read_text())
indic = m["models"]["indic-conformer-600m"]
check("model is pinned to a SHA, not a branch", len(indic["sha"]) == 40, indic["sha"])
check("points at AI4Bharat", indic["repo"].startswith("ai4bharat/"), indic["repo"])
check("licence recorded", indic.get("license") == "MIT")
check("no third-party repackaging", "meetsync" not in json.dumps(m).lower())

print(f"\n  {len(PASS)} passed, {len(FAIL)} failed\n")
if FAIL:
    for f in FAIL:
        print(f"    FAILED: {f}")
    print()
    sys.exit(1)
