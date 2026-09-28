#!/usr/bin/env python3
"""
Check whether this machine can run the project, and say what to do if not.

Run this before opening an issue. Most "it doesn't work" reports are one of
four things: the wrong Python, a missing wheel, no Hugging Face token, or audio
that isn't 16 kHz mono.

    python scripts/doctor.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, WARN, BAD = "ok  ", "warn", "FAIL"
issues: list[str] = []


def line(state: str, what: str, detail: str = "") -> None:
    print(f"  [{state}] {what:<26} {detail}")


def cmd(*args) -> str | None:
    exe = shutil.which(args[0])
    if not exe:
        return None
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else ""
    except Exception:
        return None


print("\n  Python\n")
v = sys.version_info
if v[:2] == (3, 12):
    line(OK, "python", f"{v.major}.{v.minor}.{v.micro}")
elif (3, 10) <= v[:2] <= (3, 12):
    line(OK, "python", f"{v.major}.{v.minor} — fine for recognition")
else:
    line(WARN, "python", f"{v.major}.{v.minor} — sherpa-onnx wheels may not exist yet")
    issues.append("Python 3.12 is the safe choice; sherpa-onnx (speaker labels) lags new releases.")

if sys.prefix != sys.base_prefix or os.environ.get("CONDA_PREFIX"):
    line(OK, "virtual env", Path(sys.prefix).name)
else:
    line(WARN, "virtual env", "none — installing globally often fails")
    issues.append("Create an environment: uv venv --python 3.12 .venv")

print("\n  Recognition — required\n")
for mod, why in (("onnxruntime", "runs the model"),
                 ("kaldi_native_fbank", "log-mel features"),
                 ("numpy", "arrays")):
    if importlib.util.find_spec(mod):
        try:
            m = __import__(mod)
            line(OK, mod, getattr(m, "__version__", ""))
        except Exception as e:
            line(BAD, mod, f"installed but will not import: {e}")
            issues.append(f"{mod} is broken — reinstall it.")
    else:
        line(BAD, mod, "missing")
        issues.append(f"{mod} missing: uv pip install {mod.replace('_', '-')}")

if importlib.util.find_spec("kaldi_native_fbank") is None:
    issues.append("kaldi-native-fbank is NOT interchangeable. A different mel front end "
                  "does not error — it quietly produces worse text.")

print("\n  Optional\n")
for mod, why in (("sherpa_onnx", "speaker labels"),
                 ("yt_dlp", "transcribe from a URL"),
                 ("mcp", "agent tools")):
    spec = importlib.util.find_spec(mod)
    line(OK if spec else WARN, mod, why if spec else f"missing — {why} unavailable")

print("\n  Tools\n")
ff = cmd("ffmpeg", "-version")
line(OK if ff else WARN, "ffmpeg", (ff or "missing — non-WAV input cannot be converted")[:52])
if not ff:
    issues.append("Without ffmpeg only 16 kHz mono WAV can be read.")
for tool, args in (("node", ("node", "--version")), ("pnpm", ("pnpm", "--version"))):
    out = cmd(*args)
    line(OK if out else WARN, tool, out or "missing — only needed for the web UI")

print("\n  Model access\n")
tok = next((os.environ[k] for k in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN")
            if os.environ.get(k)), None)
if not tok:
    for c in (Path.home() / ".cache/huggingface/token", Path.home() / ".huggingface/token"):
        if c.is_file() and c.read_text().strip():
            tok = "file"
            break
if tok:
    line(OK, "hugging face token", "found (not shown)")
else:
    line(WARN, "hugging face token", "none — the model is gated and needs one")
    issues.append("The model is MIT but gated. Accept at "
                  "https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual "
                  "then export HF_TOKEN=...")

found = None
for d in (ROOT / "models/asr/indic", ROOT / "models/asr/indic-int8"):
    if (d / "encoder.onnx").exists():
        found = (d, "fp32")
    elif (d / "encoder.int8.onnx").exists():
        found = (d, "int8")
if found:
    d, prec = found
    size = sum(p.stat().st_size for p in d.iterdir() if p.is_file()) / 1e6
    line(OK, "model", f"{prec}, {size:.0f} MB at {d.relative_to(ROOT)}")
else:
    line(WARN, "model", "not downloaded — python scripts/fetch_models.py --indic hi")

print("\n  Memory\n")
try:
    total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    if total >= 4:
        line(OK, "RAM", f"{total:.1f} GB")
    else:
        line(WARN, "RAM", f"{total:.1f} GB — fp32 needs ~2.7 GB resident")
        issues.append(f"{total:.1f} GB is tight for fp32. Build the int8 model "
                      "(scripts/quantize.py): 1.29 GB resident.")
except Exception:
    line(WARN, "RAM", "could not determine")

print()
if issues:
    print(f"  {len(issues)} thing(s) to fix:\n")
    for i, t in enumerate(issues, 1):
        print(f"    {i}. {t}")
    print()
    sys.exit(1)
print("  Everything needed is present.\n")
