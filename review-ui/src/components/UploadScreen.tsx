import { useRef, useState, type DragEvent } from "react";
import { SourceProfileDiagram } from "./SourceProfileDiagram";
import { WorkflowRail } from "./WorkflowRail";
import { RecentCandidatesList } from "./RecentCandidatesList";
import type { RecentCandidate } from "../lib/recentCandidates";

interface UploadScreenProps {
  onFileSelected: (file: File) => void;
  onLookup: (candidateId: string) => void;
  errorMessage: string | null;
  recentCandidates: RecentCandidate[];
}

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];
// Mirrors the backend's default (RESUME_ENGINE_MAX_UPLOAD_SIZE_MB) purely
// for fast client-side feedback -- the server enforces the real limit for
// whatever it's actually configured with.
const MAX_SIZE_MB = 10;

export function UploadScreen({
  onFileSelected,
  onLookup,
  errorMessage,
  recentCandidates,
}: UploadScreenProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [lookupId, setLookupId] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function validateAndSelect(file: File) {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setLocalError(`"${file.name}" isn't a supported format. Upload a PDF or DOCX resume.`);
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setLocalError(`"${file.name}" is larger than ${MAX_SIZE_MB}MB.`);
      return;
    }
    setLocalError(null);
    onFileSelected(file);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragActive(false);
    const file = event.dataTransfer.files[0];
    if (file) validateAndSelect(file);
  }

  return (
    <div className="intake-shell">
      <aside className="intake-rail" aria-label="How this works">
        <SourceProfileDiagram />

        <div className="intake-rail__section">
          <h2>How it works</h2>
          <WorkflowRail />
        </div>

        <RecentCandidatesList candidates={recentCandidates} onOpen={onLookup} />
      </aside>

      <div className="intake-main">
        <div className="intake-main__inner">
          <div className="intake-main__intro">
            <h2>Upload a resume for review</h2>
            <p>
              Parses the document, extracts contact details, skills, experience, and education,
              scores confidence per field, and hands you a structured profile to inspect and
              correct against the original text.
            </p>
          </div>

          {(errorMessage ?? localError) && (
            <div className="upload-error" role="alert">
              {errorMessage ?? localError}
            </div>
          )}

          <div
            className={`upload-dropzone${isDragActive ? " upload-dropzone--active" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragActive(true);
            }}
            onDragLeave={() => setIsDragActive(false)}
            onDrop={handleDrop}
          >
            <div className="upload-dropzone__icon" aria-hidden="true">
              <svg
                width="26"
                height="26"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path
                  d="M12 3v12m0-12 4 4m-4-4-4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <p>Drag a resume here, or</p>
            <button
              type="button"
              className="button button--primary"
              onClick={() => inputRef.current?.click()}
            >
              Choose file
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx"
              className="visually-hidden"
              aria-label="Choose a resume file to upload"
              tabIndex={-1}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) validateAndSelect(file);
                event.target.value = "";
              }}
            />
            <span className="upload-constraints">PDF or DOCX, up to {MAX_SIZE_MB}MB</span>
          </div>

          <div className="upload-divider" role="presentation">
            <span>Or reopen a candidate</span>
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (lookupId.trim()) onLookup(lookupId.trim());
            }}
            className="upload-lookup"
          >
            <label htmlFor="lookup-id" className="visually-hidden">
              Candidate ID
            </label>
            <input
              id="lookup-id"
              value={lookupId}
              onChange={(event) => setLookupId(event.target.value)}
              className="editable-field__input"
              style={{ width: 260 }}
              placeholder="Paste a candidate ID"
            />
            <button type="submit" className="button button--secondary button--small">
              Open
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
