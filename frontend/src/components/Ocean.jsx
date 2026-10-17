import { useEffect, useRef } from "react";

// Decorative under-the-sea layer: rising bubbles + swaying kelp along the bottom.
// Purely visual: aria-hidden, pointer-events: none, sits behind all content.
// Kelp bends away from a nearby cursor via one passive, rAF-throttled mousemove listener.

const BUBBLES = Array.from({ length: 14 }, (_, i) => ({
  left: (i * 37 + 11) % 100,              // deterministic spread across the width
  size: 6 + ((i * 7) % 16),
  dur: 14 + ((i * 5) % 12),
  delay: -((i * 3.7) % 20),               // negative delay: already mid-rise on load
}));

const FRONDS = Array.from({ length: 22 }, (_, i) => ({
  left: (i / 22) * 100 + ((i * 13) % 4),
  h: 70 + ((i * 29) % 80),
  dur: 5 + ((i * 7) % 5),
  delay: -((i * 1.3) % 6),
  shape: i % 3,
  tone: i % 4,
}));

const PATHS = [
  "M20 160 C 8 125, 30 105, 17 75 C 6 50, 28 32, 21 0 C 33 30, 15 52, 26 78 C 37 106, 16 126, 25 160 Z",
  "M20 160 C 12 130, 26 110, 18 85 C 10 60, 26 40, 19 0 C 29 42, 17 62, 24 88 C 31 114, 18 132, 24 160 Z",
  "M18 160 C 6 135, 34 118, 16 90 C 2 66, 30 46, 14 12 C 30 40, 12 68, 25 92 C 38 120, 14 136, 26 160 Z",
];

const REACH = 140;   // px: how close the cursor must be to bend a frond
const MAX_BEND = 16; // degrees

export default function Ocean() {
  const kelpRef = useRef(null);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia?.("(pointer: fine)").matches) return; // touch: sway only
    const fronds = Array.from(kelpRef.current?.querySelectorAll(".frond") || []);
    let frame = 0, mx = -1e4, my = -1e4;

    const apply = () => {
      frame = 0;
      const zoneTop = window.innerHeight - 220;
      for (const el of fronds) {
        const x = (parseFloat(el.dataset.left) / 100) * window.innerWidth;
        const dx = x - mx;
        const near = my > zoneTop && Math.abs(dx) < REACH;
        const bend = near ? Math.sign(dx || 1) * (1 - Math.abs(dx) / REACH) * MAX_BEND : 0;
        const next = `${bend.toFixed(1)}deg`;
        if (el.style.getPropertyValue("--push") !== next) el.style.setProperty("--push", next);
      }
    };
    const onMove = (e) => {
      mx = e.clientX; my = e.clientY;
      if (!frame) frame = requestAnimationFrame(apply);
    };
    const onLeave = () => { mx = my = -1e4; if (!frame) frame = requestAnimationFrame(apply); };

    window.addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseleave", onLeave);
    return () => {
      window.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="ocean" aria-hidden="true">
      <div className="rays" />
      {BUBBLES.map((b, i) => (
        <span key={i} className="bubble"
          style={{ left: `${b.left}%`, width: b.size, height: b.size, animationDuration: `${b.dur}s`, animationDelay: `${b.delay}s` }} />
      ))}
      <div className="kelp" ref={kelpRef}>
        {FRONDS.map((f, i) => (
          <div key={i} className={`frond tone-${f.tone}`} data-left={f.left}
            style={{ left: `${f.left}%`, height: f.h }}>
            <svg className="frond-sway" viewBox="0 0 40 160" preserveAspectRatio="none"
              style={{ animationDuration: `${f.dur}s`, animationDelay: `${f.delay}s` }}>
              <path d={PATHS[f.shape]} />
            </svg>
          </div>
        ))}
      </div>
    </div>
  );
}
