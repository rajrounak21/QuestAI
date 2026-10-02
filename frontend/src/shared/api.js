// Shared API helpers for agent frontends (flights, hotels, ...).
// Single copy of unwrap / timeAgo / currency helpers — was duplicated per agent.

export async function unwrap(res) {
  if (!res || res.unauthorized) {
    const err = new Error("Session expired. Please sign in again.");
    err.code = "unauthorized";
    throw err;
  }
  if (res.networkError) {
    const err = new Error("Cannot reach the server. Start the backend and retry.");
    err.code = "network";
    throw err;
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    // FastAPI validation errors come as an array — flatten to readable text
    // so the UI shows the real cause instead of generic "Request failed".
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => `${(d.loc || []).join(".")}: ${d.msg || JSON.stringify(d)}`).join("; ")
        : "Request failed";
    const err = new Error(message);
    err.code = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

export function timeAgo(iso) {
  if (!iso) return "";
  let str = String(iso);
  if (!str.endsWith("Z") && !str.includes("+") && !str.includes("Z")) {
    str += "Z";
  }
  const t = new Date(str).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(1, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(str).toLocaleDateString();
}

const CURRENCY_SYMBOLS = {
  USD: "$", INR: "₹", EUR: "€", GBP: "£",
  AED: "AED ", SAR: "SAR ", SGD: "S$ ", CAD: "CA$",
  AUD: "A$", JPY: "¥", CNY: "¥",
};

export function currencySymbol(code) {
  return CURRENCY_SYMBOLS[code] || (code ? code + " " : "$");
}

export function currencyLocale(code) {
  return code === "INR" ? "en-IN" : "en-US";
}
