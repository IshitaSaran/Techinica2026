import { useEffect, useState } from "react";
import { stegoAnalyze, stegoExtract } from "../api.js";
import FindingList from "./FindingList.jsx";
import UploadDropzone from "./UploadDropzone.jsx";

// Stage 2 — is something hidden in this image? If so, pull it out.
export default function StegoPanel({ learn, announce, file, setFile, onSendToCrypto, headingRef, available }) {
  const [preview, setPreview] = useState("");
  const [state, setState] = useState({ busy: false, error: "", findings: [], plane: null, payload: null });

  useEffect(() => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreview(url);
    setState({ busy: false, error: "", findings: [], plane: null, payload: null });
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const run = async (kind) => {
    setState((s) => ({ ...s, busy: true, error: "" }));
    try {
      if (kind === "analyze") {
        const r = await stegoAnalyze(file);
        setState((s) => ({ ...s, busy: false, findings: r.findings, plane: r.bit_plane_png }));
        announce(r.findings[0]?.summary || "Analysis complete.");
      } else {
        const r = await stegoExtract(file);
        setState((s) => ({ ...s, busy: false, findings: [...s.findings.filter((f) => !["stego.payload", "stego.no_payload"].includes(f.kind)), ...r.findings], payload: r.text ?? r.base64 ?? null }));
        announce(r.findings[0]?.summary || "Extraction complete.");
      }
    } catch (e) {
      setState((s) => ({ ...s, busy: false, error: e.message }));
      announce(`Error: ${e.message}`);
    }
  };

  return (
    <section className="panel" aria-labelledby="s2-h">
      <h2 id="s2-h" tabIndex={-1} ref={headingRef}><span className="step">2</span> Open it: look for hidden data</h2>
      <p className="hint">Images can carry secret data in tiny colour changes your eye can't see. Pick a PNG from Stage 1 or upload one.</p>
      {!available && <p className="note">The steganalysis module isn't installed on this server yet.</p>}
      <UploadDropzone id="s2-upload" label="Choose an image" accept="image/png,image/bmp,image/*" busy={state.busy} onFile={setFile} />

      {file && (
        <div className="evidence">
          <figure>
            <img src={preview} alt={`Evidence under examination: ${file.name}`} />
            <figcaption>{file.name}</figcaption>
          </figure>
          {state.plane && (
            <figure>
              <img src={`data:image/png;base64,${state.plane}`} alt="The image's lowest-bit layer. Smooth regions mean natural data; static-like noise suggests hidden content." />
              <figcaption>Lowest-bit layer (the hiding place)</figcaption>
            </figure>
          )}
        </div>
      )}

      <div className="row">
        <button type="button" disabled={!file || state.busy} onClick={() => run("analyze")}>Analyze for hidden data</button>
        <button type="button" disabled={!file || state.busy} onClick={() => run("extract")}>Extract hidden payload</button>
      </div>
      {state.error && <p className="error" role="alert">{state.error}</p>}

      <FindingList findings={state.findings} learn={learn} render={(f) =>
        f.kind === "stego.payload" && (
          <div className="payload">
            <label htmlFor={`p-${f.id}`}>Recovered payload</label>
            <textarea id={`p-${f.id}`} readOnly rows={4} value={f.data.text ?? f.data.base64} />
            <button type="button" onClick={() => onSendToCrypto(f.data.text ?? f.data.base64)}>Send to Stage 3: crack it →</button>
          </div>
        )
      } />
    </section>
  );
}
