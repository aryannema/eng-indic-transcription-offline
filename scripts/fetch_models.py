#!/usr/bin/env python3
"""
fetch_models.py — download only the weights this install actually needs.

Weights are never committed to the repo. They come from Hugging Face at install
time, pinned to a commit SHA so that a user installing today and one installing
next month get byte-identical models. A floating "main" pointer means a bug
report cannot be tied to a known set of weights.

Downloads are resumable and skip files already present with the right size, so
re-running after a dropped connection costs nothing.

Usage:
    fetch_models.py --english
    fetch_models.py --english --indic hi
    fetch_models.py --english --indic hi --cleanup
    fetch_models.py --list
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HF = "https://huggingface.co"
ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "models.json"


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download(repo: str, sha: str, filename: str, dest: Path) -> bool:
    """
    Resolve a file at a pinned revision and stream it to disk.

    Returns False rather than raising so one missing file does not abandon a
    half-finished install — the caller reports what failed and the user can
    re-run, keeping everything already fetched.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{HF}/{repo}/resolve/{sha}/{filename}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vigyanvani-installer"})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get("Content-Length", 0))

            # Skip a file that is already complete. Size is a weak check, but the
            # SHA pin means the content cannot have changed under us — only a
            # truncated download is plausible, and that changes the size.
            if dest.exists() and total and dest.stat().st_size == total:
                print(f"    {dest.name:<52} {human(total):>9}  already there")
                return True

            tmp = dest.with_suffix(dest.suffix + ".part")
            got = 0
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        pct = 100 * got / total
                        print(f"\r    {dest.name:<52} {human(got):>9} {pct:5.1f}%",
                              end="", flush=True)

            tmp.replace(dest)
            print(f"\r    {dest.name:<52} {human(got):>9}  done      ")
            return True

    except urllib.error.HTTPError as e:
        print(f"\r    {filename:<52} HTTP {e.code}")
        if e.code in (401, 403):
            print(f"      gated repo — accept the terms at {HF}/{repo}")
        return False
    except Exception as e:
        print(f"\r    {filename:<52} {type(e).__name__}: {e}")
        return False


def fetch(entry: dict, models_dir: Path) -> bool:
    print(f"\n  {entry['label']}  ({entry['license']})")
    dest = models_dir / entry["dest"]
    ok = True
    for fn in entry["files"]:
        # Some repos nest files (assets/foo.onnx); flatten to the leaf name so
        # the runtime finds them at a predictable path.
        if not download(entry["repo"], entry["sha"], fn, dest / Path(fn).name):
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--english", action="store_true", help="English ASR (73 MB)")
    ap.add_argument("--indic", metavar="LANG",
                    help="Indic ASR + language, e.g. hi. One language only: "
                         "Hindi and Urdu are mutually exclusive by design.")
    ap.add_argument("--cleanup", action="store_true",
                    help="Filler removal and punctuation LLM (397 MB, optional)")
    ap.add_argument("--models-dir", default=None)
    ap.add_argument("--list", action="store_true", help="show what is available")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    models = manifest["models"]
    models_dir = Path(args.models_dir) if args.models_dir else ROOT / "models"

    if args.list:
        print("\n  Available:\n")
        for key, m in models.items():
            if m.get("bundled_with_sherpa"):
                continue
            print(f"    {key:<24} {m['size_mb']:>5} MB   {m['license']:<12} {m['label']}")
        langs = models["indic-conformer-int8"]["languages"]
        print("\n  Indic languages (choose ONE):\n")
        for code, name in langs.items():
            if not code.startswith("_"):
                print(f"    {code:<6} {name}")
        print()
        return 0

    if not (args.english or args.indic):
        ap.error("pick at least --english or --indic LANG (see --list)")

    if args.indic:
        langs = models["indic-conformer-int8"]["languages"]
        if args.indic not in langs:
            valid = " ".join(k for k in langs if not k.startswith("_"))
            print(f"  unknown language '{args.indic}'. Available: {valid}")
            return 2

    print(f"  models -> {models_dir}")
    failed = []

    if args.english and not fetch(models["asr-en"], models_dir):
        failed.append("asr-en")

    if args.indic:
        if fetch(models["indic-conformer-int8"], models_dir):
            # Record the chosen language beside the weights. The runtime reads
            # this instead of guessing, which is the whole point of asking at
            # onboarding: Hindi and Urdu are near-identical acoustically and a
            # model made to choose writes the wrong script silently.
            cfg = models_dir / models["indic-conformer-int8"]["dest"] / "language.json"
            cfg.write_text(json.dumps({"language": args.indic}, indent=2), encoding="utf-8")
            print(f"    language locked to '{args.indic}' in {cfg.name}")
        else:
            failed.append("indic")

    if args.cleanup and not fetch(models["cleanup-llm"], models_dir):
        failed.append("cleanup-llm")

    if failed:
        print(f"\n  INCOMPLETE — failed: {', '.join(failed)}")
        print("  Re-run to resume; everything already downloaded is kept.")
        return 1

    total = sum(f.stat().st_size for f in models_dir.rglob("*") if f.is_file())
    print(f"\n  Done. {human(total)} in {models_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
