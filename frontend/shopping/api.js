// Shopping API client — wraps authFetch (auto token refresh, shared with auth).
import { authFetch } from "../auth/api";

async function unwrap(res) {
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
    const err = new Error(typeof detail === "string" ? detail : "Request failed");
    err.code = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

export const LOCATIONS = [
  { code: "in", label: "India" },
  { code: "us", label: "United States" },
  { code: "uk", label: "United Kingdom" },
  { code: "ae", label: "UAE" },
  { code: "ca", label: "Canada" },
  { code: "au", label: "Australia" },
  { code: "de", label: "Germany" },
  { code: "sg", label: "Singapore" },
];

export const DEFAULT_LOCATION = "in";

export function locationLabel(code) {
  return (LOCATIONS.find((l) => l.code === code) || {}).label || "India";
}

export const shoppingApi = {
  search: async ({ query, session_id, location }) =>
    unwrap(
      await authFetch("/api/shopping/search", {
        method: "POST",
        body: JSON.stringify({
          query,
          ...(session_id ? { session_id } : {}),
          ...(location ? { location } : {}),
        }),
      })
    ),
  history: async (limit = 20) =>
    unwrap(await authFetch(`/api/shopping/history?limit=${limit}`)),
  getSession: async (session_id) =>
    unwrap(await authFetch(`/api/shopping/${session_id}`)),
  searchAgain: async (session_id, query, location) =>
    unwrap(
      await authFetch(`/api/shopping/${session_id}/search`, {
        method: "POST",
        body: JSON.stringify({
          ...(query ? { query } : {}),
          ...(location ? { location } : {}),
        }),
      })
    ),
  remove: async (session_id) =>
    unwrap(await authFetch(`/api/shopping/${session_id}`, { method: "DELETE" })),
};

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

export function formatINR(price) {
  if (typeof price !== "number" || !price) return "";
  return `₹${Math.round(price).toLocaleString("en-IN")}`;
}

const CURRENCY_SYMBOLS = {
  USD: "$", INR: "₹", EUR: "€", GBP: "£",
  AED: "AED ", CAD: "CA$", AUD: "A$", SGD: "S$",
};

export function currencySymbol(code) {
  return CURRENCY_SYMBOLS[code] || (code ? code + " " : "₹");
}

export function currencyLocale(code) {
  return code === "INR" ? "en-IN" : "en-US";
}
