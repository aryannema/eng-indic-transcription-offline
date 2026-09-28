# Where this is going

I am an engineering student exploring speech technology for Indian languages.
This repository is the first working piece. What follows is what I intend to
build next and why — written down so that anyone who wants to work on it knows
where the edges are.

## Why Indian languages specifically

English speech recognition is a solved commercial problem. Indian languages are
not, and the gap is not evenly distributed: Hindi has usable options, Bodo,
Santali, Dogri and Manipuri have almost none, because the languages with the
fewest speakers are the least profitable to serve.

The model this project runs — AI4Bharat's IndicConformer, built at **IIT Madras**
under **Bhashini** (MeitY, Government of India) — exists because a public
institution decided all 22 scheduled languages were worth doing anyway. That
seems to me the interesting place to build.

## What works today

| | |
|---|---|
| Speech → text, 22 languages, offline on a CPU | working |
| Speaker labels, including overlap detection | working |
| Five output formats, files of any length | working |
| int8 build — 53% less memory, faster | experimental, numbers published |
| Agent tools over MCP | working |

A 12-minute Hindi TV debate transcribes in **19 seconds on a CPU** — no GPU, no
network, nothing leaving the machine.

## Next: real-time

Today you speak, stop, and then see text. Live captioning means seeing words
while you speak, and it is **a different model, not a tuning problem**.

This encoder reads the whole clip before deciding anything — its attention has
no causal mask and its positional table is fixed at export, which is also why
audio over ~2 minutes must be split. A streaming model keeps a cache and emits
tokens as it goes. **No streaming model has been published for any Indian
language**, which is precisely what makes it worth attempting.

Where I would start, and where help is most useful:

- Benchmark streaming architectures (transducers — RNN-T, Zipformer) that emit
  tokens without revising them
- Measure the real latency floor on a laptop CPU, honestly, including the
  voice-activity detection in front
- Find out whether an existing multilingual streaming model can be fine-tuned
  for one Indian language on a student's budget

## Then: text-to-speech

Speech recognition and speech synthesis are two halves of the same interface.
An offline Indic TTS that runs on a laptop would let the same machine listen and
answer — which is what any assistant, accessibility tool or voice bot needs.

Open Indic TTS models exist. Whether they run acceptably on a CPU, and what they
sound like to a native speaker rather than on a benchmark, is the open question.

## Then: translation

22 languages transcribed is 22 languages that could be translated between. The
useful version is not English-pivot — Tamil → Hindi should not have to become
Tamil → English → Hindi, because each hop loses something.

## What I want to learn from this

Concretely: how acoustic models are structured and why particular choices are
made; what quantisation costs in accuracy rather than in theory; how to measure
a speech system so the numbers mean something; and how to package research
models so an ordinary person can actually run them. That last one turns out to
be most of the work.

## Help wanted

Things that would genuinely move this forward, roughly easiest first:

1. **Test a language I have not.** 22 are supported; I have only listened
   carefully to Hindi output. If you speak Kannada, Odia, Santali or anything
   else, run a clip and tell me what is wrong with it.
2. **Hand-transcribe two minutes of audio.** This is the highest-value
   contribution and needs no code. Without a reference transcript I cannot
   compute a real error rate, which is why this repository publishes speed and
   memory numbers but no accuracy claim.
3. **Try it on hardware I do not have** — an old laptop, a Raspberry Pi,
   Windows, a Mac. Tell me what broke.
4. **Streaming.** The hard one. See above.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how.

---

*Built on AI4Bharat's IndicConformer (MIT). I did not train it and I do not
claim to have. What I built is the packaging, the RNN-T decoding path, the
quantised build, and the measurements.*
