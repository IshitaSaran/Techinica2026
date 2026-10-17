"""Stage the 90-second demo: one image in the evidence set carries an encrypted note.

    python scripts/plant_demo_case.py --query "a laptop on a desk"
    python scripts/plant_demo_case.py --target evidence_0042.jpg

Pipeline: plaintext --Vigenère(key)--> --base64--> hidden in the image's LSBs
via core.stego.embed (requires backend/core/stego.py). The target is rewritten
as PNG (JPEG would destroy the hidden bits) and the search index is updated to
point at the new filename. An answer key goes to data/demo_case.json.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import crypto  # noqa: E402
from core.clip_search import DATA_DIR, IMAGE_DIR, INDEX_PATH, search  # noqa: E402

DEFAULT_MESSAGE = (
    "Meet at the north dock warehouse at midnight on Friday. The package is under the third "
    "pallet near the loading door. Bring the key and do not tell anyone about this drop. "
    "If the lights are on, wait in the car until you see the signal from the roof."
)


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--target", help="filename inside data/sample_images")
    g.add_argument("--query", help="pick the top CLIP match for this description")
    ap.add_argument("--message", default=DEFAULT_MESSAGE)
    ap.add_argument("--key", default="TERRAPIN")
    args = ap.parse_args()

    try:
        from core import stego
    except ImportError:
        sys.exit("core/stego.py is not installed yet — add it, then re-run this script.")

    if not search.load_cache():
        sys.exit("Build the search index first: python scripts/build_embeddings.py")

    target = args.target or search.query_text(args.query, 1)[0]["filename"]
    src = IMAGE_DIR / target
    if not src.exists():
        sys.exit(f"{src} not found")

    ciphertext = base64.b64encode(crypto.vigenere_encrypt(args.message, args.key).encode()).decode()
    png = stego.embed(src.read_bytes(), ciphertext.encode())
    dst = src.with_suffix(".png")
    dst.write_bytes(png)
    if dst != src:
        src.unlink()

    # Point the cached index at the new filename (pixels changed by ±1, embedding is unaffected).
    doc = json.loads(INDEX_PATH.read_text())
    for item in doc["items"]:
        if item["filename"] == target:
            item["filename"] = dst.name
    INDEX_PATH.write_text(json.dumps(doc, indent=1))

    # Verify the whole chain end to end before the demo.
    got = stego.extract(png)
    cracked = crypto.crack(got["recovered"])["best"]
    ok = got["recovered"] == ciphertext.encode() and cracked["key"] == args.key
    case = {"image": dst.name, "query": args.query, "key": args.key,
            "ciphertext": ciphertext, "plaintext": args.message, "verified": ok}
    (DATA_DIR / "demo_case.json").write_text(json.dumps(case, indent=2))
    print(json.dumps(case, indent=2))
    print("\nChain verified ✔" if ok else "\n!! Chain did NOT verify — check stego.extract / crypto.crack")


if __name__ == "__main__":
    main()
