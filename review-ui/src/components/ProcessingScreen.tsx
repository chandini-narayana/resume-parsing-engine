import { useEffect, useState } from "react";

interface ProcessingScreenProps {
  fileName: string;
}

/**
 * Upload runs the full pipeline synchronously (see api/routes/resumes.py),
 * so there's no server-reported step-by-step progress to show. An
 * indeterminate spinner plus elapsed time is the honest representation --
 * fabricating fake "Parsing... Extracting... Scoring..." ticks would imply
 * real-time backend progress the API doesn't actually report.
 */
export function ProcessingScreen({ fileName }: ProcessingScreenProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const interval = window.setInterval(() => setElapsedSeconds((seconds) => seconds + 1), 1000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <div className="processing-screen" role="status" aria-live="polite">
      <div className="processing-spinner" aria-hidden="true" />
      <div className="processing-copy">
        <p>
          <strong>{fileName}</strong>
        </p>
        <p>Parsing, extracting, and scoring this resume…</p>
        <p>{elapsedSeconds}s elapsed</p>
      </div>
    </div>
  );
}
