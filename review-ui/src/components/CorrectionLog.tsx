import type { CorrectionResponse } from "../api/types";

interface CorrectionLogProps {
  corrections: Record<string, CorrectionResponse>;
}

export function CorrectionLog({ corrections }: CorrectionLogProps) {
  const items = Object.values(corrections).sort((a, b) => a.corrected_at.localeCompare(b.corrected_at));
  if (items.length === 0) return null;

  return (
    <div className="correction-log" aria-label="Corrections submitted this session">
      <div className="correction-log__title">Corrections submitted this session ({items.length})</div>
      {items.map((item) => (
        <div className="correction-log__item" key={item.field_path}>
          <code>{item.field_path}</code> → &ldquo;{item.corrected_value}&rdquo;
          {item.corrected_by ? ` · ${item.corrected_by}` : ""} ·{" "}
          {new Date(item.corrected_at).toLocaleString()}
        </div>
      ))}
      <p style={{ fontSize: "0.75rem", color: "var(--color-ink-faint)", marginTop: 8 }}>
        Each correction is recorded in the audit log and applied to the stored candidate profile
        immediately -- reloading or reopening this candidate later will show the corrected values.
        This list itself is session-only, since there's no API to fetch past corrections (see Known
        Limitations).
      </p>
    </div>
  );
}
