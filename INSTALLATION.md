# Installation

Three pieces, installed in this order: the transcriber, then the backend if you want the web UI,
then the UI itself. The first one alone is enough to transcribe files from the command line.

Hardware and version requirements are in [REQUIREMENTS.md](REQUIREMENTS.md). The short version:
one CPU core, 2 GB of RAM, **Python 3.12**.

---

## 1. Transcriber — the only part you actually need

### Why 3.12 specifically

`sherpa-onnx` — needed for speaker diarization, not for recognition — publishes
wheels a release or two behind Python. On 3.13 or 3.14 you will most likely get
*no wheel exists* rather than a helpful message, so pin it.

```bash
# uv handles the pinning. curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12 .venv

# recognition: these three are all it needs
uv pip install --python .venv/bin/python onnxruntime kaldi-native-fbank numpy

# speaker labels (optional — skip if you only want text)
uv pip install --python .venv/bin/python sherpa-onnx
```

**`kaldi-native-fbank` is not optional and not interchangeable.** The model was
trained on librosa-style log-mel with per-feature normalisation; a different
front end does not raise an error, it quietly produces worse text. This package
is the same implementation the reference runtime uses, which is why the numbers
match.

If the machine already has a Python managed by uv or a distribution package
manager, `pip install` may refuse with *externally-managed-environment*. That is
correct behaviour — make a venv rather than passing `--break-system-packages`.

### Fetch the models

```bash
python scripts/fetch_models.py --list        # what is available
python scripts/fetch_models.py --english     # 73 MB
python scripts/fetch_models.py --indic hi    # 197 MB
```

**One Indian language.** Hindi and Urdu are near-identical acoustically and differ mainly in
script — a model asked to choose writes the wrong script *silently* rather than raising an
error. Declaring the language at install removes that decision. The choice is recorded in
`models/asr/indic/language.json` and the transcriber reads it from there.

Downloads are resumable and pinned to a commit SHA, so a dropped connection costs nothing and
two people installing months apart get byte-identical weights.

### Transcribe something

```bash
python scripts/transcribe.py recording.wav
python scripts/transcribe.py meeting.mp3 --format srt,txt
python scripts/transcribe.py long.wav --threads 1     # still ~14x realtime
```

Non-WAV input is converted automatically if `ffmpeg` is on PATH. Without it, convert first:

```bash
ffmpeg -i input.mp3 -vn -ac 1 -ar 16000 out.wav
```

**That is the whole installation** if you only want files transcribed. What follows is for the
web interface.

---

## 2. Backend — only if you want the web UI

FastAPI, with a database that is your choice.

```bash
cd backend
uv pip install --python ../.venv/bin/python -r requirements.txt
```

### SQLite — for one person on one machine

```bash
export DATABASE_URL="sqlite:///./vigyanvoice.db"
python main.py
```

No server, no configuration, one file. The backend detects the `sqlite:///` prefix and skips
the PostgreSQL migrations entirely.

### PostgreSQL — for a server or several users

```bash
createdb vigyanvoice
psql -d vigyanvoice -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto;'
export DATABASE_URL="postgresql://user@localhost/vigyanvoice"
python main.py
```

`pgcrypto` supplies `gen_random_uuid()` for the primary keys. Migrations under
`backend/db/migrations/` run automatically on start.

The first account registered is promoted to admin. There is no seeded default password, which
means there is none to forget to change.

---

## 3. Web UI

```bash
cd ui
pnpm install
pnpm dev                    # http://localhost:5173
```

For a production build:

```bash
pnpm build                  # ~2s, 230 KB JS (70 KB gzipped)
pnpm preview
```

The UI calls the backend on **relative** `/api/*` paths, so it works behind any reverse proxy
and equally well with none — Vite's dev server proxies to the backend, and in production the
two are served from the same origin.

No nginx is required. It was used in one deployment; nothing depends on it.

---

## Verifying the privacy claim

Nothing above is a promise you have to take on trust. Run this while transcribing and count the
packets:

```bash
sudo tcpdump -i any port not 22
```

After the models are downloaded, there should be none. If you want to be certain, disconnect the
machine entirely — it will keep working.

---

## Troubleshooting

**`No module named sherpa_onnx`** — the venv is not active, or the wheel did not install
because the Python is too new. Check `python -V` says 3.12.

**`externally-managed-environment`** — the system Python is managed by uv or the distribution.
Create a venv.

**Silence or nonsense from a file that plays fine** — the audio is not 16 kHz mono. Convert it
with the `ffmpeg` line above. This is by far the most common cause, and it produces bad output
rather than an error.

**English words appear in Devanagari** — expected. The vocabulary is Indic-script only, so
`upload` has no representation and the model writes `अपलोड`. Mixed-script output needs a
different model and about 3 GB of video memory.

**Slower than the table in REQUIREMENTS.md** — check `--threads`. The default is 4; on a single
core pass `--threads 1`, which is still around 14× realtime.
