# Contributing

The most useful contributions here need no code at all.

## 1. Tell me what the output sounds like in your language

22 languages are supported. I have only listened carefully to Hindi.

```bash
python scripts/fetch_models.py --indic kn     # or ta, bn, mr, or, sat, ...
python scripts/transcribe.py your_clip.wav
```

Open an issue with: the language, roughly what was said, and what came out.
**"This is wrong and here is how" is more useful than a bug report about a
crash** — crashes are easy to find and quality problems are not.

## 2. Hand-transcribe two minutes of audio  ← most valuable

This project publishes speed and memory numbers, and **deliberately publishes no
accuracy number**, because no reference transcript exists to measure against.

Two to three minutes, transcribed by someone who speaks the language, would let
us compute a real word error rate — and settle an open question: whether the
int8 build is actually worse than fp32 or merely different. Right now we can
only say they differ.

Contribute audio you own or that is openly licensed. Do not upload copyrighted
recordings, and do not upload anyone's voice without their permission.

## 3. Break it on hardware I do not have

Old laptops, Raspberry Pi, Windows, macOS, 4 GB machines.

```bash
python scripts/doctor.py     # paste the output into the issue
```

## 4. Real-time recognition  ← the hard one

Today: speak, stop, see text. Live captioning needs a model that emits tokens
without revising them, and **no streaming model has been published for any
Indian language**.

Useful starting points:

- Benchmark a streaming transducer (RNN-T, Zipformer) for one Indian language
- Measure the real latency floor on a laptop CPU, voice-activity detection
  included, and report it honestly
- Work out whether an existing multilingual streaming model can be fine-tuned on
  a student budget

Partial results are welcome. "I tried this and it did not work, here is the
measurement" is a contribution — it stops the next person repeating it.

## 5. Speech separation for crosstalk

Overlapping speech is *detected* but cannot be *transcribed*: one mixed waveform
cannot yield two transcripts without separating the voices first. A separation
front end (TF-GridNet, MossFormer class) would be a substantial addition.

## Ground rules

- **Measure, do not assert.** A number with the command that produced it beats a
  claim. If something is unverified, say so — this repository does that about
  its own int8 build.
- **No accuracy claims without a test set.** The same model scores differently
  on different corpora; a WER without its corpus is not a measurement.
- Run `python scripts/doctor.py` before reporting a setup problem.
- Do not commit model weights or tokens. Weights are fetched at a pinned SHA;
  tokens are read from the environment.

## Running the tests

```bash
python scripts/doctor.py                  # environment
python -m tests.test_asr                  # decoding, offline, no model needed
python scripts/fleurs-wer.py 100          # error rate on FLEURS (CC-BY)
```

See [tests/README.md](tests/README.md) for what is checked and what is not.
