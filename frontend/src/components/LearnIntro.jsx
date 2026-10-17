import { INTROS } from "../learnContent.js";

// Learn Mode: a plain-language lesson shown at the top of a stage, before the user acts.
export default function LearnIntro({ stage, children }) {
  const c = INTROS[stage];
  return (
    <aside className="lesson" aria-labelledby={`lesson-${stage}`}>
      <h3 id={`lesson-${stage}`}><span aria-hidden="true">{c.icon} </span>{c.title}</h3>
      {c.body.map((p, i) => <p key={i}>{p}</p>)}
      {children}
    </aside>
  );
}
