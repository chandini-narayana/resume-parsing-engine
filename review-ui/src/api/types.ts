/**
 * Mirrors src/resume_engine/api/schemas.py and
 * src/resume_engine/schema/candidate_profile.py field-for-field. Kept as a
 * hand-written mirror (not generated) since the backend does not currently
 * publish an OpenAPI-derived client -- if the Pydantic models change, this
 * file must be updated to match.
 */

export interface Provenance {
  section: string | null;
  block_ids: string[];
  page_numbers: (number | null)[];
  original_text: string[];
}

export interface ExtractionEvidenceSummary {
  method: string;
  section: string | null;
  matching_strength: string;
  signals_agree: boolean;
  ambiguous: boolean;
  ambiguity_reason: string | null;
  normalization_ready: boolean;
  notes: string | null;
}

export interface ScoredField<T> {
  value: T;
  confidence: number | null;
  needs_review: boolean | null;
  provenance: Provenance;
  extraction_evidence: ExtractionEvidenceSummary | null;
}

export interface ContactInfo {
  full_name: ScoredField<string> | null;
  email: ScoredField<string> | null;
  phone: ScoredField<string> | null;
  location: ScoredField<string> | null;
  links: ScoredField<string>[];
}

export interface NormalizationEvidence {
  method: string; // "exact_alias" | "fuzzy" | "unmatched"
  match_score: number;
}

export interface SkillMention {
  raw_text: string;
  confidence: number | null;
  needs_review: boolean | null;
  provenance: Provenance;
  extraction_evidence: ExtractionEvidenceSummary | null;
}

export interface SkillEntry {
  canonical_name: string | null;
  mentions: SkillMention[];
  normalization_evidence: NormalizationEvidence | null;
  normalization_confidence: number | null;
  needs_review: boolean | null;
}

export interface ExperienceEntry {
  job_title: ScoredField<string> | null;
  company: ScoredField<string> | null;
  start_date: ScoredField<string> | null;
  end_date: ScoredField<string> | null;
  is_current: boolean;
  provenance: Provenance;
}

export interface EducationEntry {
  institution: ScoredField<string> | null;
  degree: ScoredField<string> | null;
  field_of_study: ScoredField<string> | null;
  graduation_date: ScoredField<string> | null;
  provenance: Provenance;
}

export interface CandidateProfile {
  source_filename: string;
  contact: ContactInfo;
  skills: SkillEntry[];
  experience: ExperienceEntry[];
  education: EducationEntry[];
  parser_warnings: string[];
  unclassified_text: string[];
}

export type CandidateStatus = "uploaded" | "processing" | "completed" | "failed";

export interface CandidateUploadResponse {
  candidate_id: string;
  original_filename: string;
  file_format: string;
  status: CandidateStatus;
  uploaded_at: string;
}

export interface CandidateStatusResponse {
  candidate_id: string;
  original_filename: string;
  file_format: string;
  status: CandidateStatus;
  uploaded_at: string;
  processing_error: string | null;
  profile: CandidateProfile | null;
}

export interface CorrectionRequest {
  field_path: string;
  corrected_value: string;
  corrected_by?: string | null;
}

export interface CorrectionResponse {
  candidate_id: string;
  field_path: string;
  corrected_value: string;
  corrected_by: string | null;
  corrected_at: string;
  original_value: string | null;
  /** The full profile as persisted after this correction was applied. */
  profile: CandidateProfile;
}
