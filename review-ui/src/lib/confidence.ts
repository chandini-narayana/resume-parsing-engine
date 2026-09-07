export type ConfidenceLevel = "unscored" | "review" | "medium" | "high";

/**
 * Purely a display bucket. The authoritative "does this need a recruiter's
 * eyes" signal is always the server's own `needs_review` flag (see
 * ConfidenceBadge) -- this only decides medium vs. high once a field is
 * already known not to need review, so the UI never invents its own
 * threshold logic that could drift from
 * confidence/scorer.py's ConfidenceConfig.review_threshold.
 */
export function confidenceLevel(confidence: number | null, needsReview: boolean | null): ConfidenceLevel {
  if (confidence === null) return "unscored";
  if (needsReview) return "review";
  return confidence >= 0.85 ? "high" : "medium";
}

export function formatConfidence(confidence: number | null): string {
  if (confidence === null) return "Not scored";
  return `${Math.round(confidence * 100)}%`;
}
