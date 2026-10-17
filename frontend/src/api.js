// Thin fetch wrappers for the Sift backend.
// VITE_API_BASE_URL = the Vultr backend, e.g. http://203.0.113.10:8000 (empty in dev: Vite proxies /api).
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch {
    throw new Error("Can't reach the Sift server. Check that the backend is running.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

const form = (fields) => {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) if (v != null) fd.append(k, v);
  return { method: "POST", body: fd };
};

export const health = () => request("/api/health");
export const analyzeFile = (file) => request("/api/analyze", form({ file }));

export const stegoAnalyze = (file) => request("/api/stego/analyze", form({ file }));
export const stegoExtract = (file) => request("/api/stego/extract", form({ file }));
export const stegoEmbed = (file, message) => request("/api/stego/embed", form({ file, message }));

export const cryptoIdentify = (text) => request("/api/crypto/identify", form({ text }));
export const cryptoCrack = (text) => request("/api/crypto/crack", form({ text }));

export const searchText = (text, k = 12) =>
  request("/api/search/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, k }),
  });
export const searchImage = (file, k = 12) => request("/api/search/by-image", form({ file, k }));

export const imageUrl = (filename) => `${API_BASE}/api/images/${encodeURIComponent(filename)}`;

// Fetch an evidence image from the server as a File so it can be re-uploaded to Stage 2.
export async function fetchEvidence(filename) {
  const res = await fetch(imageUrl(filename));
  if (!res.ok) throw new Error(`Couldn't load ${filename}`);
  const blob = await res.blob();
  return new File([blob], filename, { type: blob.type });
}

export const b64ToFile = (b64, name, type = "image/png") => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new File([bytes], name, { type });
};
