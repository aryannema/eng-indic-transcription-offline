# Attribution

Created by **Aryan Nema** as an exploration of automatic speech recognition,
for educational purposes.

This project is a thin layer over models built with public money by public
institutions. The engineering here is packaging and plumbing; the hard part —
the acoustic models and the data behind 22 Indian languages — was done by
others, and this file exists so that is not quietly forgotten.

## The speech recognition model

**IndicConformer-600M-Multi** — `ai4bharat/indic-conformer-600m-multilingual`

> AI4Bharat's IndicConformers is a suite of ASR models built to deliver accurate
> speech-to-text conversion in all 22 official Indian languages. As the country's
> first open-source ASR system covering such a vast array of languages…

- **Built by:** [AI4Bharat](https://ai4bharat.org), the AI research lab at
  **IIT Madras** (Indian Institute of Technology Madras)
- **Part of:** **Bhashini**, the National Language Translation Mission of the
  **Ministry of Electronics and Information Technology (MeitY), Government of
  India** — the national effort to give every Indian language working speech and
  language technology
- **Licence:** MIT — © 2024 AI4Bhārat
- **Source:** https://github.com/AI4Bharat/IndicConformerASR
- **Pinned revision:** `e9b71b369c048e2c6b634d4c131061c34e441179`
- **Architecture:** 600M-parameter multilingual Conformer, hybrid CTC + RNN-T

This is a government-funded public research model. It exists because a public
institution decided that speakers of Maithili, Bodo, Santali, Konkani, Dogri and
Manipuri deserve working speech recognition, not only speakers of English and
Hindi. No commercial lab would have built it, because the languages with the
fewest speakers are the least profitable and were funded anyway.

We convert nothing and retrain nothing. The ONNX graphs, the vocabularies and
the 22 per-language masks are AI4Bharat's own published export, used as
published.

## Speaker diarization

- **pyannote-segmentation-3.0** — speaker segmentation with native overlap
  handling, via the ONNX export maintained by the **k2-fsa / sherpa-onnx**
  project (Apache-2.0)
- **CAM++** — speaker embedding model, same source

## Runtimes

| | |
|---|---|
| [onnxruntime](https://onnxruntime.ai) | MIT — runs the recognition graphs |
| [kaldi-native-fbank](https://github.com/csukuangfj/kaldi-native-fbank) | Apache-2.0 — log-mel features, matching what the model was trained on |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Apache-2.0 — diarization pipeline |

## Licences at a glance

| | |
|---|---|
| This project's code | MIT, © 2026 Aryan Nema — see [LICENSE](LICENSE) |
| IndicConformer model | MIT (AI4Bharat / IIT Madras, Bhashini, MeitY) |
| Diarization models + runtimes | Apache-2.0 |

All permit commercial use without further permission. The model licences are
separate from this project's LICENSE and are not covered by it.

## If you use this

None of these licences require attribution in your interface. Crediting
AI4Bharat, IIT Madras and Bhashini anyway is both accurate and a better story
than silence — it tells your users the technology came from Indian public
research, which is unusual and worth saying.
