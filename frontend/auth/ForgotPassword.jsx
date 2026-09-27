import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "./api";
import AuthLayout from "./components/AuthLayout";
import { AuthCard, Notice, PrimaryButton, TextField } from "./components/ui";

// Real 2-step reset: 1) email -> code mailed (exact errors shown),
// 2) code + new password -> done -> login.
export default function ForgotPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null);
  const [suggestSignup, setSuggestSignup] = useState(false);
  const [loading, setLoading] = useState(false);

  const sendCode = async (e) => {
    e.preventDefault();
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setError("Enter a valid email.");
      return;
    }
    setError("");
    setLoading(true);
    setNotice(null);
    setSuggestSignup(false);
    try {
      const data = await authApi.forgotPassword(email.trim());
      if (!data || data.ok !== true) throw new Error("Could not send code. Try again.");
      setStep(2);
      setNotice({ kind: "ok", text: `Code sent to ${email.trim()}.` });
    } catch (err) {
      setStep(1); // stay on email step — no account, no code screen, no mail talk
      setNotice({ kind: "err", text: err.message });
      if (/not found/i.test(err.message || "")) setSuggestSignup(true);
    } finally {
      setLoading(false);
    }
  };

  const reset = async (e) => {
    e.preventDefault();
    if (code.replace(/\D/g, "").length < 6) {
      setError("Enter the 6-digit code.");
      return;
    }
    if (pw.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (pw !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setError("");
    setLoading(true);
    setNotice(null);
    try {
      await authApi.resetPassword(email.trim(), code.trim(), pw);
      navigate("/login", { state: { reset: true, email: email.trim() } });
    } catch (err) {
      setNotice({ kind: "err", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthCard
        title={step === 1 ? "Reset your password" : "Enter code + new password"}
        subtitle={step === 1 ? "Enter your account email." : `Code sent to ${email}.`}
      >
        {notice && (
          <Notice kind={notice.kind}>
            {notice.text}
            {suggestSignup && notice.kind === "err" && (
              <>
                {" → "}<Link className="auth-link" to="/signup">Create new account</Link>
              </>
            )}
          </Notice>
        )}
        {step === 1 ? (
          <form onSubmit={sendCode} className="auth-form" noValidate>
            <TextField label="Email" placeholder="you@example.com" value={email}
              onChange={(e) => setEmail(e.target.value)} error={error} autoComplete="email" />
            <PrimaryButton type="submit" loading={loading}>Send reset code →</PrimaryButton>
          </form>
        ) : (
          <form onSubmit={reset} className="auth-form" noValidate>
            <TextField label="6-digit code" placeholder="123456" value={code} inputMode="numeric"
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} />
            <TextField label="New password" placeholder="Min 6 characters" value={pw} showToggle
              onChange={(e) => setPw(e.target.value)} autoComplete="new-password" />
            <TextField label="Confirm new password" placeholder="Repeat password" value={confirm} showToggle
              onChange={(e) => setConfirm(e.target.value)} error={error} autoComplete="new-password" />
            <PrimaryButton type="submit" loading={loading}>Set new password →</PrimaryButton>
            <button type="button" className="auth-link" style={{ alignSelf: "center" }}
              disabled={loading} onClick={sendCode}>
              Resend code
            </button>
          </form>
        )}
        <p className="auth-bottom">
          <Link className="auth-link" to="/login">Back to sign in</Link>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
