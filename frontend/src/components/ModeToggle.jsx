// Report Mode shows findings; Learn Mode expands every "How did we find this?" panel.
export default function ModeToggle({ learn, onChange }) {
  return (
    <div className="mode" role="group" aria-label="Display mode">
      <button type="button" aria-pressed={!learn} onClick={() => onChange(false)}>
        <span aria-hidden="true">📋 </span>Report mode
      </button>
      <button type="button" aria-pressed={learn} onClick={() => onChange(true)}>
        <span aria-hidden="true">🎓 </span>Learn mode
      </button>
    </div>
  );
}
