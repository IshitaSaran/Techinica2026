import { useEffect, useId, useState } from "react";

// Severity is always icon + colour + text label — never colour alone.
const SEVERITY = {
  info: { icon: "ℹ", label: "Info" },
  low: { icon: "◔", label: "Low" },
  medium: { icon: "◑", label: "Medium" },
  high: { icon: "⚠", label: "High" },
};

export default function FindingCard({ finding, learn, children }) {
  const [open, setOpen] = useState(learn);
  const panelId = useId();
  useEffect(() => setOpen(learn), [learn]);
  const sev = SEVERITY[finding.severity] || SEVERITY.info;
  const edu = finding.education || {};

  return (
    <article className={`card sev-${finding.severity}`} aria-labelledby={`${panelId}-t`}>
      <header className="card-head">
        <span className="badge">
          <span aria-hidden="true">{sev.icon}</span> {sev.label}
          <span className="sr-only"> severity</span>
        </span>
        <h3 id={`${panelId}-t`}>{finding.title}</h3>
      </header>
      <p className="summary">{finding.summary}</p>
      {children}
      {finding.technical && (
        <details className="tech">
          <summary>Technical details</summary>
          <p><code>{finding.technical}</code></p>
        </details>
      )}
      <button type="button" className="link" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} How did we find this?
      </button>
      <div id={panelId} hidden={!open} className="edu">
        <dl>
          <dt>What it means</dt><dd>{edu.what}</dd>
          <dt>Why it matters</dt><dd>{edu.why}</dd>
          <dt>How we found it</dt><dd>{edu.how}</dd>
        </dl>
      </div>
    </article>
  );
}
