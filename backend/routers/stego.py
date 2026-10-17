"""Stage 2 endpoints. Wraps core/stego.py, which must provide:

    analyze(image_bytes) -> dict          # numbers + "reading" (str) + "suspicious" (bool)
    extract(image_bytes) -> dict          # {recovered: bytes, as_text: str|None, confidence: float}
    bit_plane_image(image_bytes) -> bytes # PNG of the LSB plane
    embed(image_bytes, message: bytes) -> bytes  # PNG; inverse of extract (sandbox/demo only)

If the module is absent the endpoints answer 501 and /api/analyze reports a
"module not installed" finding, so the rest of the app keeps working.
"""
from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from core.explain import enrich
from core.findings import Finding, Severity

try:
    from core import stego as stego_core
except ImportError:  # module not installed yet
    stego_core = None

router = APIRouter(prefix="/api/stego", tags=["stego"])
MAX_BYTES = 20 * 1024 * 1024


REQUIRED = ("analyze", "extract", "bit_plane_image", "embed")


def available() -> bool:
    # An empty or partial stego.py still imports, so check the actual functions.
    return stego_core is not None and all(callable(getattr(stego_core, f, None)) for f in REQUIRED)


def missing() -> list[str]:
    return [f for f in REQUIRED if not callable(getattr(stego_core, f, None))] if stego_core else list(REQUIRED)


def _require() -> None:
    if not available():
        raise HTTPException(501, f"Stage 2 module incomplete: backend/core/stego.py is missing {', '.join(missing())} (see README).")


def _jsonable(x: Any) -> Any:
    """Make numpy scalars/arrays and bytes safe for JSON."""
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (bytes, bytearray)):
        return base64.b64encode(bytes(x)).decode()
    if hasattr(x, "tolist"):
        return x.tolist()
    if hasattr(x, "item"):
        return x.item()
    return x


async def read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (20 MB max).")
    return data


# ---------------------------------------------------------------- findings
def unavailable_finding() -> Finding:
    return Finding(stage="stego", kind="stego.unavailable", title="Hidden-data check not installed",
                   severity=Severity.info, summary="This server doesn't have the steganalysis module yet, so images can't be checked for hidden data.",
                   technical="backend/core/stego.py is missing.")


def analyze_findings(image_bytes: bytes) -> tuple[list[Finding], str | None]:
    if not available():
        return [unavailable_finding()], None
    res = _jsonable(stego_core.analyze(image_bytes))
    suspicious = bool(res.get("suspicious"))
    reading = res.get("reading") or ("The lowest bit layer looks abnormal." if suspicious else "The lowest bit layer looks natural.")
    finding = Finding(
        stage="stego", kind="stego.suspicious" if suspicious else "stego.clean",
        title="Possible hidden data in image" if suspicious else "No sign of hidden data",
        severity=Severity.high if suspicious else Severity.info,
        summary=reading,
        technical="; ".join(f"{k}={v}" for k, v in res.items() if isinstance(v, (int, float, str)) and k != "reading"),
        data=res,
    )
    try:
        plane = base64.b64encode(stego_core.bit_plane_image(image_bytes)).decode()
    except Exception:
        plane = None
    return enrich([finding]), plane


def extract_findings(image_bytes: bytes) -> list[Finding]:
    if not available():
        return [unavailable_finding()]
    res = stego_core.extract(image_bytes)
    recovered: bytes = res.get("recovered") or b""
    text = res.get("as_text")
    conf = float(res.get("confidence") or 0.0)
    if not recovered:
        f = Finding(stage="stego", kind="stego.no_payload", title="No readable hidden payload",
                    severity=Severity.low, summary="We couldn't pull a hidden message out of this image with the layouts we know.",
                    technical=f"confidence={conf:.2f}", data={"confidence": conf})
    else:
        preview = (text[:140] + ("…" if len(text) > 140 else "")) if text else f"{len(recovered)} bytes of binary data"
        f = Finding(stage="stego", kind="stego.payload", title="Hidden data extracted",
                    severity=Severity.high,
                    summary=f"Recovered {len(recovered)} hidden bytes: “{preview}”" if text else f"Recovered {preview}.",
                    technical=f"LSB payload, {len(recovered)} bytes, confidence {conf:.2f}. Encoding: {'utf-8' if text else 'binary (base64 below)'}.",
                    data={"text": text, "base64": base64.b64encode(recovered).decode(),
                          "length": len(recovered), "confidence": conf})
    return enrich([f])


# ---------------------------------------------------------------- routes
@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    _require()
    findings, plane = analyze_findings(await read_upload(file))
    return {"findings": findings, "bit_plane_png": plane}


@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    _require()
    findings = extract_findings(await read_upload(file))
    return {"findings": findings, **{k: findings[0].data.get(k) for k in ("text", "base64", "confidence")}}


@router.post("/embed")
async def embed(file: UploadFile = File(...), message: str = Form(...)):
    """Education sandbox: hide the learner's own message so they can watch it be found."""
    _require()
    if not message or len(message) > 2000:
        raise HTTPException(400, "Message must be 1–2000 characters.")
    try:
        png = stego_core.embed(await read_upload(file), message.encode("utf-8"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"image_png": base64.b64encode(png).decode(), "bytes_hidden": len(message.encode("utf-8"))}
