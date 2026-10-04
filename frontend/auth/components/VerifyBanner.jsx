// Optional prompt for /home. Never a gate: /login does not check
// email_verified, so skipping leaves a fully working account.
export default function VerifyBanner({ email, onVerify, onSkip }) {
  return (
    <div className="verify-bar" role="status">
      <div className="verify-bar-text">
        <strong>Verify your email</strong>
        <span>
          Confirm <b>{email}</b> to secure your account. Optional — skip it and
          keep using QuestAI.
        </span>
      </div>
      <div className="verify-bar-actions">
        <button className="btn-primary" onClick={onVerify}>
          Verify email
        </button>
        <button className="auth-link" onClick={onSkip}>
          Skip for now
        </button>
      </div>
    </div>
  );
}