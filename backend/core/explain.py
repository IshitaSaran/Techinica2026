"""Plain-language explanations ("what / why / how") for every Finding.

Sift ships with hand-written templates so explanations work offline with no API
keys. The templates are written for a non-expert: short sentences, no jargon in
`what`/`why`, and the real technique named only in `how`.

Extension point: a provider can be registered in PROVIDERS and selected with the
SIFT_EXPLAIN_PROVIDER env var. None is registered today — templates are used.
A provider must return an Education or None (None = fall back to templates).
"""
from __future__ import annotations

import os
from typing import Callable

from .findings import Education, Finding

TEMPLATES: dict[str, dict[str, str]] = {
    # ---- Stage 1: search -------------------------------------------------
    "search.results": {
        "what": "We searched every image in the evidence set for ones that match your description.",
        "why": "Investigators can't look at hundreds of photos one by one. Searching by meaning lets them jump straight to the few that matter.",
        "how": "An AI model called CLIP turns each image and your words into lists of numbers that capture their meaning. Images whose numbers point in the same direction as your words (high 'cosine similarity') rank first.",
    },
    "search.empty": {
        "what": "The image search isn't ready yet.",
        "why": "Searching needs a pre-built index of every image, made once ahead of time.",
        "how": "Run scripts/build_embeddings.py (ideally on a GPU) to build the index, then restart the server.",
    },
    # ---- Stage 2: stego ---------------------------------------------------
    "stego.suspicious": {
        "what": "This picture shows signs that something may be hidden inside it.",
        "why": "Pictures can carry secret data that's invisible to the eye. Spotting it is often the first clue in a case.",
        "how": "Every colour value in an image ends in a 'lowest bit' that barely affects how it looks. In normal photos those bits follow natural patterns. Hidden data makes them look like random coin flips, and a chi-square test measures exactly that.",
    },
    "stego.clean": {
        "what": "We didn't find signs of hidden data in this picture.",
        "why": "Ruling an image out is useful too. It lets the investigator move on.",
        "how": "We checked whether the image's lowest bits look naturally patterned or suspiciously random. They looked natural. Advanced tools can hide data more cleverly, so this is strong evidence, not proof.",
    },
    "stego.payload": {
        "what": "We pulled hidden data out of this picture.",
        "why": "This is the evidence itself: the message someone tried to hide.",
        "how": "We read the lowest bit of every red, green and blue value in order and joined them into bytes. The first 32 bits say how long the message is, and the rest is the message.",
    },
    "stego.no_payload": {
        "what": "We couldn't read a hidden message using the layouts we know.",
        "why": "Data may still be there, hidden by a different tool or scrambled with a password.",
        "how": "We tried reading the lowest bits in Sift's own layout and in common CTF layouts. None gave a sensible length or readable bytes.",
    },
    "stego.unavailable": {
        "what": "The hidden-data module isn't installed on this server.",
        "why": "This part of the investigation can't run until it is.",
        "how": "Add backend/core/stego.py (see the README) and restart the backend.",
    },
    "stego.jpeg": {
        "what": "This is a JPEG photo, which tends to destroy hidden bits.",
        "why": "JPEG saving throws away tiny details, which is exactly where lowest-bit hiding puts data.",
        "how": "Lowest-bit hiding only survives lossless formats like PNG or BMP. JPEGs need different methods (for example DCT-coefficient analysis).",
    },
    # ---- Stage 3: crypto --------------------------------------------------
    "crypto.identify": {
        "what": "We made an educated guess about how this text was scrambled.",
        "why": "Knowing the kind of cipher tells you which attack to try, which saves enormous time.",
        "how": "We measured the 'Index of Coincidence': how often two random letters from the text match. English gives about 6.7%, random letters about 3.8%. Simple ciphers keep English's value, and multi-key ciphers like Vigenère land in between.",
    },
    "crypto.caesar": {
        "what": "The message was hidden by shifting every letter the same number of places.",
        "why": "This is one of the oldest ciphers, and it's easy to break: there are only 25 possible shifts.",
        "how": "We tried all 25 shifts and scored each result by how much its letter frequencies look like English (lots of E, T, A; few Z, Q). The best match was the answer.",
    },
    "crypto.xor": {
        "what": "The message was scrambled by mixing every byte with one secret number (XOR).",
        "why": "Malware and amateurs often use XOR because it's simple, but a one-byte key is easy to guess.",
        "how": "There are only 255 possible keys. We tried every one and kept the result that reads most like English.",
    },
    "crypto.vigenere": {
        "what": "The message was encrypted with a keyword (a Vigenère cipher).",
        "why": "This cipher was called 'unbreakable' for 300 years. Breaking it shows why repeating keys are weak.",
        "how": "First we found the keyword's length: splitting the text into that many columns makes each column look like ordinary English again. Each column is then just a Caesar shift, and frequency analysis cracks each letter of the key.",
    },
    "crypto.decode": {
        "what": "The text was encoded, not encrypted. It was just written in a different alphabet.",
        "why": "Encodings like Base64 hide nothing from someone who knows them, but they make data look scary and are often layered on top of real encryption.",
        "how": "We recognised the alphabet (Base64, Base32 or hexadecimal) and decoded it, repeating until the result stopped being an encoding.",
    },
    "crypto.hash-dictionary": {
        "what": "This was a password 'fingerprint' (a hash), and we found the password.",
        "why": "Hashes can't be reversed, but weak passwords can be guessed. This is why password reuse and short passwords are dangerous.",
        "how": "We identified the hash type from its length, then hashed a list of common passwords until one produced the same fingerprint.",
    },
    "crypto.hash-id": {
        "what": "This is a hash: a one-way fingerprint of some data.",
        "why": "Recognising a hash stops an investigator from wasting time trying to 'decrypt' it.",
        "how": "Hash types have tell-tale lengths: MD5 is 32 hex characters, SHA-1 is 40 and SHA-256 is 64. Recovering the original means guessing, for example with a dictionary attack.",
    },
    "crypto.plaintext": {
        "what": "This text wasn't encrypted. It's readable as-is.",
        "why": "Checking for the obvious first is good forensic practice.",
        "how": "It already scored as English on letter frequency and common words.",
    },
    "crypto.unbroken": {
        "what": "We couldn't turn this into readable text.",
        "why": "Modern encryption (like AES) is designed to resist exactly these attacks. Without the key, the data stays locked.",
        "how": "We tried Caesar, XOR, Vigenère and common encodings. Very high randomness (entropy near 8 bits per byte) is the sign of modern encryption or compression.",
    },
    # ---- Metadata ---------------------------------------------------------
    "metadata.file": {
        "what": "Basic facts about this file: its real type, size and randomness.",
        "why": "A file's name can lie, but its first bytes (its 'magic number') reveal what it really is.",
        "how": "We read the file's signature bytes and measured its entropy. Near-random content usually means it's compressed or encrypted.",
    },
    "metadata.image": {
        "what": "Basic facts about this image.",
        "why": "Size, format and embedded camera data (EXIF) can reveal where and when a picture was taken, or that it was edited.",
        "how": "We decoded the image header and listed any EXIF tags present.",
    },
}

GENERIC = {
    "what": "This is one of the facts Sift found while examining the file.",
    "why": "Each finding is a clue. Together they tell the story of what happened to the file.",
    "how": "See the technical details for the exact measurement.",
}

# name -> callable(Finding) -> Education | None
PROVIDERS: dict[str, Callable[[Finding], Education | None]] = {}


def _template_for(kind: str) -> dict[str, str]:
    return TEMPLATES.get(kind, GENERIC)


def explain(finding: Finding) -> Education:
    provider = PROVIDERS.get(os.getenv("SIFT_EXPLAIN_PROVIDER", ""))
    if provider:
        try:
            edu = provider(finding)
            if edu:
                return edu
        except Exception:  # an optional provider must never break the app
            pass
    return Education(**_template_for(finding.kind))


def enrich(findings: list[Finding]) -> list[Finding]:
    """Fill in `education` for any finding that doesn't have it yet."""
    for f in findings:
        if not (f.education.what or f.education.why or f.education.how):
            f.education = explain(f)
    return findings
