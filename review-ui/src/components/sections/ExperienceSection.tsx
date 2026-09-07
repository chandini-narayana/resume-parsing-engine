import type { ExperienceEntry, CorrectionResponse } from "../../api/types";
import { EditableField } from "../EditableField";
import { EmptyState } from "../EmptyState";
import { scoredFieldPath } from "../../api/fieldPath";
import { EMPTY_PROVENANCE } from "../../lib/evidence";
import { correctionNoteFor } from "./shared";

interface ExperienceSectionProps {
  experience: ExperienceEntry[];
  corrections: Record<string, CorrectionResponse>;
  onSubmitCorrection: (fieldPath: string, correctedValue: string) => Promise<void>;
  onFocusEvidence: (keys: string[]) => void;
}

export function ExperienceSection({
  experience,
  corrections,
  onSubmitCorrection,
  onFocusEvidence,
}: ExperienceSectionProps) {
  return (
    <section className="profile-section" aria-labelledby="section-experience">
      <h2 className="profile-section__title" id="section-experience" tabIndex={-1}>
        Experience
      </h2>
      {experience.length === 0 && <EmptyState message="No experience entries extracted." />}
      {experience.map((entry, index) => {
        const base = `experience[${index}]`;
        const rows = [
          { label: "Job title", fieldBase: `${base}.job_title`, field: entry.job_title },
          { label: "Company", fieldBase: `${base}.company`, field: entry.company },
          { label: "Start date", fieldBase: `${base}.start_date`, field: entry.start_date },
          { label: "End date", fieldBase: `${base}.end_date`, field: entry.end_date },
        ];
        return (
          <div className="entry-card" key={base}>
            <div className="entry-card__header">
              <h3>
                {entry.job_title?.value ?? "Untitled role"}
                {entry.is_current ? " · Current" : ""}
              </h3>
            </div>
            {rows.map(({ label, fieldBase, field }) => {
              const path = scoredFieldPath(fieldBase);
              return (
                <EditableField
                  key={path}
                  fieldPath={path}
                  label={label}
                  value={field?.value ?? null}
                  confidence={field?.confidence ?? null}
                  needsReview={field?.needs_review ?? null}
                  provenance={field?.provenance ?? EMPTY_PROVENANCE}
                  correctionNote={correctionNoteFor(corrections, path)}
                  onSubmitCorrection={onSubmitCorrection}
                  onFocusEvidence={onFocusEvidence}
                />
              );
            })}
          </div>
        );
      })}
    </section>
  );
}
