import { useEffect, useMemo, useState } from "react";
import { b64ToFile, stegoAnalyze, stegoEmbed, stegoExtract } from "../api.js";
import FindingList from "./FindingList.jsx";
import LearnNow from "./LearnNow.jsx";
import { INTROS } from "../learnContent.js";

// Draw a simple gradient "photo" in the browser so learners don't need their own image.
function makeCanvasImage() {
  return new Promise((resolve) => {
    const c = document.createElement("canvas");
    c.width = 320; c.height = 200;
    const g = c.getContext("2d");
    const grad = g.createLinearGradient(0, 0, 320, 200);
    grad.addColorStop(0, "#2b6cb0"); grad.addColorStop(1, "#f6ad55");
    g.fillStyle = grad; g.fillRect(0, 0, 320, 200);
    g.fillStyle = "#fff"; g.font = "bold 28px sans-serif"; g.fillText("Nothing to see here", 24, 110);
    c.toBlob((b) => resolve(new File([b], "practice.png", { type: "image/png" })), "image/png");
  });
}

// Learn by doing: hide your own message, then watch Sift detect and recover it.
export default function LearnSandbox({ learn, announce, available }) {
  const [message, setMessage] = useState("Meet me at the library at 3pm");
  const [stegoFile, setStegoFile] = useState(null);
  const [findings, setFindings] = useState([]);
  const [recovered, setRecovered] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const stegoUrl = useMemo(() => (stegoFile ? URL.createObjectURL(stegoFile) : ""), [stegoFile]);
  useEffect(() => () => stegoUrl && URL.revokeObjectURL(stegoUrl), [stegoUrl]);

  const step = async (fn) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) { setError(e.message); announce(`Error: ${e.message}`); }
    setBusy(false);
  };

  const hide = () => step(async () => {
    const r = await stegoEmbed(await makeCanvasImage(), message);
    setStegoFile(b64ToFile(r.image_png, "practice-with-secret.png"));
    setFindings([]); setRecovered(null);
    announce(`Hidden ${r.bytes_hidden} bytes. The image looks unchanged. Now run detection.`);
  });
  const detect = () => step(async () => {
    const r = await stegoAnalyze(stegoFile);
    setFindings(r.findings);
    announce(r.findings[0]?.summary || "Detection done.");
  });
  const recover = () => step(async () => {
    const r = await stegoExtract(stegoFile);
    setFindings((f) => [...f, ...r.findings]);
    setRecovered(r.text ?? null);
    announce(r.text === message ? "Success: your exact message was recovered." : "Extraction finished.");
  });

  return (
    <section className="panel sandbox" aria-labelledby="lab-h">
      <h2 id="lab-h"><span aria-hidden="true">🧪 </span>Try it yourself: hide and seek</h2>
      <p className="lead">{INTROS.sandbox.lead}</p>
      {!available && <p className="note">This sandbox needs the steganalysis module on the server.</p>}
      <label htmlFor="secret">Your secret message</label>
      <input id="secret" type="text" maxLength={500} value={message} onChange={(e) => setMessage(e.target.value)} />
      <ol className="steps">
        <li><button type="button" disabled={busy || !message} onClick={hide}>Hide it in a picture</button></li>
        <li><button type="button" disabled={busy || !stegoFile} onClick={detect}>Investigate: is something hidden?</button></li>
        <li><button type="button" disabled={busy || !stegoFile} onClick={recover}>Recover the message</button></li>
      </ol>
      {stegoFile && (
        <figure>
          <img src={stegoUrl} alt="Your practice picture, now carrying your hidden message. It looks identical to the original." />
          <figcaption>
            Looks normal, right? <a href={stegoUrl} download="practice-with-secret.png">Download it</a> and try it in Stage 2.
          </figcaption>
        </figure>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {recovered != null && (
        <p className={recovered === message ? "success" : "note"}>
          <span aria-hidden="true">{recovered === message ? "✔ " : "• "}</span>
          Recovered: “{recovered}” {recovered === message ? "(exact match)" : ""}
        </p>
      )}
      <LearnNow findings={findings} />
      <FindingList findings={findings} learn={learn} />
    </section>
  );
}
