# Sift — guided digital-forensics investigations

**Find it → Open it → Crack it.** Sift runs a real forensic pipeline on uploaded evidence and explains every finding in plain language.

1. **Find it.** Search 500+ seized images by describing them ("a laptop on a desk"). CLIP embedding is GPU-capable (the kind of job **Vultr Cloud GPUs** are built for), but embeddings are precomputed and cached, so the live service runs CPU-only on **Vultr**.
2. **Open it.** Steganalysis checks the suspicious image for hidden data and pulls the payload out.
3. **Crack it.** Cryptanalysis identifies the cipher (Index of Coincidence, frequency analysis) and breaks it (Caesar/ROT, XOR, Vigenère, base64/32/hex, hashes).

Every result is a **Finding** with a severity (icon + colour + text), a one-line plain summary, the technical detail, and a "How did we find this?" panel. Learn Mode expands all the panels and adds a hide-and-seek sandbox.

---

## Repo layout

```
backend/   FastAPI app
  main.py              app, CORS, /api/health, startup cache load
  core/                forensic engines (findings, stego, crypto, clip_search, explain)
  routers/             analyze (magic-byte dispatcher), stego, crypto, search
  scripts/             fetch_sample_images, build_embeddings, plant_demo_case
  data/                sample_images/, embeddings.npy, embeddings_index.json (generated, git-ignored)
frontend/  React + Vite (deploys to Vercel)
```

**`backend/core/stego.py`** is the Stage 2 LSB steganography module. It powers the Stage 2 routes, the Learn sandbox and `plant_demo_case.py`. Its interface is documented at the top of [backend/routers/stego.py](backend/routers/stego.py):

| function | returns |
|---|---|
| `analyze(image_bytes)` | `dict` of statistics plus `reading: str` (plain-language) and `suspicious: bool` |
| `extract(image_bytes)` | `{recovered: bytes, as_text: str \| None, confidence: float}` |
| `bit_plane_image(image_bytes)` | PNG `bytes` of the LSB plane |
| `embed(image_bytes, message: bytes)` | PNG `bytes`, readable by `extract` |

`/api/health` reports `stego_module: true/false`.

---

## Run locally

**Backend** (Python 3.10+):

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # small CPU build
pip install -r requirements.txt

python scripts/fetch_sample_images.py --count 520   # ~545 real photos into data/sample_images
python scripts/build_embeddings.py                  # ~15 s on a laptop CPU, seconds on a GPU
uvicorn main:app --reload --port 8000
```

Check: `curl localhost:8000/api/health` should return `{"status":"ok","gpu":false,"search_index":545,...}`. API docs are at http://localhost:8000/docs.

**Frontend:**

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  (/api is proxied to :8000)
```

**Stage the demo case** (needs `core/stego.py`):

```bash
cd backend
python scripts/plant_demo_case.py --query "a laptop on a desk"
```

This Vigenère-encrypts a note (key `TERRAPIN`), base64-encodes it and hides it in the top search match. It then re-saves that image as PNG, updates the index and verifies the whole chain. The answer key goes to `data/demo_case.json`.

---

## Deployment

### Architecture

```
Browser ──HTTPS──▶ Vercel: React + Vite static build (frontend/)
                     │  fetch(VITE_API_BASE_URL + "/api/…")
                     ▼
Vultr Ubuntu ── Caddy :443 (TLS for the sslip.io hostname)
                     │  reverse_proxy
                     ▼
                 uvicorn 0.0.0.0:8000 (FastAPI, systemd service "sift")
                   ├─ Stage 2/3: stego + crypto (Pillow/numpy, pure Python)
                   └─ Stage 1: CLIP search: data/embeddings.npy loaded once at startup,
                      each query = one CPU text embed (~0.3 s) + a matrix multiply
```

The runtime is **CPU-only**. CLIP image embeddings are computed ahead of time by `scripts/build_embeddings.py` and cached on disk, so serving never needs a GPU.

### Live URLs

| | |
|---|---|
| Frontend (Vercel) | https://techinica2026-7ir40lzno-ishitasaran123-3498s-projects.vercel.app |
| Backend API (Vultr + Caddy) | https://64-176-214-27.sslip.io (health check: [`/api/health`](https://64-176-214-27.sslip.io/api/health)) |
| Server | Vultr Ubuntu instance, public IP `64.176.214.27` |

### 1. Backend setup (on the Vultr instance)

```bash
ssh root@64.176.214.27
apt update && apt install -y python3 python3-venv python3-pip git
git clone https://github.com/IshitaSaran/Techinica2026.git /opt/sift
cd /opt/sift/backend
python3 -m venv .venv && . .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

python scripts/fetch_sample_images.py --count 520                # evidence photos (git-ignored)
python scripts/build_embeddings.py                               # -> data/embeddings.npy + embeddings_index.json
python scripts/plant_demo_case.py --query "a laptop on a desk"   # hides the encrypted note; prints "Chain verified ✔"
```

### 2. Run as the `sift` systemd service

