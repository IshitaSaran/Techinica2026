"""Stage 3 — cipher identification and breaking.

Everything here is classical cryptanalysis, done for real:
  * English-likeness scoring (letter-frequency chi-square + common-word hits)
    is the referee that ranks every candidate decryption.
  * Index of Coincidence (IoC) tells mono- from poly-alphabetic ciphers.
  * Breakers: Caesar/ROT (all 25 shifts), single-byte XOR (all 256 keys),
    Vigenère (IoC key-length estimate + Kasiski support + per-column
    frequency analysis), base64/base32/hex peeling, hash identification
    (+ a tiny dictionary attack for unsalted md5/sha1/sha256).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import math
import re
import string
from collections import Counter
from dataclasses import asdict, dataclass, field

from .findings import Finding, Severity

# --------------------------------------------------------------------------- #
# English model
# --------------------------------------------------------------------------- #
ENGLISH_FREQ = {
    "A": 8.167, "B": 1.492, "C": 2.782, "D": 4.253, "E": 12.702, "F": 2.228,
    "G": 2.015, "H": 6.094, "I": 6.966, "J": 0.153, "K": 0.772, "L": 4.025,
    "M": 2.406, "N": 6.749, "O": 7.507, "P": 1.929, "Q": 0.095, "R": 5.987,
    "S": 6.327, "T": 9.056, "U": 2.758, "V": 0.978, "W": 2.360, "X": 0.150,
    "Y": 1.974, "Z": 0.074,
}
_FREQ = [ENGLISH_FREQ[c] / 100 for c in string.ascii_uppercase]

COMMON_WORDS = set("""
the be to of and a in that have i it for not on with he as you do at this but his by
from they we say her she or an will my one all would there their what so up out if
about who get which go me when make can like time no just him know take people into
year your good some could them see other than then now look only come its over think
also back after use two how our work first well way even new want because any these
give day most us is are was were has had been meet tonight midnight dock warehouse
north south east west at pm am key code drop location package left behind under
""".split())

IOC_ENGLISH = 0.0667   # probability two random letters from English text match
IOC_RANDOM = 1 / 26    # ≈ 0.0385 for uniformly random letters

PRINTABLE = set(range(32, 127)) | {9, 10, 13}


def letters_only(text: str) -> str:
    return "".join(c for c in text.upper() if "A" <= c <= "Z")


def printable_ratio(data: bytes) -> float:
    return sum(b in PRINTABLE for b in data) / len(data) if data else 0.0


def byte_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in Counter(data).values())


def chi_square_english(text: str) -> float:
    """Chi-square distance between the text's letter counts and English."""
    letters = letters_only(text)
    n = len(letters)
    if n == 0:
        return float("inf")
    counts = Counter(letters)
    return sum((counts.get(c, 0) - n * p) ** 2 / (n * p) for c, p in zip(string.ascii_uppercase, _FREQ))


def index_of_coincidence(text: str) -> float:
    letters = letters_only(text)
    n = len(letters)
    if n < 2:
        return 0.0
    return sum(v * (v - 1) for v in Counter(letters).values()) / (n * (n - 1))


def english_score(text: str) -> float:
    """0..1 'how much does this look like English?' Used to rank candidates."""
    if not text:
        return 0.0
    raw = text.encode("latin-1", errors="replace")
    printable = printable_ratio(raw)
    if printable < 0.8:
        return round(0.1 * printable, 4)

    letters = letters_only(text)
    if len(letters) < 4:
        return round(0.1 * printable, 4)

    # Frequency fit: chi-square per letter is ~0.1 for English, >0.5 otherwise.
    chi_per = chi_square_english(text) / len(letters)
    s_freq = max(0.0, 1.0 - chi_per / 1.2)

    # Word fit: share of tokens that are common English words.
    words = re.findall(r"[a-z]+", text.lower())
    s_words = min(1.0, 2.2 * sum(w in COMMON_WORDS for w in words) / len(words)) if words else 0.0

    # Shape fit: mostly letters and spaces.
    s_shape = sum(c.isalpha() or c == " " for c in text) / len(text)

    return round(printable * (0.45 * s_freq + 0.40 * s_words + 0.15 * s_shape), 4)


