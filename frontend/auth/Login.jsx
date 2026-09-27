import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { authApi, storeRefresh, storeToken } from "./api";
import AuthLayout from "./components/AuthLayout";
import { AuthCard, Divider, GoogleButton, Notice, PrimaryButton, TextField } from "./components/ui";

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const justVerified = location.state?.verified;
  const justReset = location.state?.reset;
  const [email, setEmail] = useState(location.state?.email || "");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({});
  const [notice, setNotice] = useState(
    justVerified
      ? { kind: "ok", text: "Email verified. Sign in to continue." }
      : justReset
        ? { kind: "ok", text: "Password changed. Sign in with your new password." }
        : null
  );
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!/^\S+@\S+\.\S+$/.test(email)) errs.email = "Enter a valid email.";
    if (!password) errs.password = "Enter your password.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    setNotice(null);
    try {
      const data = await authApi.login(email.trim(), password);
      storeToken(data.access_token);
      storeRefresh(data.refresh_token);
      navigate("/home", { replace: true });
    } catch (err) {
      setNotice({ kind: "err", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <AuthCard title="Welcome back" subtitle="Continue where you left off.">
        <Notice kind={notice?.kind}>{notice?.text}</Notice>
        <form onSubmit={onSubmit} className="auth-form" noValidate>
          <TextField label="Email" placeholder="you@example.com" value={email}
            onChange={(e) => setEmail(e.target.value)} error={errors.email} autoComplete="email" />
          <TextField label="Password" placeholder="••••••••" value={password} showToggle
            onChange={(e) => setPassword(e.target.value)} error={errors.password} autoComplete="current-password" />
          <div className="auth-meta">
            <Link className="auth-link" to="/forgot-password">Forgot password?</Link>
          </div>
          <PrimaryButton type="submit" loading={loading}>Sign in →</PrimaryButton>
        </form>
        <Divider />
        <GoogleButton onClick={authApi.googleLogin}>Continue with Google</GoogleButton>
        <p className="auth-bottom">
          Don&apos;t have an account? <Link className="auth-link" to="/signup">Create account</Link>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
