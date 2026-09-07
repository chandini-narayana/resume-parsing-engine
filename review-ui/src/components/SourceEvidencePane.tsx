import { useEffect, useRef } from "react";
import type { CandidateProfile } from "../api/types";
import { collectEvidence } from "../lib/evidence";
import { EmptyState } from "./EmptyState";

interface SourceEvidencePaneProps {
  profile: CandidateProfile;
  activeKeys: string[];
}

/**
 * The API has no endpoint to fetch or render the original PDF/DOCX bytes
 * (see the "known limitations" note in the review README) -- this pane
 * reconstructs the "source" half of the source <-> profile comparison from
 * the provenance text every extracted field already carries, grouped by
 * the section segmentation assigned it. Hovering or expanding evidence on
 * a profile field scrolls and highlights the matching block(s) here.
 */
export function SourceEvidencePane({ profile, activeKeys }: SourceEvidencePaneProps) {
  const bySection = collectEvidence(profile);
  const blockRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  useEffect(() => {
    if (activeKeys.length === 0) return;
    const el = blockRefs.current.get(activeKeys[0]);
    if (!el) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  }, [activeKeys]);

  return (
    <>
      <div className="pane__heading pane__heading--source">
        <h2>Source evidence</h2>
        <span>{profile.source_filename}</span>
      </div>
      {bySection.size === 0 ? (
        <EmptyState message="No captured source text is available for this resume." />
      ) : (
        [...bySection.entries()].map(([section, blocks]) => (
          <div className="evidence-group" key={section}>
            <div className="evidence-group__title">{section}</div>
            {blocks.map((block) => (
              <div
                key={block.key}
                ref={(el) => {
                  if (el) blockRefs.current.set(block.key, el);
                  else blockRefs.current.delete(block.key);
                }}
                className={`evidence-block${activeKeys.includes(block.key) ? " evidence-block--active" : ""}`}
              >
                {block.pageNumber !== null && (
                  <div className="evidence-block__page">Page {block.pageNumber}</div>
                )}
                {block.text}
              </div>
            ))}
          </div>
        ))
      )}
    </>
  );
}
