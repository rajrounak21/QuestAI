import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi, storeRefresh, storeToken } from "./api";
import AuthLayout from "./components/AuthLayout";
import OtpModal from "./components/OtpModal";
import { AuthCard, Divider, GoogleButton, Notice, PrimaryButton, TextField } from "./components/ui";

export default function Signup() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState({});
  const [notice, setNotice] = useState(null);
  const [suggestSignin, setSuggestSignin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verifyEmail, setVerifyEmail] = useState(null); // opens verification modal on success

  const onSubmit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!name.trim()) errs.name = "Enter your name.";
    if (!/^\S+@\S+\.\S+$/.test(email)) errs.email = "Enter a valid email.";
    if (password.length < 6) errs.password = "Password must be at least 6 characters.";
    if (confirm !== password) errs.confirm = "Passwords do not match.";
    if (!agreed) errs.agreed = "Please accept the Terms & Privacy Policy.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    setNotice(null);
    setSuggestSignin(false);
    try {
      const data = await authApi.signup(email.trim(), password, name.trim());
      storeToken(data.access_token);
      storeRefresh(data.refresh_token);
      setPassword("");
      setConfirm("");
      setVerifyEmail(data.user.email); // verification modal takes over from here
    } catch (err) {
      setNotice({ kind: "err", text: err.message });
      if (/already registered/i.test(err.message || "")) setSuggestSignin(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthCard title="Create your account" subtitle="Start using your AI superapp.">
        {notice && (
          <Notice kind={notice.kind}>
            {notice.text}
            {suggestSignin && notice.kind === "err" && (
              <>
                {" → "}<Link className="auth-link" to="/login">Sign in</Link>
              </>
            )}
          </Notice>
        )}
        <form onSubmit={onSubmit} className="auth-form" noValidate>
          <TextField label="Name" placeholder="Your name" value={name}
            onChange={(e) => setName(e.target.value)} error={errors.name} autoComplete="name" />
          <TextField label="Email" placeholder="you@example.com" value={email}
            onChange={(e) => setEmail(e.target.value)} error={errors.email} autoComplete="email" />
          <TextField label="Password" placeholder="Min 6 characters" value={password} showToggle
            onChange={(e) => setPassword(e.target.value)} error={errors.password} autoComplete="new-password" />
          <TextField label="Confirm password" placeholder="Repeat password" value={confirm} showToggle
            onChange={(e) => setConfirm(e.target.value)} error={errors.confirm} autoComplete="new-password" />
          <label className="check-row">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            <span>I agree to the Terms &amp; Privacy Policy</span>
          </label>
          {errors.agreed && <p className="field-err">{errors.agreed}</p>}
          <PrimaryButton type="submit" loading={loading}>Create account →</PrimaryButton>
        </form>
        <Divider />
        <GoogleButton onClick={authApi.googleLogin}>Signup with Google</GoogleButton>
        <p className="auth-bottom">
          Already have an account? <Link className="auth-link" to="/login">Sign in</Link>
        </p>
      </AuthCard>
      {verifyEmail && (
        <OtpModal
          email={verifyEmail}
          onClose={() => setVerifyEmail(null)}
          onVerified={() => navigate("/home", { replace: true })}
        />
      )}
    </AuthLayout>
  );
}
