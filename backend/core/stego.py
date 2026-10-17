"""
core/stego.py — LSB steganalysis for the Sift forensics tool.

Forensic job: DETECT and RECOVER data hidden in the least-significant-bit (LSB)
plane of a PNG image — standard CTF / digital-forensics steganalysis.

Container format (self-consistent, so recovery is deterministic):
    [ 32-bit big-endian length header N ][ N payload bytes ]
written into the LSB of the R, G, B channels in row-major pixel order
(pixel 0 R, pixel 0 G, pixel 0 B, pixel 1 R, ...).

NOTE: images hidden by *other* tools may use different containers (different
bit order, channel subset, terminator-delimited payloads, etc.). `extract`
targets our format, which also matches the most common CTF LSB layout
(row-major, RGB, MSB-first bits). That is the expected scope for the demo.

Functions (signatures the routers/sandbox/demo script depend on):
    extract(image_bytes) -> dict    # the core recovery function
    analyze(image_bytes) -> dict    # detection WITHOUT recovery
    bit_plane_image(image_bytes) -> bytes   # LSB plane as a viewable PNG
    embed(image_bytes, message) -> bytes    # inverse of extract (makes practice evidence)
"""

from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image

HEADER_BITS = 32  # 32-bit big-endian payload-length header


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def _load_rgb(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes to an (H, W, 3) uint8 RGB array."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.asarray(img, dtype=np.uint8)


def _lsb_stream(arr: np.ndarray) -> np.ndarray:
    """Flatten to the row-major R,G,B bit stream of least-significant bits."""
    return (arr.reshape(-1) & 1).astype(np.uint8)


def _printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    printable = sum(1 for b in data if 9 <= b <= 13 or 32 <= b <= 126)
    return printable / len(data)


def _shannon_entropy(values: np.ndarray) -> float:
    """Shannon entropy (bits per symbol) of a byte/array distribution."""
    if values.size == 0:
        return 0.0
    counts = np.bincount(values.reshape(-1), minlength=256).astype(np.float64)
    probs = counts[counts > 0] / values.size
    return float(-np.sum(probs * np.log2(probs)))


# ----------------------------------------------------------------------------
# embed — makes practice/demo evidence (inverse of extract)
# ----------------------------------------------------------------------------
def embed(image_bytes: bytes, message) -> bytes:
    """
    Hide `message` in the image's LSB plane and return PNG bytes.
    Used only to generate the demo's seized image and the Learn-mode sandbox
    ("hide your own message, then watch the tool recover it").
    """
    if isinstance(message, str):
        payload = message.encode("utf-8")
    else:
        payload = bytes(message)

    arr = _load_rgb(image_bytes)
    flat = arr.reshape(-1).copy()
    capacity_bits = flat.size

    header = np.frombuffer(len(payload).to_bytes(4, "big"), dtype=np.uint8)
    body = np.frombuffer(payload, dtype=np.uint8)
    bits = np.unpackbits(np.concatenate([header, body]))  # MSB-first => big-endian

    if bits.size > capacity_bits:
        raise ValueError(
            f"Message too large: needs {bits.size} bits but image holds {capacity_bits}. "
            "Use a bigger image or a shorter message."
        )

    flat[: bits.size] = (flat[: bits.size] & 0xFE) | bits
    out = flat.reshape(arr.shape).astype(np.uint8)

    buf = io.BytesIO()
    Image.fromarray(out, "RGB").save(buf, format="PNG")  # PNG is lossless — LSBs survive
    return buf.getvalue()


# ----------------------------------------------------------------------------
# extract — the core forensic recovery function
# ----------------------------------------------------------------------------
def extract(image_bytes: bytes) -> dict:
    """
    Recover a hidden payload from the LSB plane.
    Returns {recovered: bytes, as_text: str|None, confidence: float}.
    confidence ~0 means "nothing coherent here"; ~1 means "clean readable payload".
    """
    arr = _load_rgb(image_bytes)
    stream = _lsb_stream(arr)

    if stream.size < HEADER_BITS:
        return {"recovered": b"", "as_text": None, "confidence": 0.0}

    header_bits = stream[:HEADER_BITS]
    length = int(np.packbits(header_bits).view(">u4")[0])

    capacity_bytes = (stream.size - HEADER_BITS) // 8
    # A sane length is the first sign a real payload is present. A wild header
    # (0, or larger than the image can hold) means the LSBs are just image noise.
    if length <= 0 or length > capacity_bytes:
        return {"recovered": b"", "as_text": None, "confidence": 0.0}

    needed = length * 8
    body_bits = stream[HEADER_BITS:HEADER_BITS + needed]
    recovered = np.packbits(body_bits).tobytes()[:length]

    try:
        as_text = recovered.decode("utf-8")
        text_ok = True
    except UnicodeDecodeError:
        as_text = None
        text_ok = False

    # Confidence: a valid header + clean UTF-8 text is a strong hit; binary
    # payloads with a valid header are a moderate hit.
    if text_ok:
        confidence = round(0.5 + 0.5 * _printable_ratio(recovered), 3)
    else:
        confidence = 0.4

    return {"recovered": recovered, "as_text": as_text, "confidence": float(confidence)}


# ----------------------------------------------------------------------------
# analyze — detection WITHOUT recovery (statistical tells)
# ----------------------------------------------------------------------------
def analyze(image_bytes: bytes) -> dict:
    """
    Statistical steganalysis: does this image *look like* it hides LSB data,
    even before we try to pull the payload out?

    Natural-photo LSBs are correlated with the higher bits and are not a perfect
    coin-flip. LSB-embedded data looks like random noise: ~50% ones and ~1.0
    bits of entropy. We report both, per channel, plus a chi-square test of the
    LSB distribution against a 50/50 split.
    """
    arr = _load_rgb(image_bytes)
    channels = {0: "red", 1: "green", 2: "blue"}
    per_channel = {}
    suspicious_channels = 0

    for idx, name in channels.items():
        lsb = (arr[:, :, idx].reshape(-1) & 1).astype(np.uint8)
        n = lsb.size
        ones = int(lsb.sum())
        zeros = n - ones
        ones_fraction = ones / n if n else 0.0

        # chi-square vs expected 50/50. LOW chi-square => indistinguishable from
        # a fair coin => consistent with embedded random bits.
        expected = n / 2.0
        chi_square = (((ones - expected) ** 2) + ((zeros - expected) ** 2)) / expected if n else 0.0

        # entropy of the LSB plane itself (max 1.0 bit for a two-symbol stream)
        p1 = ones_fraction
        p0 = 1.0 - p1
        lsb_entropy = 0.0
        for p in (p0, p1):
            if p > 0:
                lsb_entropy -= p * math.log2(p)

        channel_suspicious = (abs(ones_fraction - 0.5) < 0.01) and (lsb_entropy > 0.999)
        if channel_suspicious:
            suspicious_channels += 1

        per_channel[name] = {
            "ones_fraction": round(ones_fraction, 4),
            "chi_square": round(float(chi_square), 2),
            "lsb_entropy_bits": round(lsb_entropy, 4),
            "suspicious": channel_suspicious,
        }

    file_entropy = round(_shannon_entropy(arr), 4)  # bits/symbol over pixel values
    suspicious = suspicious_channels >= 2

    if suspicious:
        severity = "high"
        reading = (
            "The lowest bit layer is statistically abnormal: across the colour channels "
            "it is almost exactly a 50/50 coin-flip with ~1.0 bits of entropy, which natural "
            "photos rarely are. That pattern usually means data has been hidden in the LSBs. "
            "Run extraction to try to recover it."
        )
    elif suspicious_channels == 1:
        severity = "medium"
        reading = (
            "One colour channel's lowest bit layer looks unusually random. That can indicate "
            "hidden data, or just a noisy image. Worth running extraction to check."
        )
    else:
        severity = "info"
        reading = (
            "The lowest bit layer looks like ordinary image noise — no strong statistical sign "
            "of hidden LSB data. (A negative result here does not rule out other hiding methods.)"
        )

    return {
        "suspicious": suspicious,
        "severity": severity,
        "reading": reading,
        "file_entropy_bits": file_entropy,
        "channels": per_channel,
        "capacity_bytes": (arr.size - HEADER_BITS) // 8,
    }


# ----------------------------------------------------------------------------
# bit_plane_image — render the LSB plane so the UI can show it
# ----------------------------------------------------------------------------
def bit_plane_image(image_bytes: bytes) -> bytes:
    """
    Return a PNG of the LSB plane (each channel's lowest bit scaled to 0/255).
    Hidden-data regions show up as structured texture; clean areas look like
    random snow. Gives the UI (and a sighted or screen-reader-described view)
    something concrete to display.
    """
    arr = _load_rgb(image_bytes)
    plane = ((arr & 1) * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(plane, "RGB").save(buf, format="PNG")
    return buf.getvalue()


# ----------------------------------------------------------------------------
# quick self-test:  python core/stego.py
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    # Make a plain test image, hide a message, then detect + recover it.
    base = Image.new("RGB", (256, 256))
    base.putdata([((x * 7) % 256, (y * 5) % 256, (x + y) % 256)
                  for y in range(256) for x in range(256)])
    bbuf = io.BytesIO()
    base.save(bbuf, format="PNG")
    clean_png = bbuf.getvalue()

    secret = "Meet at the north dock at midnight."
    stego_png = embed(clean_png, secret)

    print("clean  analyze:", analyze(clean_png)["severity"])
    print("stego  analyze:", analyze(stego_png)["severity"])
    got = extract(stego_png)
    print("recovered      :", repr(got["as_text"]), "confidence", got["confidence"])
    assert got["as_text"] == secret, "round-trip failed"
    print("OK — embed/extract round-trip verified")