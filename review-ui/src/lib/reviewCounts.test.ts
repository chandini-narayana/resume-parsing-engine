import { describe, expect, it } from "vitest";
import { countNeedsReview, countReviewProgress } from "./reviewCounts";
import { EMPTY_PROVENANCE } from "./evidence";
import type { CandidateProfile } from "../api/types";

function scoredField(needsReview: boolean | null) {
  return { value: "x", confidence: 0.5, needs_review: needsReview, provenance: EMPTY_PROVENANCE, extraction_evidence: null };
}

const baseProfile: CandidateProfile = {
  source_filename: "resume.pdf",
  contact: { full_name: scoredField(true), email: scoredField(false), phone: null, location: null, links: [] },
  skills: [
    { canonical_name: "React", mentions: [], normalization_evidence: null, normalization_confidence: 0.9, needs_review: false },
    { canonical_name: null, mentions: [], normalization_evidence: null, normalization_confidence: 0.2, needs_review: true },
  ],
  experience: [
    {
      job_title: scoredField(true),
      company: scoredField(false),
      start_date: null,
      end_date: null,
      is_current: false,
      provenance: EMPTY_PROVENANCE,
    },
  ],
  education: [],
  parser_warnings: [],
  unclassified_text: [],
};

describe("countNeedsReview", () => {
  it("tallies needs_review flags per section using the server's own flags", () => {
    const counts = countNeedsReview(baseProfile);
    expect(counts.contact).toBe(1);
    expect(counts.skills).toBe(1);
    expect(counts.experience).toBe(1);
    expect(counts.education).toBe(0);
    expect(counts.total).toBe(3);
  });
});

describe("countReviewProgress", () => {
  it("counts every scoreable field, reviewed = total minus flagged", () => {
    // 2 contact + 2 skills + 2 experience + 0 education = 6 scoreable fields, 3 flagged
    const progress = countReviewProgress(baseProfile);
    expect(progress.total).toBe(6);
    expect(progress.reviewed).toBe(3);
  });
});
