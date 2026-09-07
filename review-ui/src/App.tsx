import { useState } from "react";
import { ApiRequestError, getCandidate, uploadResume } from "./api/client";
import type { CandidateStatusResponse } from "./api/types";
import { ToastProvider } from "./hooks/useToasts";
import { ToastRegion } from "./components/ToastRegion";
import { TopBar } from "./components/TopBar";
import { UploadScreen } from "./components/UploadScreen";
import { ProcessingScreen } from "./components/ProcessingScreen";
import { ErrorScreen } from "./components/ErrorScreen";
import { Workspace } from "./components/Workspace";
import { loadRecentCandidates, rememberCandidate, type RecentCandidate } from "./lib/recentCandidates";

type Stage =
  | { kind: "upload"; errorMessage: string | null }
  | { kind: "processing"; label: string }
  | { kind: "ready"; candidate: CandidateStatusResponse }
  | { kind: "processing-failed"; candidate: CandidateStatusResponse };

function AppInner() {
  const [stage, setStage] = useState<Stage>({ kind: "upload", errorMessage: null });
  const [recentCandidates, setRecentCandidates] = useState<RecentCandidate[]>(() =>
    loadRecentCandidates()
  );

  function remember(candidate: CandidateStatusResponse) {
    setRecentCandidates(
      rememberCandidate({
        candidateId: candidate.candidate_id,
        filename: candidate.original_filename,
        status: candidate.status,
        openedAt: new Date().toISOString(),
      })
    );
  }

  async function handleFileSelected(file: File) {
    setStage({ kind: "processing", label: file.name });
    try {
      const uploadResponse = await uploadResume(file);
      // The upload response doesn't carry the profile -- fetch the full
      // record (see api/routes/resumes.py: POST /resumes returns only
      // candidate_id/status, GET /resumes/{id} returns the profile).
      const candidate = await getCandidate(uploadResponse.candidate_id);
      remember(candidate);
      if (candidate.status === "completed" && candidate.profile) {
        setStage({ kind: "ready", candidate });
      } else {
        setStage({ kind: "processing-failed", candidate });
      }
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : "Upload failed unexpectedly.";
      setStage({ kind: "upload", errorMessage: message });
    }
  }

  async function handleLookup(candidateId: string) {
    setStage({ kind: "processing", label: `Looking up ${candidateId}` });
    try {
      const candidate = await getCandidate(candidateId);
      remember(candidate);
      if (candidate.status === "completed" && candidate.profile) {
        setStage({ kind: "ready", candidate });
      } else if (candidate.status === "failed") {
        setStage({ kind: "processing-failed", candidate });
      } else {
        setStage({
          kind: "upload",
          errorMessage: `Candidate ${candidateId} is still "${candidate.status}" -- try again shortly.`,
        });
      }
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : "Could not look up that candidate.";
      setStage({ kind: "upload", errorMessage: message });
    }
  }

  function handleStartOver() {
    setStage({ kind: "upload", errorMessage: null });
  }

  const headerCandidate =
    stage.kind === "ready" || stage.kind === "processing-failed" ? stage.candidate : undefined;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <TopBar
        filename={headerCandidate?.original_filename}
        status={headerCandidate?.status}
        onStartOver={stage.kind !== "upload" ? handleStartOver : undefined}
      />
      <main id="main-content">
        {stage.kind === "upload" && (
          <UploadScreen
            onFileSelected={handleFileSelected}
            onLookup={handleLookup}
            errorMessage={stage.errorMessage}
            recentCandidates={recentCandidates}
          />
        )}
        {stage.kind === "processing" && <ProcessingScreen fileName={stage.label} />}
        {stage.kind === "processing-failed" && (
          <ErrorScreen
            title="Processing failed"
            message={stage.candidate.processing_error ?? "This resume could not be processed."}
            onRetry={handleStartOver}
          />
        )}
        {stage.kind === "ready" && stage.candidate.profile && (
          <Workspace
            candidateId={stage.candidate.candidate_id}
            initialProfile={stage.candidate.profile}
          />
        )}
      </main>
      <ToastRegion />
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
