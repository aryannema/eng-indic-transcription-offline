# Setting up your machine

Written for someone who has not done this before. Every tool here exists to
solve one specific problem, and the problem is named so you can decide whether
you actually need it.

Two independent halves. **You only need the Python half** to transcribe audio.

---

## Python — required

### Which Python, and why it matters

**3.12.** Not newer. `sherpa-onnx` (needed only for speaker labels) publishes
wheels a release or two behind Python, and on 3.13+ you get *no matching
distribution* rather than a useful message.

### uv — recommended

`uv` is a fast installer that also manages Python versions, so you do not need
`pyenv` or a system Python of the right version.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
# Windows PowerShell:
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python onnxruntime kaldi-native-fbank numpy
```

`uv venv` downloads Python 3.12 if the machine lacks it. That single behaviour
is why it is recommended over `pip` + `venv`.

**`kaldi-native-fbank` is not swappable.** The model was trained on
librosa-style log-mel with per-feature normalisation. A different front end does
not raise an error — it quietly produces worse text, which is the hardest kind
of bug to notice.

### conda — if your course already uses it

Conda works. It is heavier, and it manages non-Python libraries too, which
matters for scientific packages and does not matter here.

```bash
conda create -n indic python=3.12
conda activate indic
pip install onnxruntime kaldi-native-fbank numpy
```

Do not mix: inside an activated conda env, use that env's `pip`, not `uv pip`.
Mixing installers in one environment is how you get two versions of numpy and an
afternoon of confusion.

### Optional extras

```bash
uv pip install sherpa-onnx   # speaker labels ("who spoke when")
uv pip install yt-dlp        # transcribe straight from a video URL
uv pip install mcp           # expose transcription as agent tools
```

**yt-dlp is a Python package**, not a separate binary — `uv pip install yt-dlp`
and you are done. It needs Python 3.10+.

### ffmpeg — not Python, still needed

Converts anything that is not already 16 kHz mono WAV.

```bash
sudo apt install ffmpeg        # Debian / Ubuntu
brew install ffmpeg            # macOS
winget install ffmpeg          # Windows
```

Without it you must convert by hand:

```bash
ffmpeg -i input.mp3 -vn -ac 1 -ar 16000 out.wav
```

Wrong sample rate is the single most common cause of "it returned nothing".

---

## Node — only for the web UI

Skip this entirely if you use the command line.

### pnpm, not npm — and no nvm

```bash
corepack enable      # ships inside Node 16.9+; nothing to install
pnpm install         # from the REPO ROOT
pnpm build
```

`corepack` reads `packageManager` in `package.json` and activates exactly that
pnpm version. This is why **nvm is unnecessary**: the version is pinned in the
repository, not in your shell profile, so everyone gets the same one.

### Why not npm

Not preference — it prevents a class of bug. npm installs a **flat**
`node_modules`, so a package can `import` something it never declared, because
that dependency happens to be hoisted. It works for you and breaks for the next
person. These are *phantom dependencies*.

pnpm builds a nested, symlinked tree where a package reaches only what it
declared. The undeclared import fails immediately, on the machine that
introduced it.

### The content-addressable store (CAS)

pnpm keeps **one copy of every package version** in a global store, and
hard-links it into each project instead of copying.

```bash
pnpm store path      # where it lives
pnpm store prune     # delete versions nothing references
```

| | |
|---|---|
| Ten projects, same React version | one copy on disk, not ten |
| Second install of a seen version | a hard link, not a download — works offline |

**Never edit files inside `node_modules`.** They are hard links into the store,
so you would be editing every project on the machine. Use `pnpm patch`.

#### Environment variables

| variable | what it does | when to set it |
|---|---|---|
| `PNPM_HOME` | where the pnpm binary and globals live | set by `pnpm setup`; must be on `PATH` |
| `PNPM_STORE_PATH` | moves the CAS | small SSD, big external disk |
| `COREPACK_ENABLE_STRICT=0` | stops corepack refusing a mismatched pnpm | rarely |

```bash
pnpm setup                     # writes PNPM_HOME into your shell profile
export PNPM_STORE_PATH=/mnt/big/pnpm-store   # optional
```

The store must be on the **same filesystem** as your projects. Across
filesystems hard links are impossible, so pnpm silently copies instead and you
lose the disk saving without any warning.

---

## Check it worked

```bash
python scripts/doctor.py
```

It reports Python version, every required and optional package, ffmpeg, node,
pnpm, whether a Hugging Face token is visible, whether the model is downloaded,
and whether you have enough RAM — and prints the exact command to fix anything
missing. Run it before opening an issue.

---

## Hugging Face access

The model is **MIT licensed** and approval is **automatic**, but the files sit
behind an account.

1. Sign in at [huggingface.co](https://huggingface.co)
2. Open [ai4bharat/indic-conformer-600m-multilingual](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual)
   and click **Agree and access repository**
3. Create a **read** token at [settings/tokens](https://huggingface.co/settings/tokens)
4. `export HF_TOKEN=...` — or `uv pip install huggingface_hub && huggingface-cli login`

Put the export in `~/.bashrc` or `~/.zshrc` so it survives a new terminal.
**Never commit a token.** If one is ever pushed, revoke it immediately — rotating
is cheap, and a leaked token is not made safe by deleting the commit.

---

## Disk and memory

| | |
|---|---|
| Model download | 2.4 GB (fp32) |
| RAM while running | ~2.7 GB (fp32) or ~1.3 GB (int8) |
| `node_modules` | ~200 MB, mostly hard links |
| Minimum practical RAM | 4 GB |

On 4 GB, build the int8 model — `python scripts/quantize.py` — which halves the
memory and runs faster. See [GUIDANCE.md](GUIDANCE.md) for what it costs.