```bash
cat > /etc/systemd/system/sift.service <<'EOF'
[Unit]
Description=Sift API (FastAPI / uvicorn)
After=network.target

[Service]
WorkingDirectory=/opt/sift/backend
Environment=SIFT_CORS_ORIGINS=https://techinica2026-7ir40lzno-ishitasaran123-3498s-projects.vercel.app
# SIFT_CORS_REGEX defaults to https://.*\.vercel\.app in main.py, so it isn't set here.
ExecStart=/opt/sift/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now sift
systemctl status sift --no-pager
curl http://127.0.0.1:8000/api/health
```

### 3. Firewall (ufw)

```bash
ufw allow OpenSSH            # allow SSH before enabling, or you'll lock yourself out
ufw allow 8000/tcp           # direct API access (optional once Caddy is up)
ufw allow 80/tcp             # Let's Encrypt HTTP challenge
ufw allow 443/tcp            # HTTPS
ufw enable && ufw status
```

If the instance has a Vultr firewall group attached, open the same ports there too.

### 4. HTTPS with Caddy + sslip.io

The Vercel site is served over HTTPS, so browsers block calls to a plain `http://IP:8000` backend as mixed content. sslip.io maps `64-176-214-27.sslip.io` to `64.176.214.27`, which gives Caddy a hostname it can get a free certificate for. No domain purchase is needed.

```bash
apt install -y caddy
cat > /etc/caddy/Caddyfile <<'EOF'
64-176-214-27.sslip.io {
    reverse_proxy 127.0.0.1:8000
}
EOF
systemctl restart caddy
curl https://64-176-214-27.sslip.io/api/health
# -> {"status":"ok","gpu":false,"device":"cpu","search_index":545,...,"stego_module":true,"stego_missing":[]}
```

### 5. Frontend on Vercel

- Import the repo and set **Root Directory = `frontend`**. The Vite preset is detected automatically (`npm run build` → `dist`).
- Set the environment variable `VITE_API_BASE_URL=https://64-176-214-27.sslip.io` (no trailing slash).
- Redeploy after changing it, because Vite bakes the value into the build.

### CORS environment variables

| Variable | Live value | Default if unset (`backend/main.py`) |
|---|---|---|
| `SIFT_CORS_ORIGINS` | `https://techinica2026-7ir40lzno-ishitasaran123-3498s-projects.vercel.app` | `http://localhost:5173,http://127.0.0.1:5173` |
| `SIFT_CORS_REGEX` | `https://.*\.vercel\.app` | `https://.*\.vercel\.app` (set to empty to disable) |

Origins are fullmatched, no credentials are allowed, and the API uses no cookies. A fresh clone therefore works with any Vercel deployment and the local Vite dev server without extra config.

### Updating the live server

```bash
cd /opt/sift && git pull && systemctl restart sift
```

`data/` (photos, embeddings, the planted image and `demo_case.json`) is git-ignored, so a pull never overwrites it. Re-run step 1's scripts only if you want to rebuild the index or re-plant the demo case.

### Optional: build the index on a Vultr Cloud GPU, then tear down

On a Cloud GPU instance, run the same step 1 commands but use the default CUDA wheels (`pip install -r requirements.txt` without the CPU index URL). Then copy the index across with `scp data/embeddings.npy data/embeddings_index.json root@64.176.214.27:/opt/sift/backend/data/` and **destroy** the GPU instance. Vultr bills stopped instances, so stopping isn't enough. After judging, destroy the CPU instance too, so the MLH credits (30-day expiry) aren't wasted.

---

## How Sift maps to each track (reusable for Devpost)

**Cipher Tech: Best Digital Forensics Hack.** Sift does real forensic analysis rather than mock-ups. Uploaded evidence is identified by magic bytes, not file extension. Images go through LSB steganalysis (entropy, chi-square on the low bit plane, bit-plane visualisation) and payload recovery. Recovered data feeds straight into a cryptanalysis engine. It uses Index of Coincidence and frequency analysis to identify the cipher, then breaks Caesar/ROT, single-byte XOR and Vigenère (key length from IoC plus Kasiski, then per-column frequency analysis), peels base64/base32/hex layers, and identifies and dictionary-attacks unsalted hashes. Every candidate decryption is ranked by an English-likeness score, with a human-readable reason.

**MLH: Best Use of Vultr.** Stage 1 is semantic search across 500+ seized images using OpenCLIP (ViT-B/32). Batch CLIP embedding is GPU-accelerated: `build_embeddings.py` uses CUDA automatically when it's available, which is the job Vultr Cloud GPUs are made for. The architecture is deliberately cost-aware, though. Embeddings are computed once and cached to disk, so the live service runs CPU-only on a Vultr compute instance. Each query is a single text embed plus a matrix multiply, about 0.3 s on CPU. `/api/health` reports the runtime device and which device built the index.

**Technica: Best Education Hack / A Sea for All (Accessibility).** Each finding has three layers: a plain-language summary anyone can read, the technical detail for experts, and a "What / Why / How" explanation. Learn Mode opens all the explanations and adds a hide-and-seek sandbox. Learners hide their own message in a picture, then switch roles and watch the tool detect and recover it. The UI is screen-reader-first. It uses semantic landmarks and headings, an `aria-live` region that announces every result, labelled inputs, full keyboard navigation with visible focus, focus moved to the next stage when evidence is handed off, alt text on every image (including the bit-plane view), and severity that is never shown by colour alone. It also respects light/dark mode and reduced motion.
