import { confidenceLevel, formatConfidence } from "../lib/confidence";

interface ConfidenceBadgeProps {
  confidence: number | null;
  needsReview: boolean | null;
}

const LABELS: Record<string, string> = {
  unscored: "Not scored",
  review: "Needs review",
  medium: "Medium confidence",
  high: "High confidence",
};

/**
 * A quiet dot+label for the routine states (high/medium/unscored) so they
 * don't compete for attention, and a solid filled chip only for "needs
 * review" -- the one state that actually asks the recruiter to act. Never
 * relies on color alone: every badge still carries a text label plus the
 * numeric percentage, so the signal survives for colorblind users and
 * screen readers alike.
 */
export function ConfidenceBadge({ confidence, needsReview }: ConfidenceBadgeProps) {
  const level = confidenceLevel(confidence, needsReview);
  const label = LABELS[level];
  const percent = formatConfidence(confidence);

  return (
    <span className={`confidence-badge confidence-badge--${level}`} title={`${label}: ${percent}`}>
      <span className="confidence-badge__dot" aria-hidden="true" />
      {label}
      {confidence !== null ? ` · ${percent}` : ""}
    </span>
  );
}