# --------------------------------------------------------------------------- #
# Candidates
# --------------------------------------------------------------------------- #
@dataclass
class Candidate:
    method: str
    key: str
    plaintext: str
    score: float
    why: str
    layers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _as_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# --------------------------------------------------------------------------- #
# Encodings (not encryption — just reversible re-spellings of bytes)
# --------------------------------------------------------------------------- #
_HEX_RE = re.compile(r"^(?:0x)?[0-9a-fA-F\s]+$")
_B64_RE = re.compile(r"^[A-Za-z0-9+/=_\-\s]+$")
_B32_RE = re.compile(r"^[A-Z2-7=\s]+$")


def try_hex(s: str) -> bytes | None:
    t = re.sub(r"\s+", "", s)
    if t.lower().startswith("0x"):
        t = t[2:]
    if len(t) < 4 or len(t) % 2 or not _HEX_RE.match(t):
        return None
    try:
        return bytes.fromhex(t)
    except ValueError:
        return None


def try_base32(s: str) -> bytes | None:
    t = re.sub(r"\s+", "", s)
    if len(t) < 8 or not _B32_RE.match(t):
        return None
    try:
        return base64.b32decode(t + "=" * (-len(t) % 8))
    except (binascii.Error, ValueError):
        return None


def try_base64(s: str) -> bytes | None:
    t = re.sub(r"\s+", "", s)
    if len(t) < 8 or not _B64_RE.match(t):
        return None
    # Plain English words can be valid base64 by accident; require some sign
    # it's really base64 (padding, digits/symbols, or mixed case with no vowels-only runs).
    if not (t.endswith("=") or re.search(r"[0-9+/_\-]", t) or (re.search(r"[a-z]", t) and re.search(r"[A-Z]", t))):
        return None
    try:
        alt = "-_" if ("-" in t or "_" in t) else None
        return base64.b64decode(t + "=" * (-len(t) % 4), altchars=alt.encode() if alt else None, validate=True)
    except (binascii.Error, ValueError):
        return None


DECODERS = [("hex", try_hex), ("base32", try_base32), ("base64", try_base64)]


def peel_encodings(data: bytes, max_layers: int = 4) -> tuple[bytes, list[str]]:
    """Repeatedly decode hex/base32/base64 while the result still makes sense."""
    layers: list[str] = []
    current = data
    for _ in range(max_layers):
        if printable_ratio(current) < 0.95:
            break
        text = _as_text(current).strip()
        for name, fn in DECODERS:
            out = fn(text)
            # Accept a decode if it produced readable text OR clearly binary
            # ciphertext (high entropy) — but not short junk.
            if out and len(out) >= 3 and (printable_ratio(out) >= 0.9 or byte_entropy(out) > 3.0):
                layers.append(name)
                current = out
                break
        else:
            break
    return current, layers


# --------------------------------------------------------------------------- #
# Hashes
# --------------------------------------------------------------------------- #
HASH_PATTERNS = [
    (re.compile(r"^\$2[abxy]?\$\d{2}\$[./A-Za-z0-9]{53}$"), "bcrypt"),
    (re.compile(r"^\$6\$[^$]+\$[./A-Za-z0-9]{86}$"), "sha512-crypt"),
    (re.compile(r"^\$5\$[^$]+\$[./A-Za-z0-9]{43}$"), "sha256-crypt"),
    (re.compile(r"^\$1\$[^$]+\$[./A-Za-z0-9]{22}$"), "md5-crypt"),
    (re.compile(r"^[a-fA-F0-9]{32}$"), "md5 (or NTLM)"),
    (re.compile(r"^[a-fA-F0-9]{40}$"), "sha1"),
    (re.compile(r"^[a-fA-F0-9]{56}$"), "sha224"),
    (re.compile(r"^[a-fA-F0-9]{64}$"), "sha256"),
    (re.compile(r"^[a-fA-F0-9]{96}$"), "sha384"),
    (re.compile(r"^[a-fA-F0-9]{128}$"), "sha512"),
]

# Tiny wordlist — enough to show *why* unsalted fast hashes are weak.
WORDLIST = """password 123456 12345678 qwerty abc123 letmein monkey dragon iloveyou admin
welcome login princess sunshine football baseball master shadow trustno1 secret
password1 hello freedom whatever terrapin testudo maryland technica cipher forensics
""".split()


