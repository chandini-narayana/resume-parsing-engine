/**
 * A per-browser memory of candidates actually opened this session, so the
 * intake screen can offer a real "recently opened" list without a backend
 * list-candidates endpoint (none exists -- see review-ui/README.md). Every
 * entry here is a real candidate_id/filename/status this browser actually
 * received from the API; nothing here is fabricated demo data. Re-opening
 * one still goes through the real GET /resumes/{id} endpoint.
 */
const STORAGE_KEY = "resume-review-ui:recent-candidates";
const MAX_ENTRIES = 5;

export interface RecentCandidate {
  candidateId: string;
  filename: string;
  status: string;
  openedAt: string;
}

export function loadRecentCandidates(): RecentCandidate[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as RecentCandidate[]) : [];
  } catch {
    return [];
  }
}

export function rememberCandidate(entry: RecentCandidate): RecentCandidate[] {
  const deduped = loadRecentCandidates().filter((c) => c.candidateId !== entry.candidateId);
  const updated = [entry, ...deduped].slice(0, MAX_ENTRIES);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // Best-effort convenience only; losing this list doesn't block the workflow.
  }
  return updated;
}
