"""Download the evaluation corpus and verify every file against its recorded SHA-256.

Uses only the standard library:   python data/evaluation/fetch_corpus.py

A hash mismatch is an ERROR on purpose. If a source changes, the labeled questions (which point
at specific pages) may no longer be correct, and evaluation results would silently shift.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CORPUS = HERE / "corpus"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads((HERE / "corpus.manifest.json").read_text())
    CORPUS.mkdir(exist_ok=True)
    problems = 0
    for doc in manifest["documents"]:
        target = CORPUS / doc["file"]
        if not target.exists():
            print(f"downloading {doc['id']} ...")
            request = urllib.request.Request(doc["url"], headers={"User-Agent": "Mozilla/5.0 (SourceMind evaluation corpus fetch)"})
            with urllib.request.urlopen(request, timeout=120) as response:
                target.write_bytes(response.read())
        actual = sha256(target)
        if actual == doc["sha256"]:
            print(f"ok       {doc['id']}")
        else:
            problems += 1
            print(f"MISMATCH {doc['id']}: expected {doc['sha256'][:16]}..., got {actual[:16]}...")
            print("         The source changed. Do not use these results with the existing questions; "
                  "re-check the labeled pages and update corpus.manifest.json deliberately.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
