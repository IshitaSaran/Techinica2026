import { useState } from "react";
import { cryptoCrack, cryptoIdentify } from "../api.js";
import FindingList from "./FindingList.jsx";
import LearnIntro from "./LearnIntro.jsx";
import LearnNow from "./LearnNow.jsx";
import { INTROS } from "../learnContent.js";

// Stage 3 — identify the cipher, then break it.
export default function CryptoPanel({ learn, announce, text, setText, headingRef }) {
  const [state, setState] = useState({ busy: false, error: "", findings: [], candidates: [] });

  const run = async (kind) => {
    setState((s) => ({ ...s, busy: true, error: "" }));
    try {
      const r = kind === "identify" ? await cryptoIdentify(text) : await cryptoCrack(text);
      setState({ busy: false, error: "", findings: r.findings, candidates: kind === "crack" ? r.candidates : [] });
      announce(r.findings[0]?.summary || "Done.");
    } catch (e) {
      setState((s) => ({ ...s, busy: false, error: e.message }));
      announce(`Error: ${e.message}`);
    }
  };

  return (
    <section className="panel" aria-labelledby="s3-h">
      <h2 id="s3-h" tabIndex={-1} ref={headingRef}><span className="step">3</span> Crack it: decrypt the message</h2>
      {learn && (
        <LearnIntro stage="crypto">
          {!text.trim() && (
            <button type="button" className="chip" onClick={() => setText(INTROS.crypto.sample)}>{INTROS.crypto.sampleLabel}</button>
          )}
        </LearnIntro>
      )}
      <p className="hint">Paste scrambled text, or send the payload from Stage 2. Sift tries classic ciphers and ranks results by how much they read like English.</p>
      <label htmlFor="ct">Ciphertext</label>
      <textarea id="ct" rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Uryyb jbeyq" />
      <div className="row">
        <button type="button" disabled={!text.trim() || state.busy} onClick={() => run("identify")}>Identify cipher</button>
        <button type="button" disabled={!text.trim() || state.busy} onClick={() => run("crack")}>Crack it</button>
      </div>
      {state.error && <p className="error" role="alert">{state.error}</p>}
      {learn && <LearnNow findings={state.findings} />}
      <FindingList findings={state.findings} learn={learn} render={(f) => f.data?.best?.plaintext && f.severity === "high" && (
        <blockquote className="plain">{f.data.best.plaintext}</blockquote>
      )} />
      {state.candidates.length > 1 && (
        <table className="cands">
          <caption>All attempts, ranked by English-likeness</caption>
          <thead><tr><th scope="col">Method</th><th scope="col">Key</th><th scope="col">Score</th><th scope="col">Output preview</th></tr></thead>
          <tbody>
            {state.candidates.map((c, i) => (
              <tr key={i}>
                <td>{[...(c.layers || []), c.method].join(" → ")}</td>
                <td><code>{c.key || "—"}</code></td>
                <td>{(c.score * 100).toFixed(0)}%</td>
                <td className="preview">{c.plaintext.slice(0, 60)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
