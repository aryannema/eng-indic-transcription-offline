# Requirements

Every number here was measured, not estimated. Where something is extrapolated, it says so.

---

## The short version

**One CPU core and 2 GB of RAM.** No GPU. That is not a minimum stated defensively — it is
where the measurement actually landed.

---

## Measured: speed against threads

45 seconds of Hindi audio, `indic-conformer` int8, x86-64:

| Threads | Decode time | Speed | Peak RAM |
|---|---|---|---|
| **1** | 3.22 s | **14× realtime** | 744 MB |
| 2 | 2.06 s | 22× | 744 MB |
| 4 | 1.45 s | 31× | 744 MB |
| 8 | 1.17 s | 38× | 744 MB |

Model load: **0.3 s**.

Two things worth reading off that table.

**One thread is already fourteen times faster than the audio plays.** A five-second dictation
utterance transcribes in about a third of a second on a single core. This does not need many
cores; it needs *a* core.

**Threads help less than you would expect** — 8× the cores buys 2.7× the speed. Past four
threads the returns are small, so `--threads 4` is the sensible default and more is rarely worth
the contention.

**Memory is flat at 744 MB** regardless of threads, because the weights load once and are shared.

---

## Minimum

| | Minimum | Why |
|---|---|---|
| CPU | any x86-64 or ARM64, **1 core** | 14× realtime measured single-threaded |
| RAM | **2 GB** | 744 MB measured peak, plus the OS |
| Disk | **500 MB** | 197 MB model, runtime, working space |
| GPU | **none** | not used, not detected, not required |
| Network | **none after install** | models download once |
| OS | Linux, Windows 10+, macOS 11+ | sherpa-onnx ships wheels for all three |
| Python | **3.12** | sherpa-onnx wheels lag newer releases — 3.13 and 3.14 may have none |

That specification is met by most machines built since roughly 2012, by a Raspberry Pi 4, and by
the cheapest VPS with no accelerator.

**The honest caveat:** those figures came from a workstation CPU and an Intel Arc laptop. The
single-thread number is the one to reason from, because it has the least hardware advantage
built in. A slower core will be proportionally slower — and there is a great deal of headroom
between 14× and 1×.

---

## Recommended

| | | |
|---|---|---|
| CPU | 4 cores | 31× realtime; past this the gains are small |
| RAM | 4 GB | comfortable with a browser open |
| Disk | 2 GB | room for several languages and the optional cleanup model |

---

## Disk, by what you install

| | Size |
|---|---|
| English ASR only | 73 MB |
| One Indian language | 197 MB |
| Both | 270 MB |
| Plus optional cleanup LLM | +397 MB |

Weights are **never** committed to this repository. They are fetched at install time from Hugging
Face, pinned to a commit SHA, so an install today and one next year produce byte-identical
models — and a bug report can be tied to known weights.

---

## Web UI

| | |
|---|---|
| Node | 20+ |
| pnpm | 10+ |
| Build | **2.05 s**, measured |
| Bundle | 230 KB JS (70 KB gzipped), 25 KB CSS |

---

## Backend

| | |
|---|---|
| Python | 3.12 |
| Database | **SQLite** for a single-user local install, **PostgreSQL** for a server |
| Extra for Postgres | `pgcrypto` extension, for `gen_random_uuid()` |

SQLite needs no server and no configuration. The backend detects which you are using from
`DATABASE_URL` and skips the Postgres migrations when the URL begins `sqlite:///`.

---

## Audio input

Whatever you have — `ffmpeg` converts it. The model itself takes one format and only one:

```
16,000 Hz · mono · float32 · range [-1.0, 1.0]
```

```bash
ffmpeg -i input.mp3 -vn -ac 1 -ar 16000 out.wav
#            -vn drop video   -ac 1 mono   -ar 16000 resample
```

Feeding int16 samples straight in produces silence or noise rather than an error, which is the
single most common reason a model appears not to work. The conversion is one division: int16
spans ±32768, models want ±1.0.

---

## What this does not do

**No live captioning.** It transcribes a recording or a completed utterance. Word-by-word
streaming needs a cache-aware encoder, and no such model has been published for any Indian
language.

**No speaker separation.** Diarization is a separate model — about 35 MB, and roughly six times
the processing cost of the transcription itself.

**No mixed-script output.** English words inside Hindi speech come out in Devanagari. The
vocabulary is 5,633 tokens and all of them are Indic script, so `upload` has no representation
and the model writes `अपलोड`. That is an arithmetic limit, not a quality one. The model that
does it properly needs about 3 GB of video memory.

---

## Accuracy

| Model | Hindi WER | Hardware |
|---|---|---|
| **indic-conformer int8** | **11.7%** | CPU, 1 core |
| Whisper large-v3-turbo | 31.3% | GPU |

Measured on the first 100 utterances of the FLEURS `hi_in` test set, both models, same audio.

Whisper is eight times larger, needs a GPU, and was wrong nearly three times as often. It
supports Hindi the way a menu lists a dish the kitchen cannot cook.

**Roughly one word in nine will be wrong.** Good enough for a working transcript a human
corrects; not good enough to file unread.
