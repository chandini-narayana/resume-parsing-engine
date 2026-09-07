import type { CandidateProfile, Provenance } from "../api/types";

export const EMPTY_PROVENANCE: Provenance = {
  section: null,
  block_ids: [],
  page_numbers: [],
  original_text: [],
};

export interface EvidenceBlock {
  key: string;
  section: string | null;
  text: string;
  pageNumber: number | null;
}

/**
 * There is no single stable evidence ID in the API contract -- block_ids is
 * the closest thing, but it's not always populated. Falling back to
 * section + index + a text prefix keeps evidence blocks from two unrelated
 * fields from colliding while still deduping genuinely repeated blocks
 * (e.g. two fields drawing on the same line of the source document).
 */
function blockKey(section: string | null, blockId: string | undefined, text: string, index: number): string {
  if (blockId) return `id:${blockId}`;
  return `sec:${section ?? "unknown"}::${index}::${text.slice(0, 40)}`;
}

export function provenanceBlockKeys(provenance: Provenance): string[] {
  const count = Math.max(provenance.block_ids.length, provenance.original_text.length);
  const keys: string[] = [];
  for (let i = 0; i < count; i++) {
    const text = provenance.original_text[i];
    if (!text) continue;
    keys.push(blockKey(provenance.section, provenance.block_ids[i], text, i));
  }
  return keys;
}

/** Every distinct evidence block in a profile, grouped by section, in first-seen order. */
export function collectEvidence(profile: CandidateProfile): Map<string, EvidenceBlock[]> {
  const bySection = new Map<string, EvidenceBlock[]>();
  const seen = new Set<string>();

  function addProvenance(provenance: Provenance): void {
    const count = Math.max(provenance.block_ids.length, provenance.original_text.length);
    for (let i = 0; i < count; i++) {
      const text = provenance.original_text[i];
      if (!text) continue;
      const key = blockKey(provenance.section, provenance.block_ids[i], text, i);
      if (seen.has(key)) continue;
      seen.add(key);
      const sectionLabel = provenance.section ?? "Unclassified";
      const list = bySection.get(sectionLabel) ?? [];
      list.push({
        key,
        section: provenance.section,
        text,
        pageNumber: provenance.page_numbers[i] ?? null,
      });
      bySection.set(sectionLabel, list);
    }
  }

  const contact = profile.contact;
  [contact.full_name, contact.email, contact.phone, contact.location, ...contact.links].forEach(
    (field) => field && addProvenance(field.provenance)
  );
  profile.skills.forEach((skill) => skill.mentions.forEach((mention) => addProvenance(mention.provenance)));
  profile.experience.forEach((entry) => {
    addProvenance(entry.provenance);
    [entry.job_title, entry.company, entry.start_date, entry.end_date].forEach(
      (field) => field && addProvenance(field.provenance)
    );
  });
  profile.education.forEach((entry) => {
    addProvenance(entry.provenance);
    [entry.institution, entry.degree, entry.field_of_study, entry.graduation_date].forEach(
      (field) => field && addProvenance(field.provenance)
    );
  });

  if (profile.unclassified_text.length > 0) {
    const list = bySection.get("Unclassified") ?? [];
    profile.unclassified_text.forEach((text, index) => {
      const key = `unclassified:${index}`;
      if (seen.has(key)) return;
      seen.add(key);
      list.push({ key, section: null, text, pageNumber: null });
    });
    bySection.set("Unclassified", list);
  }

  return bySection;
}
