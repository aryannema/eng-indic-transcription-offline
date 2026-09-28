# Tests

```bash
python -m tests.test_asr        # 22 checks, no model download needed
python scripts/doctor.py        # environment
python scripts/fleurs-wer.py 100   # word error rate on FLEURS
```

## What `test_asr.py` covers

It tests the logic that has actually broken during development, not the model.

**Audio input.** 16 kHz mono reads correctly; 8 kHz and stereo are **refused
rather than resampled**. Silently resampling would degrade output with no
warning, which is worse than an error.

**Windowing** — the fix for a real bug. A single pass over 240 s of audio once
returned *264 tokens where 120 s of the same audio returned 538*, with no error
raised, and 480 s failed outright. The encoder is full-context and its
positional table is fixed at export. So `transcribe()` splits at 45 s, cutting
at the quietest point within ±3 s of each boundary.

The tests check that nothing is lost, that no window exceeds the ceiling, that a
pause inside the search window is found — **and the honest converse: when there
is no pause nearby it cuts mid-speech anyway**, because a clipped word beats a
silently truncated transcript.

**Speaker alignment**, where the subtlety lives. Two *adjacent* turns must
produce **no** crosstalk: a token straddling the seam intersects both turns, and
an earlier version flagged that as two people talking — a false positive at every
speaker change. Overlap is decided at the token's midpoint using half-open
intervals; a point cannot lie in two abutting intervals but does lie in two
genuinely concurrent ones. Genuinely concurrent turns *are* flagged, and flagged
lines carry a warning rather than a confident speaker name.

**Manifest.** The model is pinned to a 40-character SHA rather than a branch,
points at AI4Bharat, records its licence, and contains no third-party
repackaging.

## What is NOT tested here, and why

**Accuracy.** That needs the 2.4 GB weights and a reference transcript. Speed and
memory are published; **no accuracy figure is**, because none has been measured
against ground truth. `scripts/fleurs-wer.py` computes WER against FLEURS
(CC-BY) when you have the model.

## Why there are no audio files in this directory

The clips used during development came from YouTube. Redistributing them would
be copyright infringement, however convenient it would be for testing.

So the tests **generate** the audio they need — sine tones and silence, which is
enough to exercise format handling and windowing, and is not enough to exercise
recognition quality. For that, use:

- **FLEURS** (CC-BY) — `scripts/fleurs-wer.py`, 102 languages with reference
  transcripts
- **Common Voice** (CC0) — Mozilla, includes several Indian languages
- **Your own recording** — the most useful, because it matches the audio you
  actually care about

If you contribute audio, contribute what you own or what is openly licensed, and
never someone's voice without their permission.

## Hardware the published numbers were measured on

| | |
|---|---|
| CPU | Intel Core Ultra 9 285K, 8 threads used of 24 |
| RAM | 62 GB |
| Provider | `CPUExecutionProvider` — **no GPU** |

Every speed figure in this repository is CPU-only. A GPU is present on that
machine and is not used by any of it.
