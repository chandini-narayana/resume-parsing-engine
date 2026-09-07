import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge } from "./ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("labels an unscored field without inventing a percentage", () => {
    render(<ConfidenceBadge confidence={null} needsReview={null} />);
    expect(screen.getByText(/Not scored/)).toBeInTheDocument();
  });

  it("flags a needs_review field regardless of its numeric confidence", () => {
    render(<ConfidenceBadge confidence={0.9} needsReview={true} />);
    expect(screen.getByText(/Needs review/)).toBeInTheDocument();
  });

  it("shows the percentage alongside the label, not color alone", () => {
    render(<ConfidenceBadge confidence={0.92} needsReview={false} />);
    expect(screen.getByText(/92%/)).toBeInTheDocument();
  });
});
