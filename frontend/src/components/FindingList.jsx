import FindingCard from "./FindingCard.jsx";

export default function FindingList({ findings, learn, render }) {
  if (!findings?.length) return null;
  return (
    <div className="findings">
      {findings.map((f) => (
        <FindingCard key={f.id} finding={f} learn={learn}>
          {render?.(f)}
        </FindingCard>
      ))}
    </div>
  );
}
