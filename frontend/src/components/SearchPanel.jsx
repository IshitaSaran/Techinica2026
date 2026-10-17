import { useState } from "react";
import { fetchEvidence, imageUrl, searchImage, searchText } from "../api.js";
import FindingList from "./FindingList.jsx";
import UploadDropzone from "./UploadDropzone.jsx";
import LearnIntro from "./LearnIntro.jsx";
import LearnNow from "./LearnNow.jsx";
import { INTROS } from "../learnContent.js";

// Stage 1 — find the needle in 500+ seized images by describing it.
export default function SearchPanel({ learn, announce, onOpen, available }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ busy: false, error: "", findings: [], matches: [] });

  const run = async (fn, label) => {
    setState((s) => ({ ...s, busy: true, error: "" }));
    try {
      const res = await fn();
      setState({ busy: false, error: "", findings: res.findings, matches: res.matches });
      announce(`${res.matches.length} matches for ${label}. Top match ${res.matches[0]?.filename}.`);
    } catch (e) {
      setState((s) => ({ ...s, busy: false, error: e.message }));
      announce(`Search error: ${e.message}`);
    }
  };

  const open = async (filename) => {
    try { onOpen(await fetchEvidence(filename)); } catch (e) { announce(e.message); }
  };

  return (
    <section className="panel" aria-labelledby="s1-h">
      <h2 id="s1-h"><span className="step">1</span> Find it: search the evidence</h2>
      {learn && (
        <LearnIntro stage="search">
          <p className="try">{INTROS.search.tryIt}</p>
          <ul className="chips" aria-label="Example searches">
            {INTROS.search.examples.map((ex) => (
              <li key={ex}><button type="button" className="chip" onClick={() => setQuery(ex)}>{ex}</button></li>
            ))}
          </ul>
        </LearnIntro>
      )}
      <p className="hint">Describe what you're looking for in plain words. AI ranks every image by meaning, not by filename.</p>
      {available === false && <p className="note">The search index isn't built on this server yet.</p>}
      <form className="row" onSubmit={(e) => { e.preventDefault(); query.trim() && run(() => searchText(query.trim()), query); }}>
        <label htmlFor="q" className="sr-only">Describe the image</label>
        <input id="q" type="search" placeholder='e.g. "a laptop on a desk", "handwritten note"' value={query} onChange={(e) => setQuery(e.target.value)} />
        <button type="submit" disabled={state.busy}>{state.busy ? "Searching…" : "Search"}</button>
      </form>
      <details className="alt">
        <summary>Or search with an example image</summary>
        <UploadDropzone id="s1-img" label="Choose an example image" accept="image/*" busy={state.busy}
          onFile={(f) => run(() => searchImage(f), `image ${f.name}`)} />
      </details>
      {state.error && <p className="error" role="alert">{state.error}</p>}

      {learn && <LearnNow findings={state.findings} />}
      <FindingList findings={state.findings} learn={learn} />
      {state.matches.length > 0 && (
        <ol className="grid" aria-label="Search results, best match first">
          {state.matches.map((m) => (
            <li key={m.filename} className="thumb">
              <img src={imageUrl(m.filename)} alt={`Evidence image ${m.filename}, rank ${m.rank}`} loading="lazy" />
              <div className="thumb-meta">
                <span>#{m.rank} · {m.filename}</span>
                <span>match {(m.score * 100).toFixed(1)}%</span>
              </div>
              <button type="button" onClick={() => open(m.filename)}>Open in Stage 2<span className="sr-only">: {m.filename}</span></button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
