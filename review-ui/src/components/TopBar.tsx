interface TopBarProps {
  filename?: string;
  status?: string;
  onStartOver?: () => void;
}

export function TopBar({ filename, status, onStartOver }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar__brand">
        <span className="top-bar__mark" aria-hidden="true">
          <BrandMark />
        </span>
        <div className="top-bar__wordmark">
          <h1>Candidate Review</h1>
          <span>Resume Parsing &amp; Skill Extraction Engine</span>
        </div>
      </div>
      <div className="top-bar__meta">
        {status && (
          <span className={`confidence-badge confidence-badge--${statusTone(status)}`}>
            {statusLabel(status)}
          </span>
        )}
        {filename && <span className="top-bar__filename">{filename}</span>}
        {onStartOver && (
          <>
            <span className="top-bar__divider" aria-hidden="true" />
            <button
              type="button"
              className="button button--secondary button--small"
              onClick={onStartOver}
            >
              Review another resume
            </button>
          </>
        )}
      </div>
    </header>
  );
}

/**
 * Two overlapping document outlines -- a small, literal nod to the
 * SOURCE <-> PROFILE comparison this product is built around, not a
 * decorative flourish. Plain geometry, no illustration.
 */
function BrandMark() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
      <rect x="4" y="5" width="15" height="19" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <rect
        x="11"
        y="9"
        width="15"
        height="19"
        rx="2"
        fill="var(--color-accent-tint)"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function statusLabel(status: string): string {
  switch (status) {
    case "completed":
      return "Processed";
    case "failed":
      return "Processing failed";
    case "processing":
      return "Processing";
    default:
      return status;
  }
}

function statusTone(status: string): string {
  switch (status) {
    case "completed":
      return "high";
    case "failed":
      return "review";
    default:
      return "unscored";
  }
}
