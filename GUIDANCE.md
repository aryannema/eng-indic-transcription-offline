# Guidance

Why this is built the way it is, and what to know before changing it.

---

## What this is

Offline speech-to-text for English and eight Indian languages, running on a CPU. A command-line
transcriber, optionally a web interface, and nothing that talks to a server.

**What makes it worth having is not accuracy.** Cloud services are more accurate. What this does
that they structurally cannot is run with no network permission at all, which you can verify
yourself in thirty seconds with `tcpdump`.

That matters for a specific set of people: lawyers with privileged recordings, clinics under
data-protection rules, accountants, journalists protecting sources. For everyone else, a cloud
service is probably fine, and saying so is more useful than pretending otherwise.

---

## The decisions, and why

### Utterance mode, not streaming

You speak, you stop, the text appears. Nothing streams word-by-word.

That is not a limitation worked around — it is what every shipped dictation product does,
because watching words appear one at a time, some revised a moment later, is worse than seeing a
finished sentence. It also means no cache-aware encoder is needed, which is convenient because
**no streaming model has been published for any Indian language.**

### One language, declared at setup — and enforced

Hindi and Urdu are the same acoustic model with different output alphabets. A
model left to choose writes the wrong script, and does it *silently*.

This is not managed by care, it is removed by construction. The release ships
`language_masks.json`: 22 languages, each a 5633-element mask selecting exactly
257 of a shared vocabulary. The mask is applied to the logits **before** argmax,
so tokens from every other language are not unlikely — they are absent. Feeding
Hindi audio through the `ur` mask produces Urdu script and *no Devanagari
character at all*; through `ta`, Tamil and nothing else.

So declaring the language at setup is a hard guarantee, not a hope.

### RNN-T by default, CTC available

The checkpoint is hybrid and ships **both** decoders. RNN-T is the default
because its prediction network carries state between frames, so the joint network
sees the previous token — an implicit language model, which is exactly what CTC
lacks. On the same 45 s of Hindi:

| | |
|---|---|
| CTC | `्रेश पच्चीसार फ को न ज दी तो म सव आपसे` |
| RNN-T | `फ्रेशर पच्ची फ्रेशर्स को अपने दी तो मेरा सवाल आपसे` |

It is close to free: the encoder pass is shared and dominates runtime, and the
greedy loop added 0.13 s over 563 frames.

`decoder="ctc"` remains available and is worth choosing when you need uniform
per-frame timestamps — CTC emits one token per frame, while RNN-T can emit
several at one frame, which makes its timestamps coarser. That matters for
speaker alignment, not for reading the text.

### SQLite or PostgreSQL

SQLite for one person on one machine: no server, no configuration, one file. PostgreSQL when
there are several users. The backend detects which from `DATABASE_URL`.

Defaulting to Postgres would mean a database server for a single-user desktop tool, which is
absurd. Defaulting to SQLite only would cap it at one machine.

---

## Where the models come from

| | Source | Licence |
|---|---|---|
| Indic ASR | **AI4Bharat IndicConformer-600M-Multi**, official ONNX export, pinned to `e9b71b36` | MIT |
| Diarization | pyannote-segmentation-3.0 + CAM++, via k2-fsa ONNX exports | Apache-2.0 |
| Recognition runtime | onnxruntime + kaldi-native-fbank | MIT / Apache-2.0 |
| Diarization runtime | sherpa-onnx | Apache-2.0 |

**We train nothing and convert nothing.** The graphs, the vocabularies and the 22
per-language masks are AI4Bharat's own published export, used as published.

That model was built at **IIT Madras** under **Bhashini**, the National Language
Translation Mission of **MeitY, Government of India**. It covers all 22 scheduled
languages including Bodo, Santali, Dogri and Manipuri — languages no commercial
lab would fund, because the ones with fewest speakers are least profitable. See
[NOTICE.md](NOTICE.md). Nothing obliges you to say so in your interface; saying
so anyway is accurate and a better story than silence.

Everything is MIT or Apache-2.0. Commercial use needs nobody's permission.

---

## Numbers you should be able to reproduce## Numbers you should be able to reproduce

| | |
|---|---|
| 22 languages | one shared encoder |
| Model load | 1.9 s |
| 45 s Hindi, 8 threads | 1.24 s — 36× realtime |
| 739 s Hindi debate | 19.1 s — 39× realtime, 17 windows |
| Peak RAM | ~2.6 GB (fp32 export) |

### Long audio is split, and this is not an optimisation

The encoder is full-context and its positional table is fixed at export. A single
480 s pass fails outright (`broadcast 1000 by 6000`), and — far worse — a 240 s
pass **completes with no error** while returning 264 tokens where 120 s of the
same audio returned 538. It silently stops emitting.

So `transcribe()` splits anything over 45 s, cutting at the quietest 100 ms near
each boundary. Token counts are now monotonic in duration; before, a 30-minute
recording produced a short, plausible, badly incomplete transcript with nothing
to indicate it.

```bash
python scripts/fleurs-wer.py 100
```

If your numbers differ substantially, the audio is probably not 16 kHz mono, or the thread
count is not what you think.

---

## Changing things

**Adding a language** is a 0.7 MB file, not a model. The AI4Bharat release has 22 separate
language heads that share one encoder — adding one means adding its head and its entry in
`models.json`.

**Adding an output format** means one writer function in `scripts/transcribe.py`. The existing
five are ten lines each. Watch the timestamp separator: SRT uses a comma before milliseconds and
WebVTT a dot, and getting it wrong produces a file that looks correct and that no player loads.

**Changing the model** means editing `models.json`. Pin a commit SHA, never `main` — a floating
pointer means two people get different weights and a bug report cannot be tied to either.

---

## Claims to avoid

**Do not say "real-time".** It is faster than real time, and it is not streaming. Those are
different things and the second is what people will assume.

**Do not quote a WER without the test set.** The same model scores 6.5% on one benchmark and
11.7% on another. A number without its corpus is not a measurement.

**Do not claim mixed-script output.** English inside Hindi comes out in Devanagari. That is a
vocabulary limit, not a bug, and pretending otherwise sets up a disappointment.

**Do not describe the privacy property as a policy.** It is a verifiable fact — say how to check
it rather than asking to be believed.
