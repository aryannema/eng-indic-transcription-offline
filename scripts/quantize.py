#!/usr/bin/env python3
"""
Quantise the fp32 export to int8.

Quantisation by Aryan Nema. The model itself is AI4Bharat's (MIT) and is not
modified in any other way — this only changes the numeric precision of the
weights.

Result, measured on 8 CPU threads:

    fp32   2.74 GB resident, loads in 1.9 s
    int8   1.29 GB resident, loads in 1.5 s      53% less memory, and faster

Why the output is not committed: 679 MB, well past GitHub's 100 MB per-file
limit. Build it yourself with this script; it takes under a minute.

    python scripts/quantize.py --assets <fp32 dir> --out <dir>
    python scripts/transcribe.py file.wav --models <out dir>

A caveat worth reading before trusting it is in GUIDANCE.md: int8 output
DIFFERS from fp32, in both directions, and without a reference transcript we
cannot say which is more accurate.
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

# Quantising these four covers essentially all the weight: the encoder alone is
# 2.1 GB of a 2.2 GB footprint. joint_pre_net is 2.7 KB and the language heads
# are 0.7 MB each — quantising them would save nothing measurable and adds a
# place for things to go wrong.
TARGETS = ["encoder", "rnnt_decoder", "joint_enc", "joint_pred"]
COPY_AS_IS = ["joint_pre_net.onnx", "vocab.json", "language_masks.json", "config.json"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", required=True, help="fp32 export directory")
    ap.add_argument("--out", required=True, help="where to write the int8 build")
    ap.add_argument("--languages", default="all",
                    help="comma-separated codes, or 'all' (heads are 0.7 MB each)")
    args = ap.parse_args()

    src, dst = Path(args.assets).expanduser(), Path(args.out).expanduser()
    if not (src / "encoder.onnx").exists():
        print(f"no encoder.onnx in {src}", file=sys.stderr)
        return 1
    dst.mkdir(parents=True, exist_ok=True)

    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        print("pip install onnxruntime", file=sys.stderr)
        return 1

    total_before = total_after = 0
    for stem in TARGETS:
        f = src / f"{stem}.onnx"
        if not f.exists():
            print(f"  {stem:<18} missing, skipped")
            continue
        out = dst / f"{stem}.int8.onnx"
        # encoder.onnx is a small skeleton pointing at external tensor files, so
        # its own size is meaningless — measure the directory delta instead.
        t0 = time.time()
        try:
            # NOTE: quantize_dynamic writes a temporary <name>-inferred.onnx
            # NEXT TO ITS INPUT. If the source tree is read-only that write is
            # denied and the failure surfaces as FileNotFoundError on the temp
            # file, not PermissionError — confusing enough to be worth saying.
            quantize_dynamic(str(f), str(out), weight_type=QuantType.QInt8)
        except FileNotFoundError as e:
            print(f"  {stem:<18} FAILED: {e}")
            print("     the source directory must be WRITABLE — quantize_dynamic")
            print("     writes a temp file beside its input. Copy it first, or")
            print("     point --assets at a writable copy.")
            return 1
        after = out.stat().st_size
        total_after += after
        print(f"  {stem:<18} -> {after/1e6:8.1f} MB  ({time.time()-t0:.0f}s)")

    for name in COPY_AS_IS:
        if (src / name).exists():
            shutil.copy2(src / name, dst / name)

    want = None if args.languages == "all" else set(args.languages.split(","))
    heads = 0
    for f in sorted(src.glob("joint_post_net_*.onnx")):
        code = f.stem.replace("joint_post_net_", "")
        if want and code not in want:
            continue
        shutil.copy2(f, dst / f.name)
        heads += 1

    size = sum(p.stat().st_size for p in dst.iterdir() if p.is_file())
    print(f"\n  {heads} language heads")
    print(f"  total: {size/1e6:.0f} MB  ->  {dst}")
    print("\n  Verify before relying on it — quantisation changes the output:")
    print(f"    python scripts/transcribe.py sample.wav --models {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
