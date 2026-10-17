"""Sift — guided digital-forensics investigations.  Run:  uvicorn main:app --reload"""
from __future__ import annotations

import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.clip_search import IMAGE_DIR, search, torch_device
from routers import analyze, crypto, search as search_router, stego

app = FastAPI(title="Sift", version="0.1.0", description="Find it → Open it → Crack it.")

# CORS — env-driven, with defaults that work out of the box for local dev + Vercel:
#   SIFT_CORS_ORIGINS  comma-separated exact origins (default: the Vite dev server)
#   SIFT_CORS_REGEX    regex for extra origins (default: any https://*.vercel.app,
#                      covering production and preview deploys). Starlette fullmatches
#                      it, so look-alikes such as x.vercel.app.evil.com are rejected.
#                      Set it to an empty string to turn regex matching off.
# No credentials are allowed (the API is cookie-free), so a broad origin match is safe.
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
DEFAULT_CORS_REGEX = r"https://.*\.vercel\.app"

origins = [o.strip() for o in os.getenv("SIFT_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=os.getenv("SIFT_CORS_REGEX", DEFAULT_CORS_REGEX) or None,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

for r in (analyze.router, stego.router, crypto.router, search_router.router):
    app.include_router(r)

# Evidence thumbnails for the search UI.
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=IMAGE_DIR), name="images")

_DEVICE = "unknown"


@app.on_event("startup")
def _startup() -> None:
    global _DEVICE
    _DEVICE = torch_device()     # "cuda" | "cpu" | "none" (torch not installed)
    if search.load_cache() and _DEVICE != "none":  # load the embedding matrix ONCE
        # Warm the text encoder in the background so the first live query is instant.
        threading.Thread(target=lambda: search.embed_text("warm up"), daemon=True).start()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "gpu": _DEVICE == "cuda",
        "device": _DEVICE,
        "search_index": len(search.index),
        "search_built_on": search.meta.get("device"),
        "stego_module": stego.available(),
        "stego_missing": stego.missing(),
    }
