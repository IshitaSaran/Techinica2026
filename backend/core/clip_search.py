"""Stage 1 — semantic image search with CLIP (the Vultr Cloud GPU workload).

Cost-safe design:
  * build_index() embeds the whole corpus ONCE (on a Vultr GPU if available)
    and writes data/embeddings.npy + data/embeddings_index.json.
  * The API process loads that matrix once at startup. A live query is one
    text/image embed (milliseconds, fine on CPU) + one matrix multiply.
  * torch/open_clip are imported lazily, so the rest of Sift runs even on a
    machine without them installed.
"""
from __future__ import annotations

import io
import json
import os
import threading
import time
from pathlib import Path

import numpy as np

DATA_DIR = Path(os.getenv("SIFT_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
IMAGE_DIR = DATA_DIR / "sample_images"
EMB_PATH = DATA_DIR / "embeddings.npy"
INDEX_PATH = DATA_DIR / "embeddings_index.json"

MODEL_NAME = os.getenv("SIFT_CLIP_MODEL", "ViT-B-32")
PRETRAINED = os.getenv("SIFT_CLIP_PRETRAINED", "laion2b_s34b_b79k")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


def torch_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "none"


def gpu_available() -> bool:
    return torch_device() == "cuda"


class ClipSearch:
    def __init__(self) -> None:
        self.embeddings: np.ndarray | None = None  # (N, D) float32, L2-normalised
        self.index: list[dict] = []
        self.meta: dict = {}
        self._model = None
        self._preprocess = None
        self._tokenizer = None
        self._device = "cpu"
        self._lock = threading.Lock()

    # ----------------------------------------------------------------- cache
    def load_cache(self) -> bool:
        if not (EMB_PATH.exists() and INDEX_PATH.exists()):
            return False
        self.embeddings = np.load(EMB_PATH).astype(np.float32)
        doc = json.loads(INDEX_PATH.read_text())
        self.index, self.meta = doc["items"], doc.get("meta", {})
        return True

    @property
    def ready(self) -> bool:
        return self.embeddings is not None and len(self.index) > 0

    # ----------------------------------------------------------------- model
    def _load_model(self, device: str | None = None) -> None:
        with self._lock:
            if self._model is not None and (device is None or device == self._device):
                return
            import open_clip
            import torch

            self._device = device or "cpu"  # queries default to CPU: cheap & always available
            model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED, device=self._device)
            model.eval()
            self._model, self._preprocess = model, preprocess
            self._tokenizer = open_clip.get_tokenizer(MODEL_NAME)
            torch.set_grad_enabled(False)

    def _norm(self, x: np.ndarray) -> np.ndarray:
        return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12, None)

    def embed_text(self, text: str) -> np.ndarray:
        import torch
        self._load_model()
        with torch.no_grad():
            tokens = self._tokenizer([text]).to(self._device)
            v = self._model.encode_text(tokens).float().cpu().numpy()
        return self._norm(v)[0]

    def embed_image_bytes(self, image_bytes: bytes) -> np.ndarray:
        import torch
        from PIL import Image
        self._load_model()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        with torch.no_grad():
            v = self._model.encode_image(self._preprocess(img).unsqueeze(0).to(self._device)).float().cpu().numpy()
        return self._norm(v)[0]

    # ----------------------------------------------------------------- query
    def rank(self, q: np.ndarray, k: int = 12) -> list[dict]:
        if not self.ready:
            raise RuntimeError("Search index not built. Run scripts/build_embeddings.py.")
        scores = self.embeddings @ q  # cosine similarity (both sides normalised)
        top = np.argsort(-scores)[:k]
        return [{**self.index[i], "score": round(float(scores[i]), 4), "rank": r + 1} for r, i in enumerate(top)]

    def query_text(self, text: str, k: int = 12) -> list[dict]:
        return self.rank(self.embed_text(text), k)

    def query_image(self, image_bytes: bytes, k: int = 12) -> list[dict]:
        return self.rank(self.embed_image_bytes(image_bytes), k)

    # ----------------------------------------------------------------- build
    def build_index(self, image_dir: Path = IMAGE_DIR, batch_size: int = 64, progress: bool = False) -> dict:
        """Embed every image in image_dir. Uses CUDA if present (Vultr GPU)."""
        import torch
        from PIL import Image

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model(device)
        files = sorted(p for p in Path(image_dir).iterdir() if p.suffix.lower() in IMAGE_EXTS)
        if not files:
            raise RuntimeError(f"No images found in {image_dir}")

        t0, vecs, items = time.time(), [], []
        for start in range(0, len(files), batch_size):
            batch, kept = [], []
            for p in files[start:start + batch_size]:
                try:
                    img = Image.open(p).convert("RGB")
                    batch.append(self._preprocess(img))
                    kept.append({"filename": p.name, "width": img.width, "height": img.height})
                except Exception as e:  # skip unreadable files, keep going
                    print(f"  skip {p.name}: {e}")
            if not batch:
                continue
            with torch.no_grad():
                v = self._model.encode_image(torch.stack(batch).to(device)).float().cpu().numpy()
            vecs.append(v)
            items.extend(kept)
            if progress:
                print(f"  embedded {len(items)}/{len(files)}")

        emb = self._norm(np.concatenate(vecs)).astype(np.float32)
        meta = {"model": MODEL_NAME, "pretrained": PRETRAINED, "device": device,
                "count": len(items), "seconds": round(time.time() - t0, 2),
                "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else None}
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        np.save(EMB_PATH, emb)
        INDEX_PATH.write_text(json.dumps({"meta": meta, "items": items}, indent=1))
        self.embeddings, self.index, self.meta = emb, items, meta
        # After building on GPU, drop back to CPU for queries.
        self._model = None
        return meta


search = ClipSearch()
