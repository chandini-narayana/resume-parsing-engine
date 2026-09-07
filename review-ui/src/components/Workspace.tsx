import { useEffect, useMemo, useState } from "react";
import type { CandidateProfile, CorrectionResponse } from "../api/types";
import { ApiRequestError, submitCorrection } from "../api/client";
import { countNeedsReview, countReviewProgress } from "../lib/reviewCounts";
import { useToasts } from "../hooks/useToasts";
import { SourceEvidencePane } from "./SourceEvidencePane";
import { ContactSection } from "./sections/ContactSection";
import { SkillsSection } from "./sections/SkillsSection";
import { ExperienceSection } from "./sections/ExperienceSection";
import { EducationSection } from "./sections/EducationSection";
import { CorrectionLog } from "./CorrectionLog";

interface WorkspaceProps {
  candidateId: string;
  initialProfile: CandidateProfile;
}

const REVIEWER_STORAGE_KEY = "resume-review-ui:reviewer-name";

const SECTIONS: Array<{ id: string; label: string; countKey: keyof ReturnType<typeof countNeedsReview> }> = [
  { id: "section-contact", label: "Contact", countKey: "contact" },
  { id: "section-skills", label: "Skills", countKey: "skills" },
  { id: "section-experience", label: "Experience", countKey: "experience" },
  { id: "section-education", label: "Education", countKey: "education" },
];

export function Workspace({ candidateId, initialProfile }: WorkspaceProps) {
  const { pushToast } = useToasts();
  const [profile, setProfile] = useState<CandidateProfile>(initialProfile);
  const [corrections, setCorrections] = useState<Record<string, CorrectionResponse>>({});
  const [activeEvidenceKeys, setActiveEvidenceKeys] = useState<string[]>([]);
  const [activeSection, setActiveSection] = useState<string>(SECTIONS[0].id);
  const [reviewerName, setReviewerName] = useState<string>(() => {
    try {
      return window.localStorage.getItem(REVIEWER_STORAGE_KEY) ?? "";
    } catch {
      return "";
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(REVIEWER_STORAGE_KEY, reviewerName);
    } catch {
      // Best-effort convenience only; not persisting a reviewer name across
      // sessions doesn't block the workflow.
    }
  }, [reviewerName]);

  const reviewCounts = useMemo(() => countNeedsReview(profile), [profile]);
  const reviewProgress = useMemo(() => countReviewProgress(profile), [profile]);
  const progressPercent =
    reviewProgress.total === 0 ? 100 : Math.round((reviewProgress.reviewed / reviewProgress.total) * 100);

  async function handleSubmitCorrection(fieldPath: string, correctedValue: string): Promise<void> {
    try {
      const response = await submitCorrection(candidateId, {
        field_path: fieldPath,
        corrected_value: correctedValue,
        corrected_by: reviewerName.trim() || null,
      });
      setProfile(response.profile);
      setCorrections((prev) => ({ ...prev, [fieldPath]: response }));
      pushToast("success", `Correction saved for ${fieldPath} and applied to the candidate profile.`);
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : "Correction failed unexpectedly.";
      pushToast("error", `Could not save correction for ${fieldPath}: ${message}`);
      throw err;
    }
  }

  function handleNavClick(sectionId: string) {
    setActiveSection(sectionId);
    const el = document.getElementById(sectionId);
    if (el) {
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      el.focus();
    }
  }

  return (
    <div className="workspace">
      {profile.parser_warnings.length > 0 && (
        <div className="workspace__banner">
          <div className="warnings-banner" role="status">
            <strong>
              {profile.parser_warnings.length} parsing warning
              {profile.parser_warnings.length === 1 ? "" : "s"}
            </strong>
            <ul>
              {profile.parser_warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="workspace-toolbar">
        <nav className="section-nav" aria-label="Profile sections">
          {SECTIONS.map((section) => {
            const count = reviewCounts[section.countKey];
            return (
              <button
                key={section.id}
                type="button"
                className={`section-nav__item${activeSection === section.id ? " section-nav__item--active" : ""}`}
                onClick={() => handleNavClick(section.id)}
              >
                {section.label}
                {count > 0 && <span className="section-nav__count">({count} to review)</span>}
              </button>
            );
          })}
        </nav>

        <div
          className="review-progress"
          role="status"
          title={`${reviewProgress.reviewed} of ${reviewProgress.total} fields reviewed`}
        >
          <div className="review-progress__bar">
            <div className="review-progress__fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <span className="review-progress__label">
            {reviewProgress.reviewed}/{reviewProgress.total} reviewed
          </span>
        </div>

        <div className="reviewer-field">
          <label htmlFor="reviewer-name">Reviewer</label>
          <input
            id="reviewer-name"
            value={reviewerName}
            onChange={(event) => setReviewerName(event.target.value)}
            placeholder="you@company.com"
          />
        </div>
      </div>

      <div className="workspace__body">
        <section className="pane source-pane" aria-label="Source resume evidence">
          <SourceEvidencePane profile={profile} activeKeys={activeEvidenceKeys} />
        </section>
        <section className="pane profile-pane" aria-label="Structured candidate profile">
          <div className="pane__heading pane__heading--profile">
            <h2>Structured profile</h2>
            {reviewCounts.total > 0 && (
              <span>
                {reviewCounts.total} field{reviewCounts.total === 1 ? "" : "s"} to review
              </span>
            )}
          </div>
          <ContactSection
            contact={profile.contact}
            corrections={corrections}
            onSubmitCorrection={handleSubmitCorrection}
            onFocusEvidence={setActiveEvidenceKeys}
          />
          <SkillsSection
            skills={profile.skills}
            corrections={corrections}
            onSubmitCorrection={handleSubmitCorrection}
            onFocusEvidence={setActiveEvidenceKeys}
          />
          <ExperienceSection
            experience={profile.experience}
            corrections={corrections}
            onSubmitCorrection={handleSubmitCorrection}
            onFocusEvidence={setActiveEvidenceKeys}
          />
          <EducationSection
            education={profile.education}
            corrections={corrections}
            onSubmitCorrection={handleSubmitCorrection}
            onFocusEvidence={setActiveEvidenceKeys}
          />
          {profile.unclassified_text.length > 0 && (
            <section className="profile-section" aria-labelledby="section-unclassified">
              <h2 className="profile-section__title" id="section-unclassified">
                Unclassified content
              </h2>
              <p style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)" }}>
                Segmentation couldn't confidently assign these blocks to a section. They're kept here
                rather than silently dropped.
              </p>
              <div className="entry-card">
                {profile.unclassified_text.map((text, index) => (
                  <p key={index} style={{ fontFamily: "var(--font-mono)", fontSize: "0.82rem" }}>
                    {text}
                  </p>
                ))}
              </div>
            </section>
          )}
          <CorrectionLog corrections={corrections} />
        </section>
      </div>
    </div>
  );
}
