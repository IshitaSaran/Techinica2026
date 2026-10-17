"""One-off: embed every image in data/sample_images with CLIP.

Run this on the Vultr Cloud GPU instance, copy data/embeddings.npy and
data/embeddings_index.json to the CPU instance, then DESTROY the GPU instance.

    python scripts/build_embeddings.py [--images DIR] [--batch 64]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.clip_search import EMB_PATH, IMAGE_DIR, INDEX_PATH, search  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=Path, default=IMAGE_DIR)
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    meta = search.build_index(args.images, batch_size=args.batch, progress=True)
    print(f"\nEmbedded {meta['count']} images in {meta['seconds']}s on {meta['device']}"
          + (f" ({meta['gpu_name']})" if meta.get("gpu_name") else ""))
    print(f"Wrote {EMB_PATH}\n      {INDEX_PATH}")
    if meta["device"] == "cuda":
        print("\n>>> Embeddings are cached. Copy them to the CPU box and DESTROY this GPU instance now. <<<")


if __name__ == "__main__":
    main()
