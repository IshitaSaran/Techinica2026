import { headline, narrate } from "../learnContent.js";

// Learn Mode: "what's happening right now", a narrative tied to the actual result.
export default function LearnNow({ findings }) {
  const f = headline(findings);
  const text = narrate(f);
  if (!text) return null;
  return (
    <div className="now">
      <p className="now-label"><span aria-hidden="true">💡 </span>What's happening right now</p>
      <p>{text}</p>
      <p className="now-more">Each card below breaks this down into <strong>what</strong> it means, <strong>why</strong> it matters and <strong>how</strong> we found it.</p>
    </div>
  );
}
