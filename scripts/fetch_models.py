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


def hf_token() -> str | None:
    """
    Find a Hugging Face token, without ever printing it.

    Needed because ai4bharat/indic-conformer-600m-multilingual is `gated: auto`.
    The licence is MIT and approval is automatic, but the files still sit behind
    an account: you click once to accept, and downloads then need a token. The
    repo's file LISTING is public, which is why enumeration works and fetching
    does not -- a confusing failure if you do not know to look for it.
    """
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        v = os.environ.get(var)
        if v and v.strip():
            return v.strip()
    # the location `huggingface-cli login` writes to
    for c in (Path.home() / ".cache/huggingface/token",
              Path.home() / ".huggingface/token"):
        try:
            if c.is_file():
                v = c.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except OSError:
            pass
    return None


GATE_HELP = """
    This model is gated (licence is MIT; approval is automatic).

      1. Sign in at https://huggingface.co and open
         https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
      2. Click "Agree and access repository" -- granted immediately
      3. Create a READ token at https://huggingface.co/settings/tokens
      4. export HF_TOKEN=... , or run: huggingface-cli login

    The token is read from the environment and never written or printed."""


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
        headers = {"User-Agent": "indic-transcribe-installer"}
        tok = hf_token()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        req = urllib.request.Request(url, headers=headers)
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
            print(f"      HTTP {e.code} — cannot read {repo}")
            print(GATE_HELP if not hf_token() else
                  "      A token was found but was refused. Has the repo's\n"
                  "      licence been accepted with THIS account, and is the\n"
                  "      token a READ token that has not expired?")
        return False
    except Exception as e:
        print(f"\r    {filename:<52} {type(e).__name__}: {e}")
        return False


LANGS = {
    "as": "Assamese", "bn": "Bengali", "brx": "Bodo", "doi": "Dogri",
    "gu": "Gujarati", "hi": "Hindi", "kn": "Kannada", "kok": "Konkani",
    "ks": "Kashmiri", "mai": "Maithili", "ml": "Malayalam", "mni": "Manipuri",
    "mr": "Marathi", "ne": "Nepali", "or": "Odia", "pa": "Punjabi",
    "sa": "Sanskrit", "sat": "Santali", "sd": "Sindhi", "ta": "Tamil",
    "te": "Telugu", "ur": "Urdu",
}


def list_tree(repo: str, sha: str, path: str) -> list:
    """
    Enumerate a directory in a HF repo at a pinned revision.

    The file list is not hard-coded because encoder.onnx is a 2.8 MB skeleton
    that references 368 external tensor files BY NAME. Naming them here would be
    unmaintainable, and would break silently if upstream ever re-sharded the
    weights -- you would get a model that loads and produces nonsense.
    """
    url = f"{HF}/api/models/{repo}/tree/{sha}/{path}?recursive=1"
    headers = {"User-Agent": "indic-transcribe-installer"}
    tok = hf_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        tree = json.loads(r.read().decode("utf-8"))
    return [t for t in tree if t.get("type") == "file"]


def fetch_tree(entry: dict, models_dir: Path, lang: str) -> bool:
    """
    Fetch the official export: every file in the tree except the 21 language
    heads we do not need.

    This is a 2.4 GB download and the weights are fp32. It is one encoder shared
    by all 22 languages, so a second language later costs 0.6 MB, not another
    2.4 GB.
    """
    dest = models_dir / entry["dest"]
    print(f"\n  {entry['label']}")
    print(f"    {entry['attribution']}")
    print(f"    licence {entry['license']} · pinned {entry['sha'][:12]} · {entry['size_human']}")

    if not hf_token():
        print("    NOTE: no Hugging Face token found in the environment.")
        print(GATE_HELP)
        print()

    try:
        files = list_tree(entry["repo"], entry["sha"], entry["tree"])
    except Exception as e:
        print(f"    could not list {entry['repo']}: {e}")
        return False

    keep = []
    for f in files:
        name = f["path"].split("/")[-1]
        # Other languages' heads are pure waste -- skip them, keep ours.
        if name.startswith("joint_post_net_") and name != f"joint_post_net_{lang}.onnx":
            continue
        keep.append(f)

    total = sum(f.get("size") or (f.get("lfs") or {}).get("size") or 0 for f in keep)
    print(f"    {len(keep)} files, {human(total)} — this takes a while\n")

    ok, done = True, 0
    for i, f in enumerate(keep, 1):
        name = f["path"].split("/")[-1]
        if (dest / name).exists():
            done += 1
            continue
        if not download(entry["repo"], entry["sha"], f["path"], dest / name):
            ok = False
        if i % 25 == 0 or i == len(keep):
            print(f"    … {i}/{len(keep)}")

    if ok:
        (dest / "language.json").write_text(
            json.dumps({"language": lang, "name": LANGS.get(lang, lang),
                        "repo": entry["repo"], "sha": entry["sha"]}, indent=2),
            encoding="utf-8")
        print(f"\n    ready: {dest}  ({LANGS.get(lang, lang)})")
        if done:
            print(f"    ({done} files already present, skipped)")
    return ok


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
        print("\n  Indic languages (choose ONE at install):\n")
        for code, name in sorted(LANGS.items(), key=lambda kv: kv[1]):
            print(f"    {code:<6} {name}")
        print("\n  Hindi and Urdu are mutually exclusive by design: the same")
        print("  acoustic model writes two different scripts, and the choice is")
        print("  enforced by a mask rather than guessed.")
        print()
        return 0

    if not (args.english or args.indic):
        ap.error("pick at least --english or --indic LANG (see --list)")

    if args.indic:
        langs = LANGS
        if args.indic not in langs:
            valid = " ".join(k for k in langs if not k.startswith("_"))
            print(f"  unknown language '{args.indic}'. Available: {valid}")
            return 2

    print(f"  models -> {models_dir}")
    failed = []

    if args.english and not fetch(models["asr-en"], models_dir):
        failed.append("asr-en")

    if args.indic:
        # fetch_tree writes language.json beside the weights on success. The
        # runtime reads the choice from there instead of guessing -- which is
        # the whole point of asking at install: the same acoustic model writes
        # Devanagari or Arabic script depending on the mask, and left to choose
        # it picks wrong silently.
        if not fetch_tree(models["indic-conformer-600m"], models_dir, args.indic):
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
