# Sift — guided digital-forensics investigations

**Find it → Open it → Crack it.** Sift runs a real forensic pipeline on uploaded evidence and explains every finding in plain language.

1. **Find it.** Search 500+ seized images by describing them ("a laptop on a desk"). CLIP embeddings are built on a **Vultr Cloud GPU**.
2. **Open it.** Steganalysis checks the suspicious image for hidden data and pulls the payload out.
3. **Crack it.** Cryptanalysis identifies the cipher (Index of Coincidence, frequency analysis) and breaks it (Caesar/ROT, XOR, Vigenère, base64/32/hex, hashes).

Every result is a **Finding** with a severity (icon + colour + text), a one-line plain summary, the technical detail, and a "How did we find this?" panel. Learn Mode expands all the panels and adds a hide-and-seek sandbox.

---

## Repo layout

```
backend/   FastAPI app
  main.py              app, CORS, /api/health, startup cache load
  core/                forensic engines (findings, crypto, clip_search, explain, stego*)
  routers/             analyze (magic-byte dispatcher), stego, crypto, search
  scripts/             fetch_sample_images, build_embeddings, plant_demo_case
  data/                sample_images/, embeddings.npy, embeddings_index.json (generated, git-ignored)
frontend/  React + Vite (deploys to Vercel)
```

\* **`backend/core/stego.py` is not in the repo yet.** The Stage 2 routes, the Learn sandbox and `plant_demo_case.py` are wired to it. Until it exists they answer `501` and show a "module not installed" finding; everything else runs. The interface it must provide is documented at the top of [backend/routers/stego.py](backend/routers/stego.py):

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

## Deploy: Vultr backend + Vercel frontend

Deploy a hello-world of both early (hour 2), not at hour 23.

### Cost plan for the $100 MLH credit

| instance | runs | when |
|---|---|---|
| **CPU**: Vultr Cloud Compute, regular, 2 vCPU / 4 GB is plenty | FastAPI, crypto, stego, cached CLIP search | the whole hack |
| **GPU**: Vultr Cloud GPU, smallest/fractional plan | `build_embeddings.py` only | about 20 minutes, then **destroy** |

Search only needs the cached `embeddings.npy` (a single matrix multiply) plus a text embed, which takes about 300 ms on CPU. So **the live demo runs entirely on the cheap CPU box.** The GPU is the headline workload, not a runtime dependency. Check current hourly prices on Vultr's pricing page before launching the GPU.

### 1. CPU instance (always on)

Create it in the Vultr dashboard: Cloud Compute, Ubuntu 24.04, any region near you, and add your SSH key. Then:

```bash
ssh root@CPU_IP
apt update && apt install -y python3-venv python3-pip git libjpeg-dev zlib1g-dev
git clone https://github.com/YOU/Techinica2026.git /opt/sift && cd /opt/sift/backend
python3 -m venv .venv && . .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/fetch_sample_images.py --count 520

export SIFT_CORS_ORIGINS="https://YOUR-APP.vercel.app,http://localhost:5173"
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Firewall:** In Vultr, go to *Network → Firewall → Add group*, add an inbound rule for TCP 8000 (plus 80 and 443 for HTTPS below), and attach the group to the instance. If `ufw` is active, also run `ufw allow 8000,80,443/tcp`.

Check from your laptop: `curl http://CPU_IP:8000/api/health`. It reports `"gpu": false` on this box, which is expected.

**Keep it running after you log out** with `/etc/systemd/system/sift.service`:

```ini
[Unit]
Description=Sift API
After=network.target
[Service]
WorkingDirectory=/opt/sift/backend
Environment=SIFT_CORS_ORIGINS=https://YOUR-APP.vercel.app
ExecStart=/opt/sift/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
[Install]
WantedBy=multi-user.target
```

Then run `systemctl daemon-reload && systemctl enable --now sift`.

**HTTPS (needed for Vercel).** A page served over HTTPS can't call `http://IP:8000`, because browsers block it as mixed content. A free fix that needs no domain is Caddy plus sslip.io:

