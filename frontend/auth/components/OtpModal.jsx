import { useEffect, useRef, useState } from "react";
import { authApi } from "../api";
import { LogoMark } from "./ui";

// Verification OTP modal, opened from the /home verify banner.
export default function OtpModal({ email, onVerified, onClose }) {
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [status, setStatus] = useState("idle"); // idle | sending | verifying | error
  const [msg, setMsg] = useState("");
  const boxes = useRef([]);
  const sentRef = useRef(false); // StrictMode double-mount guard: one mail only
  const [cooldown, setCooldown] = useState(0); // resend spam guard (no expiry pressure)

  const send = async () => {
    setStatus("sending");
    setMsg("Sending code...");
    try {
      const data = await authApi.requestCode(email);
      if (data.already_verified) {
        onVerified();
        return;
      }
      // Banner is hidden when this is false, so reaching here means they disagreed.
      if (data.verification_available === false) {
        setStatus("error");
        setMsg("Email verification is disabled on this instance.");
        return;
      }
      setDigits(["", "", "", "", "", ""]);
      setStatus("idle");
      setMsg(data.throttled ? `Code already sent to ${email}. Check inbox.` : `Code sent to ${email}.`);
      setCooldown(30);
      boxes.current[0]?.focus();
    } catch (err) {
      setStatus("error");
      setMsg(err.message);
    }
  };

  useEffect(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    send();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const setAt = (i, v) => {
    if (!/^\d?$/.test(v)) return;
    const next = [...digits];
    next[i] = v;
    setDigits(next);
    if (v && i < 5) boxes.current[i + 1]?.focus();
  };

  const onKey = (i, e) => {
    if (e.key === "Backspace" && !digits[i] && i > 0) boxes.current[i - 1]?.focus();
  };

  const onPaste = (e) => {
    const nums = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6).split("");
    if (!nums.length) return;
    e.preventDefault();
    const next = ["", "", "", "", "", ""];
    nums.forEach((n, k) => (next[k] = n));
    setDigits(next);
    boxes.current[Math.min(nums.length, 5)]?.focus();
  };

  const verify = async () => {
    const code = digits.join("");
    if (code.length < 6) {
      setStatus("error");
      setMsg("Enter all 6 digits.");
      return;
    }
    setStatus("verifying");
    setMsg("Checking...");
    try {
      await authApi.verifyCode(email, code);
      onVerified();
    } catch (err) {
      setStatus("error");
      setMsg(err.message);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <LogoMark size={44} />
        <h2>Check your email</h2>
        <p className="auth-sub">We sent a 6-digit code to <b>{email}</b></p>
        <div className="otp-row" onPaste={onPaste}>
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => (boxes.current[i] = el)}
              className="otp-box"
              inputMode="numeric"
              maxLength={1}
              value={d}
              onChange={(e) => setAt(i, e.target.value)}
              onKeyDown={(e) => onKey(i, e)}
            />
          ))}
        </div>
        {msg && <p className={`notice notice-${status === "error" ? "err" : "ok"}`}>{msg}</p>}
        <div className="modal-actions">
          <button className="btn-primary" style={{ flex: 1 }}
            disabled={status === "verifying"} onClick={verify}>
            {status === "verifying" ? "Checking..." : "Verify"}
          </button>
          <button className="btn-google" style={{ flex: 1 }}
            disabled={status === "sending" || cooldown > 0} onClick={send}>
            {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
          </button>
        </div>
      </div>
    </div>
  );
}
