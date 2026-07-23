import './Placeholder.css';

interface PlaceholderProps {
  title: string;
  description: string;
  phase: string;
}

export function Placeholder({ title, description, phase }: PlaceholderProps) {
  return (
    <div className="placeholder-page">
      <div className="placeholder-content">
        <span className="phase-badge">Coming in Phase {phase}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </div>
  );
}
