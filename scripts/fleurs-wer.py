import sys, io, time, re, unicodedata
import numpy as np, pyarrow.parquet as pq, soundfile as sf, sherpa_onnx

def norm(s):
    s = unicodedata.normalize('NFC', s)
    s = re.sub(r'[।॥.,?!;:"\'‘’“”()\[\]]', ' ', s)
    return ' '.join(s.split())

def wer(ref, hyp):
    r, h = norm(ref).split(), norm(hyp).split()
    d = np.zeros((len(r)+1, len(h)+1), dtype=np.int32)
    d[:,0] = np.arange(len(r)+1); d[0,:] = np.arange(len(h)+1)
    for i in range(1, len(r)+1):
        for j in range(1, len(h)+1):
            d[i,j] = min(d[i-1,j]+1, d[i,j-1]+1, d[i-1,j-1] + (r[i-1] != h[j-1]))
    return d[len(r), len(h)], len(r)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
rec = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
    model="model.int8.onnx", tokens="tokens.txt", num_threads=8)
rows = pq.ParquetFile("/tmp/fleurs_hi_test.parquet").read_row_group(0).slice(0, N).to_pylist()
E = W = 0; t0 = time.time(); dur = 0.0
for i, r in enumerate(rows):
    a, sr = sf.read(io.BytesIO(r['audio']['bytes']), dtype='float32')
    if a.ndim > 1: a = a.mean(1)
    dur += len(a)/sr
    s = rec.create_stream(); s.accept_waveform(sr, a); rec.decode_stream(s)
    e, n = wer(r['transcription'], s.result.text); E += e; W += n
    if i == 0:
        print(f"  REF: {r['transcription'][:88]}")
        print(f"  HYP: {s.result.text[:88]}")
el = time.time() - t0
print(f"\n  FLEURS hi_in test, first {N} utterances")
print(f"  WER      : {100*E/W:.1f}%   ({E} errors / {W} words)")
print(f"  audio    : {dur/60:.1f} min")
print(f"  decoded  : {el:.0f}s  ({dur/el:.0f}x realtime, CPU 8 threads)")
