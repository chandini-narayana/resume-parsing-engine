import type { CorrectionResponse } from "../../api/types";
import type { CorrectionNote } from "../EditableField";

export function correctionNoteFor(
  corrections: Record<string, CorrectionResponse>,
  path: string
): CorrectionNote | null {
  const correction = corrections[path];
  if (!correction) return null;
  return { correctedBy: correction.corrected_by, correctedAt: correction.corrected_at };
}
