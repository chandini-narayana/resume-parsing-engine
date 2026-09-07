/**
 * Mirrors _ALLOWED_FIELD_PATH_RE_SOURCE in
 * src/resume_engine/api/routes/resumes.py exactly, so the UI can reject an
 * invalid path before round-tripping to the server. The server re-validates
 * regardless -- this is purely for fast, honest client-side feedback, never
 * the source of truth.
 */
const FIELD_PATH_PATTERN = /^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])*$/;

export function isValidFieldPath(path: string): boolean {
  return FIELD_PATH_PATTERN.test(path);
}

export function scoredFieldPath(basePath: string): string {
  return `${basePath}.value`;
}