```bash
apt install -y caddy
echo 'CPU-IP-WITH-DASHES.sslip.io {
  reverse_proxy 127.0.0.1:8000
}' > /etc/caddy/Caddyfile        # e.g. 203-0-113-10.sslip.io
systemctl restart caddy
```

Your API is now `https://CPU-IP-WITH-DASHES.sslip.io`. Caddy fetches the certificate automatically.

### 2. GPU instance (on demand, destroy right after)

In the Vultr dashboard, choose *Cloud GPU*, the smallest NVIDIA plan, and an Ubuntu image with NVIDIA drivers. Then:

```bash
ssh root@GPU_IP
nvidia-smi                                   # confirm the GPU is visible
apt update && apt install -y python3-venv git
git clone https://github.com/YOU/Techinica2026.git sift && cd sift/backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt              # default torch wheel includes CUDA
python scripts/fetch_sample_images.py --count 520
python scripts/build_embeddings.py           # prints "...on cuda (NVIDIA ...)"
scp data/embeddings.npy data/embeddings_index.json root@CPU_IP:/opt/sift/backend/data/
```

> **Destroy the GPU instance now.** Stopping it isn't enough, because Vultr bills stopped instances. Use *Server → Destroy*. The cached embeddings are all search needs.

Back on the CPU box, run `systemctl restart sift`. `/api/health` should now show `"search_index": 545, "search_built_on": "cuda"`. Then plant the demo case (see above) and restart again.

### 3. Frontend on Vercel

1. In Vercel, *Add New Project*, import the repo and set **Root Directory = `frontend`**. The Vite preset is detected automatically (build `npm run build`, output `dist`).
2. Under *Environment Variables*, set `VITE_API_BASE_URL = https://CPU-IP-WITH-DASHES.sslip.io` (no trailing slash).
3. Deploy, then put the Vercel URL into `SIFT_CORS_ORIGINS` on the backend and restart it. For preview deploys, also set `SIFT_CORS_REGEX`.

### 4. Teardown

- Destroy the GPU instance as soon as embeddings are copied.
- After judging, destroy the CPU instance and delete the firewall group and any snapshots. MLH credits expire after 30 days, so don't leave anything idling.

---

## How Sift maps to each track (reusable for Devpost)

**Cipher Tech: Best Digital Forensics Hack.** Sift does real forensic analysis rather than mock-ups. Uploaded evidence is identified by magic bytes, not file extension. Images go through LSB steganalysis (entropy, chi-square on the low bit plane, bit-plane visualisation) and payload recovery. Recovered data feeds straight into a cryptanalysis engine. It uses Index of Coincidence and frequency analysis to identify the cipher, then breaks Caesar/ROT, single-byte XOR and Vigenère (key length from IoC plus Kasiski, then per-column frequency analysis), peels base64/base32/hex layers, and identifies and dictionary-attacks unsalted hashes. Every candidate decryption is ranked by an English-likeness score, with a human-readable reason.

**MLH: Best Use of Vultr.** Stage 1 is semantic search across 500+ seized images using OpenCLIP (ViT-B/32), and the corpus is embedded on a Vultr Cloud GPU. The architecture is deliberately cost-aware. The GPU does the heavy batch embedding once and is then destroyed. A small Vultr Cloud Compute instance serves the cached embedding matrix, so each live query is a single text embed plus a matrix multiply. `/api/health` reports which device built the index.

**Technica: Best Education Hack / A Sea for All (Accessibility).** Each finding has three layers: a plain-language summary anyone can read, the technical detail for experts, and a "What / Why / How" explanation. Learn Mode opens all the explanations and adds a hide-and-seek sandbox. Learners hide their own message in a picture, then switch roles and watch the tool detect and recover it. The UI is screen-reader-first. It uses semantic landmarks and headings, an `aria-live` region that announces every result, labelled inputs, full keyboard navigation with visible focus, focus moved to the next stage when evidence is handed off, alt text on every image (including the bit-plane view), and severity that is never shown by colour alone. It also respects light/dark mode and reduced motion.
