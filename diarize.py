"""
Offline speaker diarization, overlap-aware.

Runs sherpa-onnx with pyannote-segmentation-3.0 and a CAM++ embedding model.
Both are ONNX; nothing here needs torch, NeMo, or the pyannote-audio package.

Why not the classic Kaldi recipe
--------------------------------
MFCC -> x-vector -> PLDA -> agglomerative clustering assigns exactly ONE
speaker per frame. Overlap is not merely handled badly, it is unrepresentable.
pyannote 3.0 instead emits a POWERSET over three local speakers -- its graph
output is [N, T, 7] for {none, s1, s2, s3, s1s2, s1s3, s2s3} -- so two people
talking at once is a class the network predicts directly. Measured: a
constructed 4-second overlap was recovered as two concurrent turns sharing
4.02s, at 47x realtime on CPU.

Detecting overlap is not transcribing it
----------------------------------------
This tells you *that* two people spoke together. It cannot give you two
transcripts: the recogniser sees one mixed waveform and emits one token stream
for that region. Two clean transcripts would need speech separation
(TF-GridNet / MossFormer class) ahead of the recogniser -- more models, more
compute, and worse results on clean audio.

So overlap is used defensively here. Where two speakers are active, the region
is MARKED rather than attributed. Quietly picking the louder one invents
attribution the audio does not support, and in a legal or medical transcript
putting a sentence in the wrong person's mouth is the most damaging error this
tool can make.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# A token's audio extent: the encoder subsamples 8x from a 10ms hop.
TOKEN_SEC = 0.08
SPACE = "▁"


class Diarizer:
    def __init__(self, models: str | Path, threads: int = 4, int8: bool = False):
        import sherpa_onnx

        d = Path(models)
        seg = d / ("segmentation.int8.onnx" if int8 else "segmentation.onnx")
        emb = d / "embedding.onnx"
        for p in (seg, emb):
            if not p.exists():
                raise FileNotFoundError(
                    f"{p.name} not found in {d}. "
                    f"Run: python scripts/fetch_models.py --diarize")

        self._sherpa = sherpa_onnx
        self._seg, self._emb, self._threads = str(seg), str(emb), threads

    def turns(self, audio: np.ndarray, num_speakers: int = -1,
              threshold: float = 0.6) -> list[tuple[float, float, int]]:
        """
        Speaker turns as (start, end, speaker). Turns MAY overlap in time --
        that is the point, and callers must not assume a partition.

        `num_speakers` of -1 lets the clusterer decide. Pass the real count
        whenever it is known: automatic clustering splitting one person into
        several is by far the most common failure, and it is silent.
        """
        s = self._sherpa
        cfg = s.OfflineSpeakerDiarizationConfig(
            segmentation=s.OfflineSpeakerSegmentationModelConfig(
                pyannote=s.OfflineSpeakerSegmentationPyannoteModelConfig(model=self._seg),
                num_threads=self._threads),
            embedding=s.SpeakerEmbeddingExtractorConfig(
                model=self._emb, num_threads=self._threads),
            clustering=s.FastClusteringConfig(
                num_clusters=num_speakers, threshold=threshold),
            min_duration_on=0.3,      # ignore blips shorter than this
            min_duration_off=0.5)     # bridge pauses shorter than this
        sd = s.OfflineSpeakerDiarization(cfg)
        return [(x.start, x.end, x.speaker)
                for x in sd.process(np.asarray(audio, np.float32)).sort_by_start_time()]


def label(result: dict, turns: list[tuple[float, float, int]]) -> dict:
    """
    Attach speakers to a transcript, marking rather than guessing at overlap.

    `result` is what Transcriber.transcribe returns: parallel `tokens` and
    `timestamps`. Each token is matched against every turn it intersects:

      one speaker   -> attributed
      two or more   -> attributed to the largest intersection AND flagged
                       `overlap`, listing everyone active
      none          -> speaker None, rather than a fabricated guess

    Tokens are matched by greatest INTERSECTION, not by which turn contains
    their start. Token and turn boundaries are cut independently, so
    start-containment mislabels every token that begins while the previous
    speaker is still finishing -- which is most of them at a speaker change.
    """
    tokens = result.get("tokens") or []
    times = result.get("timestamps") or []

    rows = []
    for tok, t in zip(tokens, times):
        mid = t + TOKEN_SEC / 2

        # ATTRIBUTION uses the largest intersection over the token's whole
        # extent -- robust when a token sits mostly inside one turn.
        hits = sorted(((min(t + TOKEN_SEC, end) - max(t, start), spk)
                       for start, end, spk in turns
                       if min(t + TOKEN_SEC, end) - max(t, start) > 0), reverse=True)

        # OVERLAP is decided at the token's MIDPOINT with half-open intervals,
        # deliberately not from those intersections. Two adjacent turns share a
        # boundary instant, so any token straddling a speaker change intersects
        # both and would be flagged as crosstalk when nobody overlapped -- a
        # false positive at every single speaker change. A point cannot lie in
        # two abutting half-open intervals, but it does lie in two genuinely
        # concurrent ones, which is exactly the distinction wanted.
        active = tuple(sorted(spk for start, end, spk in turns if start <= mid < end))

        rows.append((tok, t, hits[0][1] if hits else None,
                     active if len(active) > 1 else ()))

    # Group runs sharing the same speaker AND the same overlap state, so a
    # crosstalk stretch becomes its own line instead of hiding inside a clean one.
    lines: list[dict] = []
    for tok, t, spk, active in rows:
        if lines and lines[-1]["_spk"] == spk and lines[-1]["_act"] == active:
            lines[-1]["_toks"].append(tok)
            lines[-1]["end"] = round(t + TOKEN_SEC, 2)
            continue
        lines.append({"_spk": spk, "_act": active, "_toks": [tok],
                      "start": round(t, 2), "end": round(t + TOKEN_SEC, 2)})

    out = []
    for ln in lines:
        text = "".join(ln.pop("_toks")).replace(SPACE, " ").strip()
        if not text:
            continue
        spk, active = ln.pop("_spk"), ln.pop("_act")
        row = {"start": ln["start"], "end": ln["end"],
               "speaker": None if spk is None else f"Speaker {spk + 1}",
               "text": text}
        if active:
            row["overlap"] = [f"Speaker {s + 1}" for s in active]
            # Say so plainly: the words here are not reliably one person's.
            row["note"] = "crosstalk - attribution uncertain"
        out.append(row)

    speakers = sorted({r["speaker"] for r in out if r["speaker"]})
    crosstalk = round(sum(r["end"] - r["start"] for r in out if r.get("overlap")), 2)

    labelled = dict(result)
    labelled.pop("tokens", None)
    labelled.pop("timestamps", None)
    labelled.update({
        "lines": out,
        "speakers": speakers,
        "num_speakers": len(speakers),
        "crosstalk_sec": crosstalk,
    })

    # Automatic clustering splits one voice when the recording changes
    # character -- an intro clip, a phone-quality stretch. The shape is
    # recognisable, so say so rather than returning a monologue formatted as a
    # panel discussion.
    if len(speakers) > 1:
        share = {}
        for r in out:
            if r["speaker"]:
                share[r["speaker"]] = share.get(r["speaker"], 0.0) + (r["end"] - r["start"])
        total = sum(share.values()) or 1.0
        top = max(share.values()) / total
        if top > 0.8:
            labelled["warning"] = (
                f"one speaker holds {top:.0%} of the speech. This is often a single "
                f"person split by a change in the recording -- re-run with "
                f"num_speakers=1 to check.")
    return labelled