def identify_hash(s: str) -> str | None:
    t = s.strip()
    for rx, name in HASH_PATTERNS:
        if rx.match(t):
            return name
    return None


def dictionary_attack(digest: str) -> tuple[str, str] | None:
    d = digest.strip().lower()
    algos = {32: "md5", 40: "sha1", 56: "sha224", 64: "sha256", 96: "sha384", 128: "sha512"}
    algo = algos.get(len(d))
    if not algo:
        return None
    for w in WORDLIST:
        if hashlib.new(algo, w.encode()).hexdigest() == d:
            return algo, w
    return None


# --------------------------------------------------------------------------- #
# Breakers
# --------------------------------------------------------------------------- #
def caesar_shift(text: str, shift: int) -> str:
    out = []
    for c in text:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + shift) % 26 + 97))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - 65 + shift) % 26 + 65))
        else:
            out.append(c)
    return "".join(out)


def break_caesar(text: str) -> Candidate | None:
    if len(letters_only(text)) < 4:
        return None
    best = max(((s, caesar_shift(text, -s)) for s in range(1, 26)), key=lambda t: english_score(t[1]))
    shift, plain = best
    name = "ROT13" if shift == 13 else f"Caesar shift {shift}"
    return Candidate(
        method="caesar", key=str(shift), plaintext=plain, score=english_score(plain),
        why=f"{name}: tried all 25 shifts; shifting letters back by {shift} gave the most English-like letter distribution.",
    )


def break_single_byte_xor(data: bytes) -> Candidate | None:
    if len(data) < 4:
        return None
    best_key, best_plain, best_score = 0, "", -1.0
    for k in range(1, 256):
        plain = bytes(b ^ k for b in data).decode("latin-1")
        s = english_score(plain)
        if s > best_score:
            best_key, best_plain, best_score = k, plain, s
    return Candidate(
        method="xor", key=f"0x{best_key:02x}", plaintext=best_plain, score=best_score,
        why=f"Single-byte XOR: tried all 255 keys; key 0x{best_key:02x} ('{chr(best_key) if 32 <= best_key < 127 else '?'}') produced the most readable English.",
    )


def kasiski_factors(text: str, top: int = 5) -> list[tuple[int, int]]:
    """Kasiski examination: distances between repeated trigrams share the key length as a factor."""
    letters = letters_only(text)
    positions: dict[str, list[int]] = {}
    for i in range(len(letters) - 2):
        positions.setdefault(letters[i:i + 3], []).append(i)
    factors: Counter[int] = Counter()
    for pos in positions.values():
        for a, b in zip(pos, pos[1:]):
            d = b - a
            for f in range(2, 21):
                if d % f == 0:
                    factors[f] += 1
    return factors.most_common(top)


