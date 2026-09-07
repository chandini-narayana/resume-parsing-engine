interface ErrorScreenProps {
  title: string;
  message: string;
  onRetry: () => void;
}

export function ErrorScreen({ title, message, onRetry }: ErrorScreenProps) {
  return (
    <div className="error-screen" role="alert">
      <h2>{title}</h2>
      <div className="error-screen__message">{message}</div>
      <div>
        <button type="button" className="button button--primary" onClick={onRetry}>
          Try a different resume
        </button>
      </div>
    </div>
  );
}
