import type { ContactInfo, CorrectionResponse } from "../../api/types";
import { EditableField } from "../EditableField";
import { EmptyState } from "../EmptyState";
import { scoredFieldPath } from "../../api/fieldPath";
import { EMPTY_PROVENANCE } from "../../lib/evidence";
import { correctionNoteFor } from "./shared";

interface ContactSectionProps {
  contact: ContactInfo;
  corrections: Record<string, CorrectionResponse>;
  onSubmitCorrection: (fieldPath: string, correctedValue: string) => Promise<void>;
  onFocusEvidence: (keys: string[]) => void;
}

export function ContactSection({
  contact,
  corrections,
  onSubmitCorrection,
  onFocusEvidence,
}: ContactSectionProps) {
  const rows = [
    { label: "Full name", base: "contact.full_name", field: contact.full_name },
    { label: "Email", base: "contact.email", field: contact.email },
    { label: "Phone", base: "contact.phone", field: contact.phone },
    { label: "Location", base: "contact.location", field: contact.location },
  ];

  return (
    <section className="profile-section" aria-labelledby="section-contact">
      <h2 className="profile-section__title" id="section-contact" tabIndex={-1}>
        Contact
      </h2>
      <div className="entry-card">
        {rows.map(({ label, base, field }) => {
          const path = scoredFieldPath(base);
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
        {contact.links.map((link, index) => {
          const path = scoredFieldPath(`contact.links[${index}]`);
          return (
            <EditableField
              key={path}
              fieldPath={path}
              label={`Link ${index + 1}`}
              value={link.value}
              confidence={link.confidence}
              needsReview={link.needs_review}
              provenance={link.provenance}
              correctionNote={correctionNoteFor(corrections, path)}
              onSubmitCorrection={onSubmitCorrection}
              onFocusEvidence={onFocusEvidence}
            />
          );
        })}
        {contact.links.length === 0 && <EmptyState message="No links extracted." />}
      </div>
    </section>
  );
}
