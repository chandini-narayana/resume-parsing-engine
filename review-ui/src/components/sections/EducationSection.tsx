import type { EducationEntry, CorrectionResponse } from "../../api/types";
import { EditableField } from "../EditableField";
import { EmptyState } from "../EmptyState";
import { scoredFieldPath } from "../../api/fieldPath";
import { EMPTY_PROVENANCE } from "../../lib/evidence";
import { correctionNoteFor } from "./shared";

interface EducationSectionProps {
  education: EducationEntry[];
  corrections: Record<string, CorrectionResponse>;
  onSubmitCorrection: (fieldPath: string, correctedValue: string) => Promise<void>;
  onFocusEvidence: (keys: string[]) => void;
}

export function EducationSection({
  education,
  corrections,
  onSubmitCorrection,
  onFocusEvidence,
}: EducationSectionProps) {
  return (
    <section className="profile-section" aria-labelledby="section-education">
      <h2 className="profile-section__title" id="section-education" tabIndex={-1}>
        Education
      </h2>
      {education.length === 0 && <EmptyState message="No education entries extracted." />}
      {education.map((entry, index) => {
        const base = `education[${index}]`;
        const rows = [
          { label: "Institution", fieldBase: `${base}.institution`, field: entry.institution },
          { label: "Degree", fieldBase: `${base}.degree`, field: entry.degree },
          { label: "Field of study", fieldBase: `${base}.field_of_study`, field: entry.field_of_study },
          {
            label: "Graduation date",
            fieldBase: `${base}.graduation_date`,
            field: entry.graduation_date,
          },
        ];
        return (
          <div className="entry-card" key={base}>
            <div className="entry-card__header">
              <h3>{entry.institution?.value ?? "Untitled institution"}</h3>
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
