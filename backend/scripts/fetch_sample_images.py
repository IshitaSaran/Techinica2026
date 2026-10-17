"""Download a demo evidence set of real photos (Lorem Picsum, free-to-use Unsplash images).

    python scripts/fetch_sample_images.py --count 520
"""
from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.clip_search import IMAGE_DIR  # noqa: E402


def fetch(i: int, size: str) -> str | None:
    out = IMAGE_DIR / f"evidence_{i:04d}.jpg"
    if out.exists():
        return out.name
    w, h = size.split("x")
    try:
        with urllib.request.urlopen(f"https://picsum.photos/id/{i}/{w}/{h}", timeout=30) as r:
            out.write_bytes(r.read())
        return out.name
    except (urllib.error.URLError, TimeoutError):
        return None  # some ids don't exist; that's fine


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=520)
    ap.add_argument("--size", default="640x480")
    args = ap.parse_args()
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    got, i = 0, 0
    with ThreadPoolExecutor(16) as pool:
        while got < args.count and i < 1100:  # picsum has ids 0..~1084
            batch = range(i, i + 64)
            got += sum(1 for r in pool.map(lambda n: fetch(n, args.size), batch) if r)
            i += 64
            print(f"  {got} images")
    print(f"Done: {got} images in {IMAGE_DIR}")


if __name__ == "__main__":
    main()
