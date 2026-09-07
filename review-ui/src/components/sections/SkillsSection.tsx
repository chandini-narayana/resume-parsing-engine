import type { CorrectionResponse, Provenance, SkillEntry } from "../../api/types";
import { EditableField } from "../EditableField";
import { EmptyState } from "../EmptyState";
import { ConfidenceBadge } from "../ConfidenceBadge";
import { EMPTY_PROVENANCE, provenanceBlockKeys } from "../../lib/evidence";
import { correctionNoteFor } from "./shared";

interface SkillsSectionProps {
  skills: SkillEntry[];
  corrections: Record<string, CorrectionResponse>;
  onSubmitCorrection: (fieldPath: string, correctedValue: string) => Promise<void>;
  onFocusEvidence: (keys: string[]) => void;
}

/** A skill entry has no provenance of its own -- it's the union of its mentions'. */
function aggregateProvenance(entry: SkillEntry): Provenance {
  if (entry.mentions.length === 0) return EMPTY_PROVENANCE;
  return entry.mentions.reduce<Provenance>(
    (acc, mention) => ({
      section: acc.section ?? mention.provenance.section,
      block_ids: [...acc.block_ids, ...mention.provenance.block_ids],
      page_numbers: [...acc.page_numbers, ...mention.provenance.page_numbers],
      original_text: [...acc.original_text, ...mention.provenance.original_text],
    }),
    { section: null, block_ids: [], page_numbers: [], original_text: [] }
  );
}

export function SkillsSection({
  skills,
  corrections,
  onSubmitCorrection,
  onFocusEvidence,
}: SkillsSectionProps) {
  return (
    <section className="profile-section" aria-labelledby="section-skills">
      <h2 className="profile-section__title" id="section-skills" tabIndex={-1}>
        Skills
      </h2>
      {skills.length === 0 && <EmptyState message="No skills extracted." />}
      <div className="skills-grid">
        {skills.map((skill, index) => {
          const path = `skills[${index}].canonical_name`;
          return (
            <div className="skill-entry" key={path}>
              <EditableField
                fieldPath={path}
                label={`Skill ${index + 1}`}
                value={skill.canonical_name}
                confidence={skill.normalization_confidence}
                needsReview={skill.needs_review}
                provenance={aggregateProvenance(skill)}
                correctionNote={correctionNoteFor(corrections, path)}
                onSubmitCorrection={onSubmitCorrection}
                onFocusEvidence={onFocusEvidence}
                emptyValueLabel="Unmatched -- no canonical skill found"
              />
              {skill.mentions.length > 0 && (
                <div className="skill-entry__mentions">
                  {skill.mentions.map((mention, mentionIndex) => (
                    <div className="skill-mention" key={mentionIndex}>
                      <code>{mention.raw_text}</code>
                      <ConfidenceBadge confidence={mention.confidence} needsReview={mention.needs_review} />
                      {mention.provenance.original_text.length > 0 && (
                        <button
                          type="button"
                          className="field-row__evidence-toggle"
                          onClick={() => onFocusEvidence(provenanceBlockKeys(mention.provenance))}
                        >
                          Locate in source
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
