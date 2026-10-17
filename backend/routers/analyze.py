"""POST /api/analyze — identify a file by its magic bytes and run the right pipeline.

A file's extension can lie; its first bytes ("magic number") usually can't.
"""
from __future__ import annotations

import io

from fastapi import APIRouter, File, UploadFile

from core import crypto as crypto_core
from core.explain import enrich
from core.findings import Finding, Severity

from . import stego as stego_router

router = APIRouter(prefix="/api", tags=["analyze"])

# extract() reports ~0 for "nothing coherent", 0.4 for a valid header + binary
# payload, and 0.5–1.0 for a readable payload. On clean photos ~1% of random LSB
# headers look valid and yield 0.4 binary junk, so the one-click flow only surfaces
# readable payloads; binary ones remain available via Stage 2's Extract button.
MIN_EXTRACT_CONFIDENCE = 0.5

MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "png", "image"),
    (b"\xff\xd8\xff", "jpeg", "image"),
    (b"GIF87a", "gif", "image"),
    (b"GIF89a", "gif", "image"),
    (b"BM", "bmp", "image"),
    (b"%PDF", "pdf", "document"),
    (b"PK\x03\x04", "zip (or docx/xlsx/apk)", "archive"),
    (b"\x1f\x8b", "gzip", "archive"),
    (b"7z\xbc\xaf\x27\x1c", "7z", "archive"),
    (b"Rar!", "rar", "archive"),
    (b"\x7fELF", "elf executable", "binary"),
    (b"MZ", "windows executable", "binary"),
]


def sniff(data: bytes) -> tuple[str, str]:
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image"
    for sig, name, family in MAGIC:
        if data.startswith(sig):
            return name, family
    if crypto_core.printable_ratio(data[:4096]) > 0.95:
        return "text", "text"
    return "unknown binary", "binary"


def _file_finding(name: str, data: bytes, ftype: str) -> Finding:
    ent = crypto_core.byte_entropy(data)
    # Images/archives/PDFs are compressed by design, so high entropy only means
    # something for files we couldn't otherwise identify.
    high = ent > 7.5 and ftype in ("unknown binary", "text")
    return Finding(
        stage="metadata", kind="metadata.file",
        title=f"File identified as {ftype}",
        severity=Severity.low if high and ftype == "unknown binary" else Severity.info,
        summary=(f"This file's real type is {ftype}" + (" and its contents look almost perfectly random, which usually means encrypted or compressed data." if high else ".")),
        technical=f"{name}: {len(data)} bytes; magic={data[:8].hex()}; entropy={ent:.3f} bits/byte.",
        data={"filename": name, "type": ftype, "size": len(data), "entropy": round(ent, 3), "magic_hex": data[:8].hex()},
    )


def _image_finding(name: str, data: bytes, ftype: str) -> Finding:
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    exif = {}
    try:
        exif = {str(k): str(v)[:80] for k, v in img.getexif().items()}
    except Exception:
        pass
    return Finding(
        stage="metadata", kind="metadata.image",
        title=f"{ftype.upper()} image, {img.width}×{img.height}",
        severity=Severity.info,
        summary=f"A {img.width}×{img.height} {ftype.upper()} picture" + (f" with {len(exif)} embedded camera/EXIF tags." if exif else " with no camera (EXIF) data."),
        technical=f"mode={img.mode}; format={img.format}; size={len(data)} bytes; EXIF tags={len(exif)}",
        data={"filename": name, "width": img.width, "height": img.height, "mode": img.mode, "exif": exif},
    )


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> list[Finding]:
    data = await stego_router.read_upload(file)
    ftype, family = sniff(data)
    findings: list[Finding] = [_file_finding(file.filename or "upload", data, ftype)]

    if family == "image":
        try:
            findings.append(_image_finding(file.filename or "upload", data, ftype))
        except Exception:
            pass
        if ftype == "jpeg":
            findings.append(Finding(stage="stego", kind="stego.jpeg", title="JPEG: lowest-bit hiding unlikely to survive",
                                    severity=Severity.info, summary="JPEG compression wipes out the tiny details where lowest-bit hidden data lives.",
                                    technical="LSB steganalysis targets lossless formats (PNG/BMP). JPEG needs DCT-domain tools (e.g. stegdetect)."))
        else:
            stego_f, plane = stego_router.analyze_findings(data)
            if plane:
                stego_f[0].data["bit_plane_png"] = plane
            findings += stego_f
            if stego_router.available():
                # The statistical detector decides what the analyze card says; extraction
                # success decides whether a payload card appears. Small payloads barely
                # move whole-image statistics, so always try to extract.
                extracted = stego_router.extract_findings(data)[0]
                found = (extracted.kind == "stego.payload"
                         and extracted.data.get("confidence", 0) >= MIN_EXTRACT_CONFIDENCE)
                if found:
                    findings.append(extracted)
                    # Chain: if the payload is text, hand it straight to Stage 3.
                    if extracted.data.get("text"):
                        findings += crypto_core.crack_findings(extracted.data["text"].encode())
                elif stego_f[0].kind == "stego.suspicious":
                    # Detector fired but nothing readable came out: say so honestly.
                    findings.append(extracted)
    elif family == "text":
        findings += crypto_core.identify_findings(data)
        findings += crypto_core.crack_findings(data)

    return enrich(findings)
