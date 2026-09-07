import { useToasts } from "../hooks/useToasts";

export function ToastRegion() {
  const { toasts, dismissToast } = useToasts();

  return (
    <div className="toast-region" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast--${toast.kind}`}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span>{toast.message}</span>
            <button
              type="button"
              className="button button--ghost button--small"
              onClick={() => dismissToast(toast.id)}
              aria-label="Dismiss notification"
            >
              Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
