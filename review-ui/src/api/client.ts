import type {
  CandidateStatusResponse,
  CandidateUploadResponse,
  CorrectionRequest,
  CorrectionResponse,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);

/**
 * Thrown for any non-2xx response. The backend uses two different error
 * shapes (see api/main.py + api/routes/resumes.py):
 *   - FastAPI's default HTTPException shape: { "detail": "..." }
 *     (upload validation 400s, 404s, correction field_path 400s)
 *   - The app's own ErrorResponse shape: { "code": "...", "message": "..." }
 *     (422 request-validation errors, 500 unhandled errors)
 * `message` below normalizes both into one human-readable string.
 */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

async function parseJsonBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function extractMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    if (typeof record.message === "string") return record.message;
  }
  return fallback;
}

function extractCode(body: unknown): string | null {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.code === "string") return record.code;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiRequestError(
      0,
      "Could not reach the resume processing service. Check that the API is running and reachable."
    );
  }

  const body = await parseJsonBody(response);
  if (!response.ok) {
    throw new ApiRequestError(
      response.status,
      extractMessage(body, `Request failed with status ${response.status}.`),
      extractCode(body)
    );
  }
  return body as T;
}

export function uploadResume(file: File): Promise<CandidateUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<CandidateUploadResponse>("/resumes", {
    method: "POST",
    body: formData,
  });
}

export function getCandidate(candidateId: string): Promise<CandidateStatusResponse> {
  return request<CandidateStatusResponse>(`/resumes/${encodeURIComponent(candidateId)}`);
}

export function submitCorrection(
  candidateId: string,
  correction: CorrectionRequest
): Promise<CorrectionResponse> {
  return request<CorrectionResponse>(`/resumes/${encodeURIComponent(candidateId)}/corrections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(correction),
  });
}
