"""Stage 3 endpoints. Accept either a `text` form field or an uploaded `file`."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from core import crypto as crypto_core
from core.explain import enrich

router = APIRouter(prefix="/api/crypto", tags=["crypto"])
MAX_BYTES = 256 * 1024


async def _input(text: str | None, file: UploadFile | None) -> bytes:
    if file is not None and file.filename:
        data = await file.read()
    elif text:
        data = text.encode("utf-8")
    else:
        raise HTTPException(400, "Send a `text` field or a `file`.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Input too large (256 KB max).")
    return data


@router.post("/identify")
async def identify(text: str | None = Form(None), file: UploadFile | None = File(None)):
    data = await _input(text, file)
    return {"findings": enrich(crypto_core.identify_findings(data)), **crypto_core.identify(data)}


@router.post("/crack")
async def crack(text: str | None = Form(None), file: UploadFile | None = File(None)):
    data = await _input(text, file)
    findings = enrich(crypto_core.crack_findings(data))
    return {"findings": findings, **findings[0].data}
