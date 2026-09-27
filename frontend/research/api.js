// Research API client — wraps authFetch (auto token refresh, shared with auth).
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

export const researchApi = {
  run: async ({ query, session_id, force_new, force_continue, max_rounds }) =>
    unwrap(
      await authFetch("/api/research/run", {
        method: "POST",
        body: JSON.stringify({
          query,
          ...(session_id ? { session_id } : {}),
          ...(force_new ? { force_new: true } : {}),
          ...(force_continue ? { force_continue: true } : {}),
          ...(max_rounds ? { max_rounds } : {}),
        }),
      })
    ),
  history: async (limit = 30) => unwrap(await authFetch(`/api/research/history?limit=${limit}`)),
  getSession: async (session_id) => unwrap(await authFetch(`/api/research/${session_id}`)),
  cancel: async (session_id) =>
    unwrap(await authFetch(`/api/research/${session_id}/cancel`, { method: "POST" })),
  remove: async (session_id) =>
    unwrap(await authFetch(`/api/research/${session_id}`, { method: "DELETE" })),
};

export function timeAgo(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const s = Math.max(1, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}
