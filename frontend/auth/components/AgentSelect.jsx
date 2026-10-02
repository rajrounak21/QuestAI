import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ChevronDownIcon, CheckIcon } from "./icons";

/**
 * A styled select for the theme.
 *
 * A native <select> cannot be styled: the OS paints the popup itself, so on
 * Windows it renders as a white box with black text that ignores the dark
 * theme entirely. This is a button + listbox instead, so the menu is part of
 * the page and can follow the theme.
 *
 * Keyboard support: Enter/Space/ArrowDown open, ArrowUp/ArrowDown move the
 * active option, Enter picks it, Escape closes, Tab closes and moves on.
 */
export default function AgentSelect({ value, options, onChange, disabled, id }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  // Flip the menu above the button when there is not enough room below.
  const [up, setUp] = useState(false);
  const wrapRef = useRef(null);
  const btnRef = useRef(null);
  const listId = useId();

  const selected = options.find((o) => o.id === value) || options[0];

  // Measured on open: a 7-item menu is ~500px tall, taller than the space
  // under the input on a laptop and way taller on a phone.
  const placeMenu = useCallback(() => {
    const btn = btnRef.current;
    if (!btn) return;
    const needed = options.length * 52 + 16;
    const below = window.innerHeight - btn.getBoundingClientRect().bottom;
    setUp(needed > below && btn.getBoundingClientRect().top > below);
  }, [options.length]);

  const close = useCallback((focusBtn = true) => {
    setOpen(false);
    if (focusBtn) btnRef.current?.focus();
  }, []);

  // Close on an outside click. mousedown (not click) so it fires before the
  // click lands on whatever is underneath.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  // Keep the highlighted row in step with the chosen one each time it opens.
  useEffect(() => {
    if (!open) return;
    const i = options.findIndex((o) => o.id === value);
    setActive(i < 0 ? 0 : i);
    placeMenu();
  }, [open, options, value, placeMenu]);

  // Re-measure on resize / scroll so the menu never ends up off-screen.
  useEffect(() => {
    if (!open) return;
    const remeasure = () => placeMenu();
    window.addEventListener("resize", remeasure);
    window.addEventListener("scroll", remeasure, true);
    return () => {
      window.removeEventListener("resize", remeasure);
      window.removeEventListener("scroll", remeasure, true);
    };
  }, [open, placeMenu]);

  const pick = (id) => {
    onChange(id);
    setOpen(false);
    btnRef.current?.focus();
  };

  const onKeyDown = (e) => {
    if (!open) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % options.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i - 1 + options.length) % options.length);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (options[active]) pick(options[active].id);
    } else if (e.key === "Tab") {
      setOpen(false);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(options.length - 1);
    }
  };

  // Arrow keys move the highlight, so bring the new row into view. Without
  // this the keyboard can walk into a row that is scrolled out of sight.
  useEffect(() => {
    if (!open || !active) return;
    wrapRef.current
      ?.querySelectorAll(".dash-agent-opt")
      [active]?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  return (
    <div className="dash-ask-agent" ref={wrapRef}>
      <button
        ref={btnRef}
        type="button"
        id={id}
        className={`dash-agent-btn${open ? " is-open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={onKeyDown}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={`Agent: ${selected.label}. Change agent`}
      >
        <span className="dash-agent-btn-label">{selected.label}</span>
        <ChevronDownIcon />
      </button>

      {open && (
        <ul
          className={`dash-agent-menu${up ? " is-up" : ""}`}
          id={listId}
          role="listbox"
          aria-label="Choose an agent"
        >
          {options.map((o, i) => {
            const isSel = o.id === value;
            return (
              <li key={o.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={isSel}
                  className={`dash-agent-opt${isSel ? " is-sel" : ""}${
                    i === active ? " is-active" : ""
                  }`}
                  onClick={() => pick(o.id)}
                  onMouseEnter={() => setActive(i)}
                >
                  <span className="dash-agent-opt-text">
                    <span className="dash-agent-opt-label">{o.label}</span>
                    <span className="dash-agent-opt-hint">{o.hint}</span>
                  </span>
                  {isSel && <CheckIcon />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
