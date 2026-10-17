import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeFile, health } from "./api.js";
import ModeToggle from "./components/ModeToggle.jsx";
import UploadDropzone from "./components/UploadDropzone.jsx";
import FindingList from "./components/FindingList.jsx";
import SearchPanel from "./components/SearchPanel.jsx";
import StegoPanel from "./components/StegoPanel.jsx";
import CryptoPanel from "./components/CryptoPanel.jsx";
import LearnSandbox from "./components/LearnSandbox.jsx";

export default function App() {
  const [learn, setLearn] = useState(false);
  const [status, setStatus] = useState(null);
  const [announcement, setAnnouncement] = useState("");
  const [evidence, setEvidence] = useState(null); // File handed from Stage 1 to Stage 2
  const [cipher, setCipher] = useState("");       // text handed from Stage 2 to Stage 3
  const [quick, setQuick] = useState({ busy: false, error: "", findings: [] });
  const stegoRef = useRef(null);
  const cryptoRef = useRef(null);

  useEffect(() => {
    health().then(setStatus).catch(() => setStatus({ status: "down" }));
  }, []);

  // Single polite live region: every panel reports through here for screen readers.
  const announce = useCallback((msg) => {
    setAnnouncement("");
    setTimeout(() => setAnnouncement(msg), 50);
  }, []);

  const goTo = (ref) => setTimeout(() => ref.current?.focus(), 50);

  const sendToStego = (file) => {
    setEvidence(file);
    announce(`${file.name} opened in Stage 2.`);
    goTo(stegoRef);
  };
  const sendToCrypto = (text) => {
    setCipher(text);
    announce("Hidden payload sent to Stage 3.");
    goTo(cryptoRef);
  };

  const runQuick = async (file) => {
    setQuick({ busy: true, error: "", findings: [] });
    try {
      const findings = await analyzeFile(file);
      setQuick({ busy: false, error: "", findings });
      announce(`Analysis complete: ${findings.length} findings for ${file.name}.`);
    } catch (e) {
      setQuick({ busy: false, error: e.message, findings: [] });
      announce(`Error: ${e.message}`);
    }
  };

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <div>
          <h1>Sift</h1>
          <p className="tag">Find it → Open it → Crack it. A guided forensic investigation that explains every step.</p>
        </div>
        <div className="top-right">
          <ModeToggle learn={learn} onChange={(v) => { setLearn(v); announce(v ? "Learn mode on. Explanations expanded." : "Report mode on."); }} />
          <ServerStatus status={status} />
        </div>
      </header>

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</div>

      <main id="main">
        <section className="panel" aria-labelledby="quick-h">
          <h2 id="quick-h">Analyze any file</h2>
          <p className="hint">Drop an image or text file. Sift detects the real file type and runs the right checks automatically.</p>
          <UploadDropzone id="quick-upload" label="Choose a file to analyze" onFile={runQuick} busy={quick.busy} />
          {quick.error && <p className="error" role="alert">{quick.error}</p>}
          <FindingList findings={quick.findings} learn={learn} />
        </section>

        <SearchPanel learn={learn} announce={announce} onOpen={sendToStego} available={status?.search_index > 0} />
        <StegoPanel learn={learn} announce={announce} file={evidence} setFile={setEvidence} onSendToCrypto={sendToCrypto} headingRef={stegoRef} available={status?.stego_module !== false} />
        <CryptoPanel learn={learn} announce={announce} text={cipher} setText={setCipher} headingRef={cryptoRef} />
        <LearnSandbox learn={learn} announce={announce} available={status?.stego_module !== false} />
      </main>

      <footer className="foot">
        <p>Built at Technica 2026. Stage 1 runs CLIP embeddings on a Vultr Cloud GPU.</p>
      </footer>
    </>
  );
}

function ServerStatus({ status }) {
  if (!status) return <p className="status">Connecting…</p>;
  if (status.status !== "ok") return <p className="status bad"><span aria-hidden="true">✖ </span>Server unreachable</p>;
  return (
    <p className="status ok">
      <span aria-hidden="true">● </span>Server online · {status.gpu ? "GPU" : "CPU"} · {status.search_index} images indexed
    </p>
  );
}
