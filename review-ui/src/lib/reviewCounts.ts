import type { CandidateProfile } from "../api/types";

export interface ReviewCounts {
  contact: number;
  skills: number;
  experience: number;
  education: number;
  total: number;
}

/** Server-computed needs_review flags, just tallied per section for the nav badges. */
export function countNeedsReview(profile: CandidateProfile): ReviewCounts {
  const contact = [
    profile.contact.full_name,
    profile.contact.email,
    profile.contact.phone,
    profile.contact.location,
    ...profile.contact.links,
  ].filter((field) => field?.needs_review).length;

  const skills = profile.skills.filter((skill) => skill.needs_review).length;

  const experience = profile.experience.reduce((count, entry) => {
    const flagged = [entry.job_title, entry.company, entry.start_date, entry.end_date].filter(
      (field) => field?.needs_review
    ).length;
    return count + flagged;
  }, 0);

  const education = profile.education.reduce((count, entry) => {
    const flagged = [
      entry.institution,
      entry.degree,
      entry.field_of_study,
      entry.graduation_date,
    ].filter((field) => field?.needs_review).length;
    return count + flagged;
  }, 0);

  return { contact, skills, experience, education, total: contact + skills + experience + education };
}

export interface ReviewProgress {
  reviewed: number;
  total: number;
}

interface NeedsReviewable {
  needs_review: boolean | null;
}

/** Aggregate reviewed-vs-total across every scoreable field, for the workspace's progress meter. */
export function countReviewProgress(profile: CandidateProfile): ReviewProgress {
  let total = 0;
  let flagged = 0;

  function tally(field: NeedsReviewable | null | undefined): void {
    if (!field) return;
    total += 1;
    if (field.needs_review) flagged += 1;
  }

  tally(profile.contact.full_name);
  tally(profile.contact.email);
  tally(profile.contact.phone);
  tally(profile.contact.location);
  profile.contact.links.forEach(tally);

  profile.skills.forEach(tally);

  profile.experience.forEach((entry) => {
    tally(entry.job_title);
    tally(entry.company);
    tally(entry.start_date);
    tally(entry.end_date);
  });

  profile.education.forEach((entry) => {
    tally(entry.institution);
    tally(entry.degree);
    tally(entry.field_of_study);
    tally(entry.graduation_date);
  });

  return { reviewed: total - flagged, total };
}
