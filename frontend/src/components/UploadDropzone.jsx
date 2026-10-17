import { useState } from "react";

// A real <input type="file"> (keyboard + screen-reader friendly) inside a drag-and-drop zone.
export default function UploadDropzone({ id, label, onFile, accept, busy }) {
  const [over, setOver] = useState(false);
  const pick = (files) => files?.[0] && onFile(files[0]);

  return (
    <div
      className={`drop ${over ? "over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
    >
      <label htmlFor={id}>{label}</label>
      <input id={id} type="file" accept={accept} disabled={busy} onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
      <span className="hint">…or drag and drop it here.</span>
      {busy && <span className="busy" role="progressbar" aria-label="Working">Working…</span>}
    </div>
  );
}
