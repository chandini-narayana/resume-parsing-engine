import { useId, useState } from "react";
import type { Provenance } from "../api/types";
import { isValidFieldPath } from "../api/fieldPath";
import { provenanceBlockKeys } from "../lib/evidence";
import { ConfidenceBadge } from "./ConfidenceBadge";

export interface CorrectionNote {
  correctedBy: string | null;
  correctedAt: string;
}

interface EditableFieldProps {
  fieldPath: string;
  label: string;
  value: string | null;
  confidence: number | null;
  needsReview: boolean | null;
  provenance: Provenance;
  correctionNote: CorrectionNote | null;
  onSubmitCorrection: (fieldPath: string, correctedValue: string) => Promise<void>;
  onFocusEvidence: (keys: string[]) => void;
  emptyValueLabel?: string;
}

/**
 * One row of the profile pane: a single ScoredField (or skill canonical
 * name, which shares the same value/confidence/provenance shape) with
 * inline editing, a confidence badge, and a source-evidence disclosure.
 *
 * `value`/`confidence`/`needsReview` always come straight from the current
 * profile prop -- the backend now applies a correction to the stored
 * CandidateProfile before returning it (see api/routes/resumes.py), so
 * there's no separate client-side overlay to reconcile. `correctionNote`
 * is purely an informational "you corrected this" caption for fields
 * corrected earlier in this session; it never overrides what's displayed.
 */
export function EditableField({
  fieldPath,
  label,
  value,
  confidence,
  needsReview,
  provenance,
  correctionNote,
  onSubmitCorrection,
  onFocusEvidence,
  emptyValueLabel = "Not extracted",
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [showEvidence, setShowEvidence] = useState(false);
  const [status, setStatus] = useState<"idle" | "saving" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputId = useId();

  const evidenceKeys = provenanceBlockKeys(provenance);
  const hasEvidence = provenance.original_text.length > 0;

  function startEditing() {
    setDraft(value ?? "");
    setStatus("idle");
    setErrorMessage(null);
    setIsEditing(true);
  }

  async function handleSave() {
    if (!isValidFieldPath(fieldPath)) {
      setStatus("error");
      setErrorMessage("This field can't be corrected -- its path isn't recognized by the API.");
      return;
    }
    setStatus("saving");
    setErrorMessage(null);
    try {
      await onSubmitCorrection(fieldPath, draft);
      setStatus("idle");
      setIsEditing(false);
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Correction failed.");
    }
  }

  return (
    <div className="field-row">
      <div className="field-row__main">
        <div className="field-row__label">{label}</div>
        {!isEditing ? (
          <div
            className={`field-row__value${value ? "" : " field-row__value--empty"}`}
            onMouseEnter={() => evidenceKeys.length > 0 && onFocusEvidence(evidenceKeys)}
          >
            {value || emptyValueLabel}
          </div>
        ) : (
          <div className="editable-field">
            <label htmlFor={inputId} className="visually-hidden">
              Corrected value for {label}
            </label>
            <input
              id={inputId}
              className="editable-field__input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={status === "saving"}
              // eslint-disable-next-line jsx-a11y/no-autofocus -- opened via explicit user action (Edit button)
              autoFocus
            />
            <div className="editable-field__row">
              <button
                type="button"
                className="button button--primary button--small"
                onClick={handleSave}
                disabled={status === "saving"}
              >
                {status === "saving" ? "Saving…" : "Save correction"}
              </button>
              <button
                type="button"
                className="button button--ghost button--small"
                onClick={() => setIsEditing(false)}
                disabled={status === "saving"}
              >
                Cancel
              </button>
              {status === "error" && errorMessage && (
                <span className="editable-field__status editable-field__status--error" role="alert">
                  {errorMessage}
                </span>
              )}
            </div>
          </div>
        )}
        {correctionNote && (
          <div className="field-row__correction-note">
            Corrected by {correctionNote.correctedBy || "you"} in this session · saved to the
            candidate profile
          </div>
        )}
        {hasEvidence && (
          <>
            <button
              type="button"
              className="field-row__evidence-toggle"
              aria-expanded={showEvidence}
              onClick={() => {
                setShowEvidence((prev) => !prev);
                onFocusEvidence(evidenceKeys);
              }}
            >
              {showEvidence ? "Hide source evidence" : "View source evidence"}
            </button>
            {showEvidence && (
              <div className="field-evidence-excerpt">
                {provenance.section && <div>Section: {provenance.section}</div>}
                {provenance.original_text.join("\n")}
              </div>
            )}
          </>
        )}
      </div>
      <div className="field-row__side">
        <ConfidenceBadge confidence={confidence} needsReview={needsReview} />
        {!isEditing && (
          <button type="button" className="button button--ghost button--small" onClick={startEditing}>
            Edit
          </button>
        )}
      </div>
    </div>
  );
}
