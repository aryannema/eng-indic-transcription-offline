"""
Offline Indic + English speech recognition on AI4Bharat's official ONNX export.

Runs on onnxruntime directly. sherpa-onnx is not used here and is not needed:
its from_nemo_ctc expects one file with vocab_size embedded in the graph
metadata, while AI4Bharat ships the vocabulary as vocab.json beside the graphs.
That is a packaging difference, not a missing capability, so reading the pieces
directly is simpler than rewriting the export to satisfy a wrapper.

What the export contains:

    encoder.onnx        audio_signal[B,80,T] + length  ->  [B,1024,T']
    ctc_decoder.onnx    encoder_output[B,1024,T']      ->  logprobs[B,T',5633]
    vocab.json          22 languages, 257 tokens each
    language_masks.json 22 languages, 5633 bools, exactly 257 True each

One shared CTC head serves all 22 languages. A language is a 257-column slice
of the 5633, selected by its mask -- so adding a language costs nothing and
"which language" is a slicing decision, not a different model.

That slicing is also why Hindi and Urdu cannot be confused. They are the same
acoustic model with different output alphabets; masking to one removes the
other's tokens from the graph's reach entirely, so the wrong script is
unreachable rather than merely unlikely.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

# Indic scripts have no Latin, so English speech inside Indic audio comes out
# transliterated. That is a vocabulary limit, not a bug -- see GUIDANCE.md.
SPACE = "▁"       # SentencePiece word-start marker


class Transcriber:
    """One loaded model, reusable across files. Load once; decode many."""

    def __init__(self, assets: str | Path, language: str = "hi", threads: int = 4,
                 decoder: str = "rnnt", precision: str = "auto"):
        import onnxruntime as ort

        if decoder not in ("rnnt", "ctc"):
            raise ValueError(f"decoder must be 'rnnt' or 'ctc', got {decoder!r}")
        if precision not in ("auto", "fp32", "int8"):
            raise ValueError(f"precision must be 'auto', 'fp32' or 'int8', got {precision!r}")
        self.assets = Path(assets)
        self.language = language
        self.decoder = decoder
        self._threads = threads
        self._rnnt = None

        # int8 graphs sit beside the fp32 ones as <name>.int8.onnx. "auto"
        # prefers int8 when present, because a directory that has it was built
        # deliberately.
        def pick(stem: str) -> Path:
            q = self.assets / f"{stem}.int8.onnx"
            f = self.assets / f"{stem}.onnx"
            if precision == "int8":
                return q
            if precision == "fp32":
                return f
            return q if q.exists() else f

        self._pick = pick
        enc_p = pick("encoder")
        self.precision = "int8" if enc_p.name.endswith(".int8.onnx") else "fp32"
        dec_p = self.assets / "ctc_decoder.onnx"
        needed = [enc_p, self.assets / "vocab.json"]
        if decoder == "ctc":
            needed += [dec_p, self.assets / "language_masks.json"]
        for p in needed:
            if not p.exists():
                raise FileNotFoundError(
                    f"{p.name} not found in {self.assets}. "
                    f"Run: python scripts/fetch_models.py --indic {language}")

        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts = dict(sess_options=so, providers=["CPUExecutionProvider"])
        self._enc = ort.InferenceSession(str(enc_p), **opts)
        self._dec = ort.InferenceSession(str(dec_p), **opts) if dec_p.exists() else None

        vocabs = json.loads((self.assets / "vocab.json").read_text(encoding="utf-8"))
        mask_f = self.assets / "language_masks.json"
        masks = json.loads(mask_f.read_text(encoding="utf-8")) if mask_f.exists() else {}
        if language not in vocabs:
            raise ValueError(f"unknown language {language!r}. "
                             f"available: {', '.join(sorted(vocabs))}")

        self.vocab: list[str] = vocabs[language]
        self._keep = (np.flatnonzero(np.asarray(masks[language], dtype=bool))
                      if language in masks else None)
        if self._keep is not None and len(self._keep) != len(self.vocab):
            raise RuntimeError(
                f"{language}: mask selects {len(self._keep)} columns but vocab has "
                f"{len(self.vocab)} tokens -- assets are mismatched")

        # config.json records BLANK_ID=256, the last of the 257.
        self._blank = len(self.vocab) - 1

        # Frame stride after the encoder's 8x subsampling: 10ms hop * 8.
        self.frame_sec = 0.08

        # config.json RNNT_MAX_SYMBOLS
        self.max_symbols = 10

        # The encoder is FULL-CONTEXT and its positional table is baked to a
        # fixed length at export. Measured: 480s raises outright ("broadcast
        # 1000 by 6000"), and -- far worse -- 240s completes with NO error while
        # returning 264 tokens where 120s of the same audio returned 538. It
        # silently stops emitting. So long input must be split, and the window
        # is kept well under the observed 120s safe point.
        self.max_window_sec = 45.0

    # ---------------------------------------------------------------- features

    def _features(self, audio: np.ndarray) -> np.ndarray:
        """
        NeMo's front end: 80-dim log-mel, 25ms window, 10ms hop, librosa-style
        mel, then per-feature normalisation.

        This is the one step that fails *silently*. Wrong features do not raise
        -- they produce plausible wrong text. kaldi-native-fbank exposes
        is_librosa for exactly this case and is the same implementation sherpa
        calls internally, so the numerics match what the model was trained on.
        Do not substitute a hand-rolled mel filterbank here.
        """
        import kaldi_native_fbank as knf

        o = knf.FbankOptions()
        o.frame_opts.samp_freq = 16000
        o.frame_opts.frame_length_ms = 25.0
        o.frame_opts.frame_shift_ms = 10.0
        o.frame_opts.dither = 0.0
        o.frame_opts.preemph_coeff = 0.0      # measured cleaner than 0.97
        o.frame_opts.remove_dc_offset = False
        o.frame_opts.window_type = "hann"
        o.frame_opts.snip_edges = False
        o.mel_opts.num_bins = 80
        o.mel_opts.low_freq = 0.0
        o.mel_opts.high_freq = 0.0           # 0 means Nyquist
        o.mel_opts.is_librosa = True
        o.use_energy = False

        f = knf.OnlineFbank(o)
        f.accept_waveform(16000, audio.tolist())
        f.input_finished()
        if f.num_frames_ready == 0:
            raise ValueError("audio too short to produce a single frame")
        m = np.stack([f.get_frame(i) for i in range(f.num_frames_ready)]).T  # [80,T]

        # NeMo normalize='per_feature': per mel bin, over this utterance only.
        m = (m - m.mean(1, keepdims=True)) / (m.std(1, keepdims=True) + 1e-5)
        return m[None].astype(np.float32)

    # ----------------------------------------------------------------- decode

    def transcribe(self, audio: np.ndarray) -> dict:
        """
        `audio` must be 16 kHz mono float32. The [-1, 1] range is conventional
        but not load-bearing here: per-feature normalisation divides each mel
        bin by its own standard deviation, so a constant amplitude factor
        cancels. Measured -- int16-scaled input decodes identically.

        The sample RATE does matter and is not checked here, because a bare
        array carries no rate. Feed 16 kHz; `read_wav16k` enforces it for files.

        Audio longer than `max_window_sec` is split automatically. This is not
        an optimisation -- a single long pass silently truncates.
        """
        audio = np.asarray(audio, dtype=np.float32)
        if len(audio) / 16000 <= self.max_window_sec:
            return self._transcribe_one(audio, 0.0)

        out = {"text": "", "tokens": [], "timestamps": [], "language": self.language,
               "duration_sec": round(len(audio) / 16000, 2), "windows": 0}
        texts = []
        for start, seg in self._windows(audio):
            r = self._transcribe_one(seg, start)
            texts.append(r["text"])
            out["tokens"] += r["tokens"]
            out["timestamps"] += r["timestamps"]
            out["windows"] += 1
        out["text"] = " ".join(t for t in texts if t).strip()
        return out

    def _windows(self, audio: np.ndarray):
        """
        Split into windows, cutting at the quietest point near each boundary.

        A fixed cut lands mid-word roughly whenever it feels like it; searching
        a few seconds either side for the lowest-energy 100ms costs almost
        nothing and usually finds a real pause. No VAD model needed.
        """
        R = 16000
        win = int(self.max_window_sec * R)
        slack = int(3.0 * R)          # how far to hunt for a quiet spot
        probe = int(0.1 * R)

        i, n = 0, len(audio)
        while i < n:
            if i + win >= n:
                yield i / R, audio[i:]
                return
            lo = max(i + win - slack, i + win // 2)
            hi = min(i + win + slack, n - probe)
            best, best_e = i + win, None
            for c in range(lo, hi, probe):
                e = float(np.abs(audio[c:c + probe]).mean())
                if best_e is None or e < best_e:
                    best, best_e = c, e
            yield i / R, audio[i:best]
            i = best

    def _transcribe_one(self, audio: np.ndarray, offset: float) -> dict:
        feats = self._features(audio)
        enc_out, _ = self._enc.run(
            None, {"audio_signal": feats,
                   "length": np.array([feats.shape[2]], dtype=np.int64)})

        if self.decoder == "rnnt":
            tokens, times = self._decode_rnnt(enc_out)
        else:
            tokens, times = self._decode_ctc(enc_out)

        if offset:
            times = [round(t + offset, 3) for t in times]
        return {
            "text": "".join(tokens).replace(SPACE, " ").strip(),
            "tokens": tokens,
            "timestamps": times,
            "language": self.language,
            "duration_sec": round(len(audio) / 16000, 2),
        }

    def _decode_ctc(self, enc_out: np.ndarray) -> tuple[list[str], list[float]]:
        logprobs = self._dec.run(None, {"encoder_output": enc_out})[0]

        # Slice to this language's 257 columns before argmax. Doing it here and
        # not after is the whole guarantee: other scripts are never candidates.
        ids = logprobs[0][:, self._keep].argmax(-1)

        # Greedy CTC: collapse runs, drop blank. Keep the frame index of each
        # surviving token so callers can align against speaker turns.
        tokens: list[str] = []
        times: list[float] = []
        prev = -1
        for frame, i in enumerate(ids):
            i = int(i)
            if i != prev and i != self._blank:
                tokens.append(self.vocab[i])
                times.append(round(frame * self.frame_sec, 3))
            prev = i
        return tokens, times

    # --------------------------------------------------------------- RNN-T

    def _load_rnnt(self):
        """
        The transducer path, loaded on demand.

        The checkpoint is hybrid CTC + RNN-T and ships BOTH decoders. RNN-T is
        markedly more accurate because the prediction network carries state
        between frames, so the joint sees the previous token -- an implicit
        language model, which is exactly what CTC lacks. Measured on 45s of
        Hindi: CTC gave "्रेश पच्चीसार फ को न ज दी तो म सव आपसे", RNN-T gave
        "फ्रेशर पच्ची फ्रेशर्स को अपने दी तो मेरा सवाल आपसे".

        It is also nearly free: the encoder pass is shared and dominates, and
        the greedy loop added 0.13s over 563 frames.

        Note this path uses the PER-LANGUAGE joint_post_net head directly, so
        no mask is involved -- choosing the head is what confines the output to
        one language, where CTC masks a shared 5633-way head.
        """
        if self._rnnt is not None:
            return self._rnnt
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = self._threads
        need = {"joint_enc": self._pick("joint_enc"), "pred": self._pick("rnnt_decoder"),
                "joint_pred": self._pick("joint_pred"),
                "pre": self.assets / "joint_pre_net.onnx",
                "post": self.assets / f"joint_post_net_{self.language}.onnx"}
        parts = {}
        for k, f in need.items():
            fn = f.name
            if not f.exists():
                raise FileNotFoundError(
                    f"{fn} missing — RNN-T needs the full export. "
                    f"Use decoder='ctc' or re-fetch the model.")
            parts[k] = ort.InferenceSession(
                str(f), sess_options=so, providers=["CPUExecutionProvider"])
        parts["pred_in"] = [i.name for i in parts["pred"].get_inputs()]
        self._rnnt = parts
        return parts

    def _pred_step(self, r, token: int, state):
        """One step of the prediction LSTM. `state` is (h, c), each [2, 1, 640]."""
        h, c = state if state is not None else (
            np.zeros((2, 1, 640), np.float32), np.zeros((2, 1, 640), np.float32))
        n = r["pred_in"]
        out = r["pred"].run(None, {n[0]: np.array([[token]], np.int32),
                                  n[1]: np.array([1], np.int32),
                                  n[2]: h, n[3]: c})
        return out[0], (out[2], out[3])

    def _decode_rnnt(self, enc_out: np.ndarray) -> tuple[list[str], list[float]]:
        r = self._load_rnnt()
        enc_p = r["joint_enc"].run(
            None, {"input": np.ascontiguousarray(enc_out.transpose(0, 2, 1))})[0]

        tokens: list[str] = []
        times: list[float] = []
        pout, state = self._pred_step(r, self._blank, None)   # SOS == BLANK == 256
        pp = r["joint_pred"].run(
            None, {"input": np.ascontiguousarray(pout.transpose(0, 2, 1))})[0]

        for t in range(enc_p.shape[1]):
            # RNNT_MAX_SYMBOLS caps emissions per frame; without it a confident
            # model can loop forever on one frame.
            for _ in range(self.max_symbols):
                z = r["pre"].run(None, {"input": enc_p[:, t:t + 1, :] + pp[:, :1, :]})[0]
                k = int(r["post"].run(None, {"input": z})[0][0, 0].argmax())
                if k == self._blank:
                    break
                tokens.append(self.vocab[k])
                times.append(round(t * self.frame_sec, 3))
                pout, state = self._pred_step(r, k, state)
                pp = r["joint_pred"].run(
                    None, {"input": np.ascontiguousarray(pout.transpose(0, 2, 1))})[0]
        return tokens, times

    def transcribe_wav(self, path: str | Path) -> dict:
        return self.transcribe(read_wav16k(path))

    @staticmethod
    def languages(assets: str | Path) -> list[str]:
        p = Path(assets) / "vocab.json"
        return sorted(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else []


def read_wav16k(path: str | Path) -> np.ndarray:
    """Read a 16 kHz mono WAV as float32. Raises rather than resampling badly."""
    with wave.open(str(path)) as wf:
        if wf.getnchannels() != 1 or wf.getframerate() != 16000:
            raise ValueError(
                f"{Path(path).name} is {wf.getnchannels()}ch @ {wf.getframerate()}Hz; "
                f"need 16000 Hz mono. Convert: "
                f"ffmpeg -i in -vn -ac 1 -ar 16000 out.wav")
        if wf.getsampwidth() != 2:
            raise ValueError(f"need 16-bit PCM, got {wf.getsampwidth()*8}-bit")
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0
