import { BrandMark } from "./BrandMark.jsx";
import { useScrolled } from "../hooks.js";
import { useState } from "react";

const LINKS = [
  { label: "Research", href: "#agents" },
  { label: "Travel", href: "#agents" },
  { label: "Shopping", href: "#agents" },
  { label: "Jobs", href: "#agents" },
  { label: "How it works", href: "#how" },
];

export default function Navbar() {
  const scrolled = useScrolled();
  const [open, setOpen] = useState(false);

  return (
    <nav className={`nav${scrolled ? " scrolled" : ""}`} aria-label="Primary">
      <div className="container nav-inner">
        <BrandMark />

        <div className={`nav-links${open ? " open" : ""}`} id="nav-links">
          {LINKS.map((l) => (
            <a key={l.label} href={l.href} onClick={() => setOpen(false)}>{l.label}</a>
          ))}
        </div>

        <div className="nav-cta">
          <a className="nav-login" href="mailto:rajrounak366@gmail.com">Contact</a>
          <a className="nav-login" href="/login">Log in</a>
          <a className="btn btn-primary" href="/signup" style={{ minHeight: 38, fontSize: 13 }}>
            Get Started <span className="arr" aria-hidden="true">→</span>
          </a>
          <button
            className="menu-btn" aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open} aria-controls="nav-links"
            onClick={() => setOpen((v) => !v)}
          >
            <svg width="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              {open
                ? <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                : <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />}
            </svg>
          </button>
        </div>
      </div>
    </nav>
  );
}
