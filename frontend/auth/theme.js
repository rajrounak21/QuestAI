// Day/night theme: "dark" (default) or "light", persisted in localStorage.
export function getTheme() {
  try {
    const saved = localStorage.getItem("questai_theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* private mode */
  }
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    return "light";
  }
  return "dark";
}

export function applyTheme(t) {
  if (t === "light") document.documentElement.dataset.theme = "light";
  else document.documentElement.removeAttribute("data-theme");
  try {
    localStorage.setItem("questai_theme", t);
  } catch {
    /* private mode */
  }
}
