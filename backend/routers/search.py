"""Stage 1 endpoints: CLIP semantic search over the cached evidence index."""
from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from core.clip_search import search
from core.explain import enrich
from core.findings import Finding, Severity

router = APIRouter(prefix="/api/search", tags=["search"])


class TextQuery(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    k: int = Field(12, ge=1, le=60)


def _results_finding(query: str, matches: list[dict]) -> Finding:
    top = matches[0] if matches else None
    return Finding(
        stage="search", kind="search.results",
        title=f"{len(matches)} closest matches for “{query}”",
        severity=Severity.info,
        summary=(f"The closest image is {top['filename']}. Results are ranked by how well each picture matches your description."
                 if top else "No images matched."),
        technical=f"CLIP {search.meta.get('model')} cosine similarity over {len(search.index)} cached embeddings; top score {top['score'] if top else 0}.",
        data={"matches": matches, "query": query},
    )


def _guard():
    if not search.ready:
        raise HTTPException(503, "Search index not built yet. Run backend/scripts/build_embeddings.py.")


async def _run(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except ImportError:
        raise HTTPException(503, "CLIP is not installed on this server (pip install torch open_clip_torch).")


@router.post("/query")
async def query(body: TextQuery):
    _guard()
    matches = await _run(search.query_text, body.text, body.k)
    return {"findings": enrich([_results_finding(body.text, matches)]), "matches": matches}


@router.post("/by-image")
async def by_image(file: UploadFile = File(...), k: int = Form(12)):
    _guard()
    matches = await _run(search.query_image, await file.read(), max(1, min(k, 60)))
    return {"findings": enrich([_results_finding(f"image: {file.filename}", matches)]), "matches": matches}


@router.post("/index")
async def rebuild_index(x_admin_token: str | None = Header(None)):
    """Admin: re-embed data/sample_images. Slow on CPU — prefer the script on a GPU box."""
    expected = os.getenv("SIFT_ADMIN_TOKEN")
    if not expected or x_admin_token != expected:
        raise HTTPException(403, "Set SIFT_ADMIN_TOKEN on the server and send it as X-Admin-Token.")
    meta = await _run(search.build_index)
    return {"status": "ok", **meta}