def estimate_vigenere_key_length(text: str, max_len: int = 20) -> tuple[int, dict[int, float]]:
    letters = letters_only(text)
    iocs: dict[int, float] = {}
    for L in range(1, min(max_len, max(1, len(letters) // 6)) + 1):
        cols = [letters[i::L] for i in range(L)]
        iocs[L] = sum(index_of_coincidence(c) for c in cols) / L
    if not iocs:
        return 1, iocs
    peak = max(iocs.values())
    # Multiples of the true length score as well as the true length, so take
    # the *smallest* length that is close to the best.
    for L in sorted(iocs):
        if iocs[L] >= 0.9 * peak and iocs[L] > 0.055:
            return L, iocs
    return max(iocs, key=iocs.get), iocs


def vigenere_decrypt(text: str, key: str) -> str:
    out, i = [], 0
    shifts = [ord(k) - 65 for k in key.upper()]
    for c in text:
        if c.isalpha() and c.isascii():
            s = shifts[i % len(shifts)]
            base = 65 if c.isupper() else 97
            out.append(chr((ord(c) - base - s) % 26 + base))
            i += 1
        else:
            out.append(c)
    return "".join(out)


def vigenere_encrypt(text: str, key: str) -> str:
    """Used by scripts/plant_demo_case.py to create the demo ciphertext."""
    inverse = "".join(chr((26 - (ord(k) - 65)) % 26 + 65) for k in key.upper())
    return vigenere_decrypt(text, inverse)


def break_vigenere(text: str) -> Candidate | None:
    letters = letters_only(text)
    if len(letters) < 40:
        return None
    L, iocs = estimate_vigenere_key_length(text)
    key = ""
    for i in range(L):
        col = letters[i::L]
        key += min(string.ascii_uppercase, key=lambda k: chi_square_english(caesar_shift(col, -(ord(k) - 65))))
    plain = vigenere_decrypt(text, key)
    kas = kasiski_factors(text)
    kas_note = f" Kasiski repeats also point at factors {[f for f, _ in kas[:3]]}." if kas else ""
    return Candidate(
        method="vigenere", key=key, plaintext=plain, score=english_score(plain),
        why=(f"Vigenère: splitting the text into {L} columns made each column look like English "
             f"(average IoC {iocs.get(L, 0):.3f} vs {IOC_ENGLISH} for English), so the key is {L} letters long."
             f"{kas_note} Frequency analysis on each column recovered the key '{key}'."),
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def stats(data: bytes) -> dict:
    text = _as_text(data)
    return {
        "length": len(data),
        "printable_ratio": round(printable_ratio(data), 3),
        "entropy_bits_per_byte": round(byte_entropy(data), 3),
        "letters": len(letters_only(text)),
        "ioc": round(index_of_coincidence(text), 4),
        "chi_square_vs_english": round(chi_square_english(text), 1) if letters_only(text) else None,
        "english_score": english_score(text),
    }


def identify(data: bytes) -> dict:
    """Rank guesses for what kind of cipher/encoding this is."""
    text = _as_text(data).strip()
    st = stats(data)
    guesses: list[dict] = []

    def add(kind: str, conf: float, reason: str):
        guesses.append({"type": kind, "confidence": round(conf, 2), "reason": reason})

    h = identify_hash(text)
    if h:
        add(f"hash:{h}", 0.95, f"{len(text)} characters of hex/crypt syntax is the exact shape of a {h} digest. Hashes are one-way: they can be guessed, not decrypted.")

    for name, fn in DECODERS:
        out = fn(text)
        if out and (printable_ratio(out) >= 0.9 or byte_entropy(out) > 3.0):
            add(name, 0.9 if name != "hex" or not h else 0.3,
                f"Only uses the {name} alphabet and decodes cleanly to {len(out)} bytes.")

    ioc, letters = st["ioc"], st["letters"]
    if st["printable_ratio"] < 0.85:
        if st["entropy_bits_per_byte"] > 7.5 and len(data) >= 64:
            add("modern encryption or compression", 0.7, f"Entropy is {st['entropy_bits_per_byte']} bits/byte — nearly perfectly random. Classical ciphers can't produce that; AES/ChaCha or zip can.")
        add("xor (binary)", 0.6, "Mostly non-printable bytes with structure — the classic sign of a repeating XOR key.")
    elif letters >= 20:
        L, iocs = estimate_vigenere_key_length(text)
        letter_share = letters / max(1, len(text))
        if st["english_score"] > 0.55:
            add("plaintext", 0.85, "Already reads as English.")
        elif letter_share < 0.5:
            add("xor (single byte)", 0.7,
                f"Printable but only {letter_share:.0%} letters — XOR with a small key tends to turn letters into punctuation.")
        elif ioc < 0.058 and L > 1 and iocs.get(L, 0) > 0.055:
            add("vigenère (polyalphabetic)", 0.85,
                f"IoC is {ioc:.3f} — flatter than English ({IOC_ENGLISH}) — but splitting into {L} columns restores English-like IoC ({iocs[L]:.3f}). That's a {L}-letter Vigenère key.")
        elif ioc >= 0.058:
            add("caesar / monoalphabetic substitution", 0.75,
                f"IoC is {ioc:.3f}, close to English ({IOC_ENGLISH}): letters were swapped one-for-one, so the frequency *shape* survived even though the letters moved.")
        elif ioc >= 0.042:
            add("vigenère (polyalphabetic)", 0.75,
                f"IoC is {ioc:.3f}, between English ({IOC_ENGLISH}) and random ({IOC_RANDOM:.4f}): several alphabets are being mixed, which flattens frequencies — Vigenère's fingerprint.")
        else:
            add("random / strong cipher", 0.5, f"IoC is {ioc:.3f}, close to random ({IOC_RANDOM:.4f}).")
        add("xor (single byte)", 0.2, "Always worth a brute-force: only 255 keys.")

    guesses.sort(key=lambda g: -g["confidence"])
    return {"candidates": guesses, "stats": st}


def crack(data: bytes, top: int = 5) -> dict:
    """Try every breaker (after peeling encodings) and rank by English-likeness."""
    raw_text = _as_text(data).strip()
    cands: list[Candidate] = []

    h = identify_hash(raw_text)
    if h:
        hit = dictionary_attack(raw_text)
        if hit:
            cands.append(Candidate("hash-dictionary", hit[0], hit[1], 1.0,
                                   f"Identified as {hit[0]}; hashing common passwords found '{hit[1]}' produces exactly this digest."))
        else:
            cands.append(Candidate("hash-id", h, "", 0.0,
                                   f"Looks like a {h} digest. It's one-way — only a guessing attack can recover the input, and our small wordlist didn't contain it."))

    if h:  # hashes are one-way: running ciphers on them only produces noise
        return {"best": cands[0].to_dict(), "candidates": [c.to_dict() for c in cands], "stats": stats(data)}

    inner, layers = peel_encodings(data)
    layer_note = (" → ".join(layers) + " decoded, then ") if layers else ""
    inner_text = _as_text(inner)

    if layers:
        cands.append(Candidate("decode", "", inner_text, english_score(inner_text),
                               f"Peeled {len(layers)} encoding layer(s): {' → '.join(layers)}.", list(layers)))

    if printable_ratio(inner) >= 0.85:
        for fn in (break_caesar, break_vigenere):
            c = fn(inner_text)
            if c:
                c.layers = list(layers)
                c.why = layer_note + c.why
                cands.append(c)
    c = break_single_byte_xor(inner)
    if c:
        c.layers = list(layers)
        c.why = layer_note + c.why
        cands.append(c)

    if not layers:
        # Listed first so that, on a tie, "it was never encrypted" wins.
        cands.insert(0, Candidate("plaintext", "", inner_text, english_score(inner_text), "No transformation — scored as-is."))
    # A Vigenère key of all 'A's is the identity — not a real decryption.
    cands = [c for c in cands if not (c.method == "vigenere" and set(c.key) == {"A"})]

    cands.sort(key=lambda c: -c.score)  # stable: ties keep insertion order
    return {"best": cands[0].to_dict() if cands else None, "candidates": [c.to_dict() for c in cands[:top]], "stats": stats(data)}


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #
def identify_findings(data: bytes) -> list[Finding]:
    res = identify(data)
    top = res["candidates"][0] if res["candidates"] else {"type": "unknown", "confidence": 0, "reason": "Too little data to tell."}
    return [Finding(
        stage="crypto", kind="crypto.identify",
        title=f"Looks like: {top['type']}",
        severity=Severity.medium if top["type"] not in ("plaintext", "unknown") else Severity.info,
        summary=top["reason"],
        technical=(f"IoC={res['stats']['ioc']} (English {IOC_ENGLISH}, random {IOC_RANDOM:.4f}); "
                   f"entropy={res['stats']['entropy_bits_per_byte']} bits/byte; printable={res['stats']['printable_ratio']}"),
        data=res,
    )]


def crack_findings(data: bytes) -> list[Finding]:
    res = crack(data)
    best = res["best"]
    if not best or best["score"] < 0.35:
        return [Finding(
            stage="crypto", kind="crypto.unbroken", title="No readable message recovered",
            severity=Severity.low,
            summary="None of the classic ciphers turned this into readable English. It may use modern encryption, which can't be broken by analysis alone.",
            technical=f"Best attempt: {best['method'] if best else 'none'} (score {best['score'] if best else 0}).",
            data=res,
        )]
    solved = best["method"] not in ("plaintext",)
    return [Finding(
        stage="crypto", kind=f"crypto.{best['method']}",
        title="Message decrypted" if solved else "Text is already readable",
        severity=Severity.high if solved else Severity.info,
        summary=(f"Recovered the message: “{best['plaintext'][:140]}{'…' if len(best['plaintext']) > 140 else ''}”"
                 if solved else "This text didn't need decrypting."),
        technical=f"{best['why']} English-likeness score {best['score']:.2f}." + (f" Key: {best['key']}." if best["key"] else ""),
        data=res,
    )]
