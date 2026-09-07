import type { RecentCandidate } from "../lib/recentCandidates";

interface RecentCandidatesListProps {
  candidates: RecentCandidate[];
  onOpen: (candidateId: string) => void;
}

function statusTone(status: string): string {
  if (status === "completed") return "high";
  if (status === "failed") return "review";
  return "unscored";
}

export function RecentCandidatesList({ candidates, onOpen }: RecentCandidatesListProps) {
  if (candidates.length === 0) return null;

  return (
    <div className="recent-candidates">
      <div className="recent-candidates__title">Recently opened</div>
      <ul>
        {candidates.map((candidate) => (
          <li key={candidate.candidateId}>
            <button
              type="button"
              className="recent-candidates__item"
              onClick={() => onOpen(candidate.candidateId)}
            >
              <span className="recent-candidates__filename">{candidate.filename}</span>
              <span className={`confidence-badge confidence-badge--${statusTone(candidate.status)}`}>
                <span className="confidence-badge__dot" aria-hidden="true" />
                {candidate.status}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
