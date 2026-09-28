# Offline speech-to-text for 22 Indian languages

> Created by **Aryan Nema** as an exploration of automatic speech recognition,
> for educational purposes. Built on **IndicConformer** by **AI4Bharat**,
> Indian Institute of Technology Madras — see
> [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

Transcribes Hindi, Tamil, Bengali, Marathi, Telugu, Kannada, Malayalam, Gujarati,
Punjabi, Odia, Assamese, Urdu, Nepali, Sanskrit, Sindhi, Konkani, Maithili,
Dogri, Bodo, Santali, Manipuri and Kashmiri — on a CPU, with no network.

```bash
python scripts/transcribe.py recording.wav --format srt,txt
```

A 12-minute Hindi TV debate transcribes in **19 seconds on a CPU**, 39× faster
than real time. No GPU. No API key. No data leaving the machine.

## Why this rather than a cloud API

Cloud services are more accurate. Say so plainly — anything else is a sales
pitch. What this does that they structurally cannot is run with **no network
permission at all**, which you can verify yourself in thirty seconds:

```bash
sudo tcpdump -i any port not 22      # transcribe something. count the packets.
```

There will be none. That matters for a specific set of people — lawyers with
privileged recordings, clinics under data-protection rules, accountants,
journalists protecting sources. For everyone else, a cloud service is probably
fine.

## What it does

| | |
|---|---|
| **22 languages** | one shared encoder; a language is a 0.6 MB head |
| **Speaker labels** | who spoke when, including *both at once* |
| **Five output formats** | txt, srt, vtt, json, md |
| **Long files** | split automatically; a 30-minute recording is fine |
| **Agent tools** | MCP server, so Claude can transcribe for you |

## Measured, on one CPU

| | |
|---|---|
| Model load | 1.9 s |
| 45 s Hindi | 1.24 s — **36× realtime** |
| 739 s Hindi debate | 19.1 s — **39× realtime** |
| Diarization | 27× realtime |
| RAM | ~2.6 GB |

## The language is declared, and enforced

Hindi and Urdu are the same acoustic model with two alphabets. Asked to guess, a
model writes the wrong script *silently*.

Here it cannot. The release ships a mask per language, applied to the logits
**before** argmax, so every other language's tokens are not merely unlikely —
they are absent. The same Hindi audio through three masks:

```
hi  →  सो ओवर द लस्ट वन इयर…
ur  →  سو اوورا لسٹ ون ایئر…
ta  →  சோ ஓவர் தலஸ்ட வன் இயர்…
```

Zero script mixing in any of them.

## Speaker overlap is marked, not guessed

Two people talking at once is detected — the segmentation model predicts
concurrent speech as a native output class. On a real Hindi TV debate, **43% of
all speech was overlapped.**

What it will *not* do is give you two transcripts. The recogniser sees one mixed
waveform and cannot separate the voices; that needs speech separation, which this
does not ship. So overlapped regions are labelled `crosstalk — attribution
uncertain` rather than confidently attributed to one person.

That restraint is deliberate. In a legal or medical transcript, putting a
sentence in the wrong person's mouth is the most damaging error this tool can
make. Nobody solves this cleanly — even the current best open diarizer publishes
no overlap-specific accuracy figure.

## Install

Python 3.12, one CPU core, 4 GB RAM. Full detail in
[INSTALLATION.md](INSTALLATION.md).

### First: the model is gated

The model is **MIT licensed and approval is automatic**, but the files sit
behind a Hugging Face account. This takes a minute and cannot be skipped:

1. Sign in at [huggingface.co](https://huggingface.co) and open
   [ai4bharat/indic-conformer-600m-multilingual](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual)
2. Click **Agree and access repository** — granted immediately
3. Create a **read** token at [settings/tokens](https://huggingface.co/settings/tokens)
4. `export HF_TOKEN=...` (or run `huggingface-cli login`)

Without it the download fails with `HTTP 401` on every file. The token is read
from the environment and never written or printed.

### Then

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python onnxruntime kaldi-native-fbank numpy

python scripts/fetch_models.py --list        # the 22 languages
python scripts/fetch_models.py --indic hi    # 2.4 GB, pinned to a SHA
python scripts/transcribe.py recording.wav
```

Add `sherpa-onnx` only if you want speaker labels.

**Download size is 2.4 GB and that is almost entirely the encoder**, which is
shared by all 22 languages — a language is a 0.7 MB head, so a second language
later costs 0.7 MB, not another 2.4 GB. Expect ~2.2 GB resident while running.

### Web UI (optional) — pnpm workspace

```bash
corepack enable      # activates the pnpm version pinned in package.json; no nvm needed
pnpm install         # from the REPO ROOT, not from ui/
pnpm build           # ~2s
```

pnpm rather than npm on purpose: npm's flat `node_modules` lets a package import
something it never declared, which works on your machine and breaks on someone
else's. pnpm's store is content-addressable and hard-linked, so one copy of a
version is shared across every project on the machine. See
[INSTALLATION.md](INSTALLATION.md#3-web-ui--pnpm-only).

## Where the models come from

**AI4Bharat's IndicConformer-600M**, built at **IIT Madras** under **Bhashini**,
the National Language Translation Mission of **MeitY, Government of India**. MIT
licensed, pinned to a commit SHA.

We train nothing and convert nothing — the graphs and vocabularies are
AI4Bharat's own published export, used as published. It covers languages no
commercial lab would fund, because the ones with fewest speakers are least
profitable, and it was funded anyway. [NOTICE.md](NOTICE.md) has the full
attribution and it is worth reading.

## Documentation

| | |
|---|---|
| [INSTALLATION.md](INSTALLATION.md) | setup, and what breaks |
| [REQUIREMENTS.md](REQUIREMENTS.md) | hardware and versions |
| [GUIDANCE.md](GUIDANCE.md) | why it is built this way; **claims to avoid** |
| [BRANDING.md](BRANDING.md) | marks and colour |
| [NOTICE.md](NOTICE.md) | attribution |
| [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) | model and runtime licences, verbatim |
| [docs/how-it-works.html](docs/how-it-works.html) | the pipeline, illustrated |

## Honest limitations

- **English inside Indic audio comes out transliterated.** The vocabulary has no
  Latin script, so `upload` becomes `अपलोड`. A vocabulary limit, not a bug.
- **No two-speaker transcripts during crosstalk.** Marked, not separated.
- **Not streaming.** Faster than real time is not the same as live captioning;
  no streaming model has been published for any Indian language.
- **Accuracy on overlapped speech is unmeasured.** It recovers far more content
  than the alternative decoder, but no reference transcript exists yet to put a
  number on it, so we do not publish one.

## Licence

MIT, © 2026 Aryan Nema — created as an exploration of ASR for educational
purposes. Covers the code in this repository only. The models are separately licensed — MIT and Apache-2.0, all
permitting commercial use. See [LICENSE](LICENSE), [NOTICE.md](NOTICE.md) and
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
