import { useState } from "react";
import { Link } from "react-router-dom";
import QuestMark from "../../src/shared/QuestMark.jsx";
import { applyTheme, getTheme } from "../theme";
import { MoonIcon, SunIcon } from "./icons";

export function AuthCard({ title, subtitle, children }) {
  return (
    <div className="auth-card">
      <div className="auth-card-top">
        <span className="auth-card-logo">
          <LogoMark size={32} />
        </span>
        <HomeTab />
      </div>
      <h2>{title}</h2>
      {subtitle && <p className="auth-sub">{subtitle}</p>}
      {children}
    </div>
  );
}

export function LogoMark({ size = 40 }) {
  return <QuestMark size={size} />;
}

export function Notice({ kind, children }) {
  if (!children) return null;
  return <div className={`notice notice-${kind}`}>{children}</div>;
}

export function TextField({ label, error, showToggle, ...props }) {
  const [show, setShow] = useState(false);
  const type = showToggle ? (show ? "text" : "password") : props.type;
  return (
    <div className="field">
      {label && <label>{label}</label>}
      <div className="field-row">
        <input className={`input${error ? " input-error" : ""}`} {...props} type={type} />
        {showToggle && (
          <button type="button" className="eye" onClick={() => setShow((s) => !s)}>
            {show ? "HIDE" : "SHOW"}
          </button>
        )}
      </div>
      {error && <p className="field-err">{error}</p>}
    </div>
  );
}

export function PrimaryButton({ loading, children, ...props }) {
  return (
    <button className="btn-primary" disabled={loading || props.disabled} {...props}>
      {loading && <span className="spin" />}
      {children}
    </button>
  );
}

export function GoogleButton({ children, ...props }) {
  return (
    <button type="button" className="btn-google" {...props}>
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
      </svg>
      {children}
    </button>
  );
}

export function Divider() {
  return <div className="divider">OR</div>;
}

export function HomeTab() {
  return (
    <Link className="home-tab" to="/" title="Back to home page">
      ← Home
    </Link>
  );
}

export function ThemeToggle({ float = false }) {
  const [theme, setTheme] = useState(() => getTheme());
  const flip = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
  };
  return (
    <button
      className={float ? "theme-toggle theme-toggle-float" : "theme-toggle"}
      onClick={flip}
      title={theme === "light" ? "Switch to night" : "Switch to day"}
      aria-label="Toggle day night theme"
    >
      {theme === "light" ? <MoonIcon /> : <SunIcon />}
    </button>
  );
}
