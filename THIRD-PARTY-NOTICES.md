# Third-party notices

This repository was created by **Aryan Nema** as an exploration of automatic
speech recognition, for educational purposes. Its own code is MIT
(© 2026 Aryan Nema — see [LICENSE](LICENSE)).

This project loads speech models it did not create. They are licensed
separately and are **not** covered by [LICENSE](LICENSE), which applies only to
the code in this repository.

Kept out of `LICENSE` deliberately, and this is measured rather than assumed:
GitHub's detector reports `NOASSERTION` the moment anything is added to the MIT
body — including extra words on the copyright line. An undetected licence reads
as "Other" to anyone evaluating whether they may use this, which is worse than
having the attribution one click away.

## IndicConformer

Automatic speech recognition for all 22 scheduled Indian languages, built by
**AI4Bharat** at the **Indian Institute of Technology Madras**, under
**Bhashini** — the National Language Translation Mission of the Ministry of
Electronics and Information Technology, Government of India.

```
Copyright (c) AI4Bharat, Indian Institute of Technology Madras
Source:  https://github.com/AI4Bharat/IndicConformerASR
Model:   https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
Pinned:  e9b71b369c048e2c6b634d4c131061c34e441179
License: MIT
```

Used as published. Nothing here is retrained, converted or re-exported.

### Their LICENSE, verbatim

```
MIT License

Copyright (c) 2024 AI4Bhārat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Diarization models and runtimes

| | | |
|---|---|---|
| pyannote-segmentation-3.0 | speaker segmentation, ONNX export by k2-fsa | Apache-2.0 |
| CAM++ | speaker embeddings, same source | Apache-2.0 |
| sherpa-onnx | diarization runtime | Apache-2.0 |
| onnxruntime | recognition runtime | MIT |
| kaldi-native-fbank | log-mel features | Apache-2.0 |

All permit commercial use without further permission.

See [NOTICE.md](NOTICE.md) for why this attribution is worth making even though
no licence requires it.
