"""Plant encrypted notes across many topics so any demo search can reach the full chain.

    python scripts/plant_many.py            # plant any queries not yet recorded
    python scripts/plant_many.py --replant   # also overwrite recorded plants in place

For each query below, the top CLIP match that isn't already planted gets a
Vigenère-encrypted (key TERRAPIN), base64-encoded note hidden in its LSBs via
core.stego.embed — exactly like plant_demo_case.py: the image is re-saved as
PNG, the original JPEG removed, and data/embeddings_index.json repointed at the
new filename. All other images stay clean, so "detected when present, honest
when absent" still holds.

data/demo_case.json becomes a list of {filename, query, key, ciphertext, plaintext}.
The old single-object shape written by plant_demo_case.py is read and carried over.

Safe to re-run: queries already recorded are re-verified, not planted again
(unless --replant, which re-embeds them into the same files).
Exits non-zero if any planted image fails extract → crack verification.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import crypto, stego  # noqa: E402
from core.clip_search import DATA_DIR, IMAGE_DIR, INDEX_PATH, search  # noqa: E402
from plant_messages import MESSAGES  # noqa: E402

KEY = "TERRAPIN"
CASE_PATH = DATA_DIR / "demo_case.json"

# Plaintexts live in plant_messages.py (~350-400 letters each, i.e. ~45+ per position
# of the 8-letter key — enough for per-column frequency analysis to recover the key).
QUERIES = ["shoes", "a laptop on a desk", "a dog", "mountains", "a car", "a person walking",
           "stairs", "a forest", "a beach", "a building", "food", "a phone"]
PLANTS: list[tuple[str, str]] = [(q, MESSAGES[q]) for q in QUERIES]


def load_cases() -> list[dict]:
    """Read demo_case.json in either shape and normalise to the list format."""
    if not CASE_PATH.exists():
        return []
    doc = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    raw = doc if isinstance(doc, list) else [doc]  # old shape: one object with "image"
    return [{"filename": c.get("filename") or c.get("image"), "query": c.get("query"),
             "key": c.get("key", KEY), "ciphertext": c["ciphertext"], "plaintext": c["plaintext"]}
            for c in raw]


def encrypt(plaintext: str) -> str:
    return base64.b64encode(crypto.vigenere_encrypt(plaintext, KEY).encode()).decode()


def plant(filename: str, ciphertext: str) -> str:
    """Hide ciphertext in the image, re-save as PNG, repoint the index. Returns the new filename."""
    src = IMAGE_DIR / filename
    png = stego.embed(src.read_bytes(), ciphertext.encode())
    dst = src.with_suffix(".png")
    dst.write_bytes(png)
    if dst != src:
        src.unlink()

    doc = json.loads(INDEX_PATH.read_text())
    for item in doc["items"]:
        if item["filename"] == filename:
            item["filename"] = dst.name
    INDEX_PATH.write_text(json.dumps(doc, indent=1))
    search.load_cache()  # keep the in-memory index in sync for the next query
    return dst.name


def verify(case: dict) -> tuple[bool, str]:
    got = stego.extract((IMAGE_DIR / case["filename"]).read_bytes())
    best = crypto.crack(got["recovered"])["best"] if got["recovered"] else None
    ok = (got["recovered"] == case["ciphertext"].encode() and best is not None
          and best["key"] == case["key"] and best["plaintext"] == case["plaintext"])
    return ok, (best["plaintext"] if best else "<nothing extracted>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replant", action="store_true",
                    help="re-embed queries already in demo_case.json into the same files (same query -> filename)")
    args = ap.parse_args()

    if not search.load_cache():
        sys.exit("Build the search index first: python scripts/build_embeddings.py")

    cases = load_cases()
    planted = {c["filename"] for c in cases}
    done_queries = {c["query"] for c in cases if c["query"]}

    for query, plaintext in PLANTS:
        if query in done_queries:
            if not args.replant:
                print(f"  = {query!r}: already planted, re-verifying")
                continue
            case = next(c for c in cases if c["query"] == query)
            case.update(key=KEY, plaintext=plaintext, ciphertext=encrypt(plaintext))
            plant(case["filename"], case["ciphertext"])  # same file, so the index is unchanged
            print(f"  ~ {query!r}: re-planted into {case['filename']}")
            continue
        matches = search.query_text(query, 25)
        pick = next((m for m in matches if m["filename"] not in planted
                     and Path(m["filename"]).stem + ".png" not in planted), None)
        if pick is None:
            sys.exit(f"No unplanted image among the top 25 for {query!r}")
        ciphertext = encrypt(plaintext)
        new_name = plant(pick["filename"], ciphertext)
        cases.append({"filename": new_name, "query": query, "key": KEY,
                      "ciphertext": ciphertext, "plaintext": plaintext})
        planted.add(new_name)
        print(f"  + {query!r}: planted into {new_name} (search rank {pick['rank']})")

    CASE_PATH.write_text(json.dumps(cases, indent=2), encoding="utf-8")

    print("\nVerification (stego.extract -> crypto.crack):")
    failures = 0
    for c in cases:
        ok, text = verify(c)
        failures += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {c['filename']:20} {text[:70]}{'…' if len(text) > 70 else ''}")

    print(f"\n{'Query':22} Planted file")
    print(f"{'-' * 22} {'-' * 20}")
    for c in cases:
        print(f"{(c['query'] or '(legacy --target)'):22} {c['filename']}")

    total = len(list(IMAGE_DIR.glob('*.*')))
    print(f"\n{len(cases)} planted, {total - len(cases)} clean images left untouched.")
    if failures:
        sys.exit(f"\n!! {failures} image(s) FAILED verification — do not demo until fixed.")
    print("All planted images verified ✔")


if __name__ == "__main__":
    main()
